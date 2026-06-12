#!/usr/bin/env python3
"""
02_enrich.py — Gọi GPT (gpt-5.4-mini) để bổ sung mô tả cho các KB nodes trống.

Cách chạy:
    uv run python src/kb_standardizer/02_enrich.py --input output/kb_export_20260612_120000.yaml
    uv run python src/kb_standardizer/02_enrich.py --input output/kb_export_20260612_120000.yaml --max 5

Kết quả: output/kb_enriched_YYYYMMDD_HHMMSS.yaml + báo cáo token & chi phí
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Fix encoding on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import yaml
from dotenv import load_dotenv
from openai import OpenAI

# Load .env từ thư mục kb_standardizer (cha của src/)
load_dotenv(Path(__file__).parent.parent.parent / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

# Chi phí theo giá gpt-5.4-mini
PRICE_INPUT_PER_1M = 0.75    # USD / 1M input tokens
PRICE_OUTPUT_PER_1M = 4.50   # USD / 1M output tokens

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


# ===================== LOAD PROMPT =====================

def load_prompt(category_hint: str) -> str | None:
    """
    Load prompt hệ thống = SYSTEM_BASE.md (quy tắc chung) + prompt danh mục cụ thể.
    SYSTEM_BASE.md được ghép vào đầu để GPT hiểu toàn bộ bức tranh 12 danh mục.
    """
    if not category_hint or category_hint.startswith("UNKNOWN"):
        return None

    # Lấy chữ cái đầu tiên (A, B, C, ...)
    letter = category_hint.strip()[0].upper()
    prompt_file = CATEGORY_PROMPT_MAP.get(letter)
    if not prompt_file:
        return None

    prompt_path = PROMPTS_DIR / prompt_file
    if not prompt_path.exists():
        print(f"  ⚠️  Không tìm thấy file prompt: {prompt_path}")
        return None

    # Ghép SYSTEM_BASE.md (quy tắc chung) + prompt danh mục cụ thể
    system_base_path = PROMPTS_DIR / "SYSTEM_BASE.md"
    category_prompt = prompt_path.read_text(encoding="utf-8")

    if system_base_path.exists():
        base_prompt = system_base_path.read_text(encoding="utf-8")
        return (
            base_prompt
            + "\n\n---\n\n"
            + "## Hướng dẫn cụ thể cho danh mục này\n\n"
            + category_prompt
        )
    else:
        return category_prompt


# ===================== GPT CALL =====================

def call_gpt(client: OpenAI, node: dict, system_prompt: str) -> dict | None:
    """
    Gọi GPT để sinh ra 4 trường description.
    Trả về dict với keys: description, description_vi, description_graph, description_graph_vi.
    Trả về None nếu lỗi.
    """
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

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.4,
            max_tokens=1200,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        usage = response.usage

        result = json.loads(content)
        return {
            "result": result,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
        }
    except json.JSONDecodeError as e:
        print(f"  ❌ Lỗi parse JSON: {e}")
        return None
    except Exception as e:
        print(f"  ❌ Lỗi gọi GPT: {e}")
        return None


# ===================== ENRICH =====================

def needs_enrichment(node: dict) -> bool:
    """Kiểm tra node có cần bổ sung mô tả không."""
    return (
        not node.get("description")
        or not node.get("description_vi")
        or not node.get("description_graph")
        or not node.get("description_graph_vi")
    )


def enrich_nodes(input_file: Path, max_nodes: int | None = None):
    """Đọc YAML, gọi GPT bổ sung, xuất file mới."""
    with open(input_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    nodes = data.get("nodes", [])
    print(f"📂 Đọc {len(nodes)} nodes từ {input_file.name}")

    client = OpenAI(api_key=OPENAI_API_KEY)

    # Thống kê token
    total_input_tokens = 0
    total_output_tokens = 0
    processed = 0
    skipped = 0
    errors = 0

    to_process = [n for n in nodes if needs_enrichment(n)]
    if max_nodes:
        to_process = to_process[:max_nodes]

    print(f"🎯 Cần làm giàu: {len(to_process)} nodes\n")

    for i, node in enumerate(nodes):
        if not needs_enrichment(node):
            skipped += 1
            continue

        # Kiểm tra đã được xử lý trong batch này chưa
        if processed >= len(to_process):
            break

        kb_id = node.get("kb_id", "?")
        name = node.get("name", "?")
        category = node.get("category_hint", "UNKNOWN")
        print(f"[{processed + 1}/{len(to_process)}] 🔄 {name} ({kb_id}) — {category}")

        # Load prompt phù hợp
        system_prompt = load_prompt(category)
        if not system_prompt:
            print(f"  ⚠️  Không có prompt cho danh mục '{category}' — bỏ qua")
            errors += 1
            processed += 1
            continue

        # Gọi GPT
        gpt_resp = call_gpt(client, node, system_prompt)
        if gpt_resp is None:
            errors += 1
            processed += 1
            continue

        result = gpt_resp["result"]
        total_input_tokens += gpt_resp["prompt_tokens"]
        total_output_tokens += gpt_resp["completion_tokens"]

        # Cập nhật vào node — chỉ ghi đè trường đang trống
        for field in ["description", "description_vi", "description_graph", "description_graph_vi"]:
            if not node.get(field) and result.get(field):
                node[field] = result[field]

        processed += 1
        print(f"  ✅ Xong | tokens: +{gpt_resp['prompt_tokens']} in / +{gpt_resp['completion_tokens']} out")

        # Delay nhỏ để tránh rate limit
        if processed < len(to_process):
            time.sleep(0.5)

    # Xuất file kết quả
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"kb_enriched_{timestamp}.yaml"

    data["metadata"]["enriched_at"] = datetime.now().isoformat()
    data["metadata"]["nodes_enriched"] = processed - errors
    data["metadata"]["model_used"] = OPENAI_MODEL

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

    print("\n" + "=" * 40)
    print("   ====== TOKEN USAGE REPORT ======")
    print(f"   Model             : {OPENAI_MODEL}")
    print(f"   Nodes processed   : {processed - errors}")
    print(f"   Nodes skipped     : {skipped} (đã có đủ mô tả)")
    print(f"   Nodes errors      : {errors}")
    print(f"   Input tokens      : {total_input_tokens:,}")
    print(f"   Output tokens     : {total_output_tokens:,}")
    print(f"   Total tokens      : {total_input_tokens + total_output_tokens:,}")
    print(f"   Est. cost (USD)   : ${total_cost:.4f}")
    print(f"   (gpt-5.4-mini: ${PRICE_INPUT_PER_1M}/1M in, ${PRICE_OUTPUT_PER_1M}/1M out)")
    print("=" * 40)

    print(f"\n✅ Đã lưu kết quả → {output_file}")
    print(f"📝 Bước tiếp theo:")
    print(f"   1. Review file YAML trên, kiểm tra chất lượng mô tả")
    print(f"   2. Chỉnh sửa nếu cần, sau đó chạy:")
    print(f"      uv run python src/kb_standardizer/03_import.py --input {output_file.name}")
    return output_file


# ===================== MAIN =====================

def find_latest_file(pattern: str) -> Path | None:
    """Tìm file YAML mới nhất trong output/ khớp với pattern (vd: 'kb_export_*.yaml')."""
    files = sorted(OUTPUT_DIR.glob(pattern), reverse=True)
    return files[0] if files else None


def main():
    parser = argparse.ArgumentParser(description="Gọi GPT bổ sung mô tả cho KB nodes từ file YAML")
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Tên file YAML trong thư mục output/ (vd: kb_export_20260612_120000.yaml). "
             "Nếu bỏ trống, tự động chọn file kb_export_*.yaml mới nhất.",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help="Số lượng node tối đa cần xử lý (để test thử). Mặc định: tất cả",
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
        # Tự động tìm file kb_export_*.yaml mới nhất
        input_path = find_latest_file("kb_export_*.yaml")
        if not input_path:
            print("❌ Không tìm thấy file kb_export_*.yaml nào trong output/")
            print("   Hãy chạy trước: uv run python src/kb_standardizer/01_export.py")
            sys.exit(1)
        print(f"ℹ️  Tự động chọn file mới nhất: {input_path.name}")

    if not input_path.exists():
        print(f"❌ Không tìm thấy file: {input_path}")
        sys.exit(1)

    print(f"🚀 Bắt đầu làm giàu dữ liệu với model: {OPENAI_MODEL}")
    print(f"📂 Input: {input_path.name}")
    enrich_nodes(input_path, max_nodes=args.max)


if __name__ == "__main__":
    main()
