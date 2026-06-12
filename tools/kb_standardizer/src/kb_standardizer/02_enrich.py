#!/usr/bin/env python3
"""
02_enrich.py — Gọi GPT song song với rate-limit-safe để bổ sung mô tả cho KB nodes.

Cách chạy:
    uv run python src/kb_standardizer/02_enrich.py                  # tự chọn file mới nhất
    uv run python src/kb_standardizer/02_enrich.py --max 10         # test 10 nodes
    uv run python src/kb_standardizer/02_enrich.py --workers 5      # 5 concurrent (default)

Rate limit an toàn (OpenAI Tier 1 - gpt-5.4-mini):
    RPM: 500 req/phút  → mỗi worker cách nhau tối thiểu 120ms
    TPM: 200,000 tok/phút → với ~2000 tok/node, tối đa ~100 nodes/phút an toàn
    Cơ chế: semaphore + exponential backoff khi gặp 429

Kết quả:
    - Ghi YAML 1 lần duy nhất khi toàn bộ xong (không lock file)
    - Báo cáo tổng token (input + output) chính xác từ usage thực
"""

import argparse
import asyncio
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path

# Fix encoding on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import yaml
from dotenv import load_dotenv
from openai import AsyncOpenAI, RateLimitError, APIStatusError

# Load .env từ thư mục kb_standardizer (cha của src/)
load_dotenv(Path(__file__).parent.parent.parent / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

# Chi phí theo giá gpt-5.4-mini
PRICE_INPUT_PER_1M = 0.75    # USD / 1M input tokens
PRICE_OUTPUT_PER_1M = 4.50   # USD / 1M output tokens

# Rate limit constants (OpenAI Tier 1)
# TPM = 200,000 → với ~2,000 tok/node → tối đa ~100 nodes/60s
# RPM = 500 → rất thoải mái
# Để an toàn, giới hạn ~80 nodes/phút → delay 750ms giữa các request
MIN_REQUEST_DELAY_S = 0.75   # ms delay tối thiểu giữa các request khi acquire semaphore

# Retry config
MAX_RETRIES = 5
RETRY_BASE_DELAY = 2.0       # giây — base cho exponential backoff
RETRY_MAX_DELAY = 60.0       # giây — cap tối đa

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"

# Mapping category_hint → file prompt
CATEGORY_PROMPT_MAP = {
    "A": "A_di_tich_lich_su.md",
    "B": "B_ho_cong_vien.md",
    "C": "C_bao_tang.md",
    "D": "D_nghe_thuat_bieu_dien.md",
    "E": "E_le_hoi_su_kien.md",
    "F": "F_lang_nghe_truyen_thong.md",
    "G": "G_am_thuc.md",
    "H": "H_hoat_dong_du_lich.md",
    "I": "I_thien_nhien_ngoai_thanh.md",
    "J": "J_nguoi_dan_van_hoa_song.md",
    "K": "K_bon_mua_ha_noi.md",
    "L": "L_video_dac_biet.md",
}

# Cache prompt đã load — tránh đọc file lặp lại khi chạy song song
_prompt_cache: dict[str, str | None] = {}


# ===================== LOAD PROMPT =====================

def load_prompt(category_hint: str) -> str | None:
    """
    Load prompt = SYSTEM_BASE.md + prompt danh mục cụ thể.
    Kết quả được cache trong memory.
    """
    if not category_hint or category_hint.startswith("UNKNOWN"):
        return None

    letter = category_hint.strip()[0].upper()

    if letter in _prompt_cache:
        return _prompt_cache[letter]

    prompt_file = CATEGORY_PROMPT_MAP.get(letter)
    if not prompt_file:
        _prompt_cache[letter] = None
        return None

    prompt_path = PROMPTS_DIR / prompt_file
    if not prompt_path.exists():
        print(f"  ⚠️  Không tìm thấy file prompt: {prompt_path}")
        _prompt_cache[letter] = None
        return None

    system_base_path = PROMPTS_DIR / "SYSTEM_BASE.md"
    category_prompt = prompt_path.read_text(encoding="utf-8")

    if system_base_path.exists():
        base_prompt = system_base_path.read_text(encoding="utf-8")
        full_prompt = (
            base_prompt
            + "\n\n---\n\n"
            + "## Hướng dẫn cụ thể cho danh mục này\n\n"
            + category_prompt
        )
    else:
        full_prompt = category_prompt

    _prompt_cache[letter] = full_prompt
    return full_prompt


# ===================== GPT CALL (ASYNC + RETRY) =====================

async def call_gpt_with_retry(
    client: AsyncOpenAI,
    node: dict,
    system_prompt: str,
    semaphore: asyncio.Semaphore,
    index: int,
    total: int,
    counter: list,
    lock: asyncio.Lock,
    request_throttle: asyncio.Lock,
) -> dict:
    """
    Gọi GPT bất đồng bộ với:
    - Semaphore để giới hạn số lượng concurrent calls
    - Throttle delay tối thiểu giữa các request (tránh TPM limit)
    - Exponential backoff khi gặp RateLimitError (429)
    """
    kb_id = node.get("kb_id", "?")
    name = node.get("name", "?")

    user_message = f"""Thông tin node cần viết mô tả:
- Tên (EN): {node.get("name", "")}
- Tên (VI): {node.get("name_vi", "")}
- Loại: {node.get("type", "concept")}
- Danh mục: {node.get("category_hint", "")}
- Tags: {", ".join(node.get("tags", []))}
- Visual cues: {node.get("visual_cues", "")}

Trả về JSON (không markdown code block, chỉ JSON thuần):
{{
  "description": "...",
  "description_vi": "...",
  "description_graph": "...",
  "description_graph_vi": "..."
}}"""

    async with semaphore:
        # Throttle: đảm bảo delay tối thiểu giữa các request để tránh TPM spike
        async with request_throttle:
            await asyncio.sleep(MIN_REQUEST_DELAY_S)

        # Retry loop với exponential backoff
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.4,
                    max_completion_tokens=1200,
                    response_format={"type": "json_object"},
                )

                content = response.choices[0].message.content
                usage = response.usage

                # Đảm bảo usage không None
                input_tokens = usage.prompt_tokens if usage else 0
                output_tokens = usage.completion_tokens if usage else 0

                result = json.loads(content)

                async with lock:
                    counter[0] += 1
                    done = counter[0]

                print(
                    f"  [{done:>3}/{total}] ✅ {name[:35]:<35} "
                    f"| {input_tokens:>5} in / {output_tokens:>4} out tok"
                )

                return {
                    "index": index,
                    "result": result,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "error": False,
                }

            except RateLimitError as e:
                # 429 — đợi rồi retry
                delay = min(RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1), RETRY_MAX_DELAY)
                print(f"  ⏳ [{name[:25]}] Rate limit (attempt {attempt+1}/{MAX_RETRIES}), đợi {delay:.1f}s...")
                await asyncio.sleep(delay)

            except json.JSONDecodeError as e:
                async with lock:
                    counter[0] += 1
                    done = counter[0]
                print(f"  [{done:>3}/{total}] ❌ {name} ({kb_id}) — Lỗi parse JSON: {e}")
                return {"index": index, "error": True, "input_tokens": 0, "output_tokens": 0}

            except APIStatusError as e:
                if e.status_code == 400:
                    # Bad request — không retry
                    async with lock:
                        counter[0] += 1
                        done = counter[0]
                    print(f"  [{done:>3}/{total}] ❌ {name} ({kb_id}) — API Error 400: {e.message}")
                    return {"index": index, "error": True, "input_tokens": 0, "output_tokens": 0}
                # Lỗi khác — thử retry
                delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
                print(f"  ⏳ [{name[:25]}] API Error {e.status_code} (attempt {attempt+1}/{MAX_RETRIES}), đợi {delay:.1f}s...")
                await asyncio.sleep(delay)

            except Exception as e:
                delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
                print(f"  ⏳ [{name[:25]}] Lỗi: {e} (attempt {attempt+1}/{MAX_RETRIES}), đợi {delay:.1f}s...")
                await asyncio.sleep(delay)

        # Hết retry
        async with lock:
            counter[0] += 1
            done = counter[0]
        print(f"  [{done:>3}/{total}] ❌ {name} ({kb_id}) — Hết {MAX_RETRIES} lần retry")
        return {"index": index, "error": True, "input_tokens": 0, "output_tokens": 0}


# ===================== NEEDS ENRICHMENT =====================

def needs_enrichment(node: dict) -> bool:
    return (
        not node.get("description")
        or not node.get("description_vi")
        or not node.get("description_graph")
        or not node.get("description_graph_vi")
    )


# ===================== MAIN ENRICH (ASYNC) =====================

async def enrich_nodes_async(input_file: Path, max_nodes: int | None = None, workers: int = 5):
    """
    Đọc YAML, gọi GPT song song với rate-limit protection,
    gom kết quả trong memory, ghi YAML 1 lần duy nhất khi xong.
    """
    with open(input_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    nodes = data.get("nodes", [])
    print(f"📂 Đọc {len(nodes)} nodes từ {input_file.name}")

    # Lọc nodes cần xử lý
    to_process_indices = [i for i, n in enumerate(nodes) if needs_enrichment(n)]
    skipped = len(nodes) - len(to_process_indices)

    if max_nodes:
        to_process_indices = to_process_indices[:max_nodes]

    total = len(to_process_indices)
    print(f"🎯 Cần làm giàu   : {total} nodes")
    print(f"⏭️  Bỏ qua (đủ rồi): {skipped} nodes")
    print(f"⚡ Concurrent workers: {workers}")
    print(f"⏱️  Throttle delay  : {MIN_REQUEST_DELAY_S}s/req (tránh TPM={200_000:,}/phút)")
    print(f"🔁 Retry           : tối đa {MAX_RETRIES} lần khi gặp 429\n")

    if total == 0:
        print("✅ Tất cả nodes đã có đủ mô tả — không cần làm gì!")
        return None

    # Thời gian dự kiến
    est_seconds = total * MIN_REQUEST_DELAY_S / workers
    print(f"⏳ Thời gian dự kiến: ~{est_seconds:.0f}s ({est_seconds/60:.1f} phút)\n")

    # Pre-load tất cả prompts vào cache trước khi chạy async
    categories_needed = set(nodes[i].get("category_hint", "") for i in to_process_indices)
    for cat in categories_needed:
        load_prompt(cat)

    # Tạo async client + synchronization primitives
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    semaphore = asyncio.Semaphore(workers)
    lock = asyncio.Lock()
    request_throttle = asyncio.Lock()  # serialize request timing
    counter = [0]

    start_time = asyncio.get_event_loop().time()

    # Tạo và chạy tất cả tasks
    tasks = []
    skip_indices = []

    for node_idx in to_process_indices:
        node = nodes[node_idx]
        category = node.get("category_hint", "UNKNOWN")
        system_prompt = load_prompt(category)

        if not system_prompt:
            print(f"  ⚠️  Bỏ qua '{node.get('name', '?')}' — không có prompt cho '{category}'")
            skip_indices.append(node_idx)
            continue

        tasks.append(
            call_gpt_with_retry(
                client=client,
                node=node,
                system_prompt=system_prompt,
                semaphore=semaphore,
                index=node_idx,
                total=total,
                counter=counter,
                lock=lock,
                request_throttle=request_throttle,
            )
        )

    # Chạy song song, thu kết quả khi mỗi task xong
    results = await asyncio.gather(*tasks, return_exceptions=True)

    elapsed = asyncio.get_event_loop().time() - start_time

    # ===================== GOM KẾT QUẢ VÀO MEMORY =====================
    total_input_tokens = 0
    total_output_tokens = 0
    processed = 0
    errors = len(skip_indices)  # nodes bị bỏ qua do thiếu prompt

    for res in results:
        if isinstance(res, Exception):
            errors += 1
            continue

        if res.get("error"):
            errors += 1
            continue

        node_idx = res["index"]
        node = nodes[node_idx]
        gpt_result = res.get("result", {})

        # Chỉ điền trường còn trống — không overwrite dữ liệu cũ
        for field in ["description", "description_vi", "description_graph", "description_graph_vi"]:
            if not node.get(field) and gpt_result.get(field):
                node[field] = gpt_result[field]

        # Cộng token chính xác từ usage thực
        total_input_tokens += res["input_tokens"]
        total_output_tokens += res["output_tokens"]
        processed += 1

    # ===================== GHI FILE YAML 1 LẦN DUY NHẤT =====================
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"kb_enriched_{timestamp}.yaml"

    data["metadata"]["enriched_at"] = datetime.now().isoformat()
    data["metadata"]["nodes_enriched"] = processed
    data["metadata"]["nodes_skipped"] = skipped
    data["metadata"]["nodes_errors"] = errors
    data["metadata"]["model_used"] = OPENAI_MODEL
    data["metadata"]["workers"] = workers
    data["metadata"]["total_input_tokens"] = total_input_tokens
    data["metadata"]["total_output_tokens"] = total_output_tokens
    data["metadata"]["elapsed_seconds"] = round(elapsed, 1)

    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=120,
        )

    # ========= TOKEN USAGE REPORT =========
    cost_input = (total_input_tokens / 1_000_000) * PRICE_INPUT_PER_1M
    cost_output = (total_output_tokens / 1_000_000) * PRICE_OUTPUT_PER_1M
    total_cost = cost_input + cost_output
    throughput = processed / (elapsed / 60) if elapsed > 0 else 0

    print("\n" + "=" * 52)
    print("         ====== TOKEN USAGE REPORT ======")
    print("=" * 52)
    print(f"   Model             : {OPENAI_MODEL}")
    print(f"   Workers parallel  : {workers}")
    print(f"   Elapsed time      : {elapsed:.1f}s ({elapsed/60:.1f} phút)")
    print(f"   Throughput        : {throughput:.1f} nodes/phút")
    print("   " + "-" * 48)
    print(f"   Nodes processed   : {processed}")
    print(f"   Nodes skipped     : {skipped} (đã có đủ mô tả)")
    print(f"   Nodes errors      : {errors}")
    print("   " + "-" * 48)
    print(f"   Input tokens      : {total_input_tokens:>10,}")
    print(f"   Output tokens     : {total_output_tokens:>10,}")
    print(f"   TOTAL tokens      : {total_input_tokens + total_output_tokens:>10,}")
    print("   " + "-" * 48)
    print(f"   Cost input        : ${cost_input:>8.4f}")
    print(f"   Cost output       : ${cost_output:>8.4f}")
    print(f"   TOTAL COST (USD)  : ${total_cost:>8.4f}")
    print(f"   (Giá: ${PRICE_INPUT_PER_1M}/1M in · ${PRICE_OUTPUT_PER_1M}/1M out)")
    print("=" * 52)

    print(f"\n✅ Đã lưu kết quả → {output_file.name}")
    return output_file


# ===================== MAIN =====================

def find_latest_file(pattern: str) -> Path | None:
    """Tìm file YAML mới nhất trong output/ khớp với pattern."""
    files = sorted(OUTPUT_DIR.glob(pattern), reverse=True)
    return files[0] if files else None


def main():
    parser = argparse.ArgumentParser(
        description="Gọi GPT song song (rate-limit-safe) để bổ sung mô tả cho KB nodes"
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Tên file YAML trong thư mục output/. Nếu bỏ trống, tự chọn kb_export_*.yaml mới nhất.",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help="Số lượng node tối đa (để test). Mặc định: tất cả",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="Số concurrent GPT calls (default: 5). Tier1 TPM=200K → ~100 nodes/phút an toàn",
    )
    args = parser.parse_args()

    if not OPENAI_API_KEY or OPENAI_API_KEY == "your_actual_openai_api_key_here":
        print("❌ Thiếu OPENAI_API_KEY trong .env")
        sys.exit(1)

    # Resolve đường dẫn input
    if args.input:
        input_path = Path(args.input)
        if not input_path.is_absolute():
            input_path = OUTPUT_DIR / input_path
    else:
        input_path = find_latest_file("kb_export_*.yaml")
        if not input_path:
            print("❌ Không tìm thấy file kb_export_*.yaml nào trong output/")
            print("   Hãy chạy trước: uv run python src/kb_standardizer/01_export.py")
            sys.exit(1)
        print(f"ℹ️  Tự động chọn file mới nhất: {input_path.name}")

    if not input_path.exists():
        print(f"❌ Không tìm thấy file: {input_path}")
        sys.exit(1)

    print(f"🚀 Model: {OPENAI_MODEL} | Input: {input_path.name}\n")

    asyncio.run(
        enrich_nodes_async(
            input_file=input_path,
            max_nodes=args.max,
            workers=args.workers,
        )
    )


if __name__ == "__main__":
    main()
