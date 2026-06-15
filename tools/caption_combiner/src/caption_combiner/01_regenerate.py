#!/usr/bin/env python3
"""
01_regenerate.py — Batch generate combined captions using OpenAI GPT.

Usage:
    uv run python src/caption_combiner/01_regenerate.py
    uv run python src/caption_combiner/01_regenerate.py --limit 10
    uv run python src/caption_combiner/01_regenerate.py --use-category-prompts
    uv run python src/caption_combiner/01_regenerate.py --workers 10
"""

import argparse
import asyncio
import os
import random
import sys
import time
from pathlib import Path

# Fix encoding on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI, RateLimitError, APIStatusError

# Load .env
load_dotenv(Path(__file__).parent.parent.parent / ".env")

API_URL = os.getenv("ANNOTATOR_API_URL", "https://annotator-api.stecom.vn")
USERNAME = os.getenv("ANNOTATOR_USERNAME", "")
PASSWORD = os.getenv("ANNOTATOR_PASSWORD", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

# Rate limiting — mirror KB standardizer
MIN_REQUEST_DELAY_S = 0.75   # delay tối thiểu giữa các request khi acquire semaphore
MAX_RETRIES = 5
RETRY_BASE_DELAY = 2.0       # giây — base exponential backoff
RETRY_MAX_DELAY = 60.0       # giây — cap tối đa

# Giá gpt-5.4-mini
PRICE_INPUT_PER_1M = 0.75    # USD / 1M input tokens
PRICE_OUTPUT_PER_1M = 4.50   # USD / 1M output tokens

# ===================== KB DETECTION =====================

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

def detect_category(node: dict, all_nodes: list[dict]) -> str:
    if not node:
        return "UNKNOWN"
    id_index = {n.get("id"): n for n in all_nodes if n.get("id")}
    KEYWORD_MAP = [
        ("A", ["di tích", "lịch sử", "historic", "heritage", "monument", "communal house", "đình", "đền", "chùa", "miếu", "thành", "lăng", "bia", "pagoda", "temple", "shrine"]),
        ("B", ["hồ", "công viên", "cảnh quan", "lake", "park", "garden", "vườn hoa"]),
        ("C", ["bảo tàng", "museum"]),
        ("D", ["nghệ thuật", "biểu diễn", "performing arts", "ca trù", "chèo", "tuồng", "múa rối", "water puppet", "rối nước", "xẩm"]),
        ("E", ["lễ hội", "festival", "sự kiện", "hội làng"]),
        ("F", ["làng nghề", "craft village", "silk village", "làng lụa", "làng gốm", "làng đúc", "nghề truyền thống", "thủ công"]),
        ("G", ["ẩm thực", "food", "cuisine", "phở", "bún", "bánh", "chả", "nem", "bia hơi", "cốm", "kem tràng tiền", "quán ăn"]),
        ("H", ["hoạt động du lịch", "giải trí", "activity", "tour", "trải nghiệm", "experience"]),
        ("I", ["thiên nhiên", "ngoại thành", "nature", "mountain", "núi", "rừng", "thác nước", "national park", "vườn quốc gia"]),
        ("J", ["người dân", "văn hoá sống", "people", "lifestyle", "community", "phụ nữ", "women"]),
        ("K", ["bốn mùa", "mùa xuân", "mùa hè", "mùa thu", "mùa đông", "spring", "summer", "autumn", "fall", "winter", "season"]),
        ("L", ["video", "tư liệu", "documentary", "special", "đặc biệt"]),
    ]

    def match_letter(text: str) -> str | None:
        if not text: return None
        text_lower = text.lower()
        for letter, keywords in KEYWORD_MAP:
            for kw in keywords:
                if kw in text_lower:
                    return letter
        return None

    visited = set()
    current_id = node.get("parent_id")
    ancestor_chain = []
    while current_id and current_id not in visited:
        visited.add(current_id)
        ancestor = id_index.get(current_id)
        if not ancestor: break
        ancestor_chain.append(ancestor)
        current_id = ancestor.get("parent_id")

    for ancestor in reversed(ancestor_chain):
        l = match_letter(ancestor.get("name", "")) or match_letter(ancestor.get("name_vi", ""))
        if l: return l

    l = match_letter(node.get("name", "")) or match_letter(node.get("name_vi", ""))
    if l: return l

    return "UNKNOWN"

_prompt_cache = {}

def load_prompt(category_hint: str, use_category: bool) -> str:
    system_base_path = PROMPTS_DIR / "SYSTEM_BASE.md"
    base_prompt = system_base_path.read_text(encoding="utf-8") if system_base_path.exists() else "You are a helpful assistant."

    if not use_category or not category_hint or category_hint == "UNKNOWN":
        return base_prompt

    letter = category_hint.strip()[0].upper()
    if letter in _prompt_cache:
        return _prompt_cache[letter]

    prompt_file = CATEGORY_PROMPT_MAP.get(letter)
    if not prompt_file:
        _prompt_cache[letter] = base_prompt
        return base_prompt

    prompt_path = PROMPTS_DIR / prompt_file
    if not prompt_path.exists():
        _prompt_cache[letter] = base_prompt
        return base_prompt

    category_prompt = prompt_path.read_text(encoding="utf-8")
    full_prompt = base_prompt + "\n\n---\n\n" + category_prompt
    _prompt_cache[letter] = full_prompt
    return full_prompt

# ===================== ASYNC HTTP (fetch phase) =====================

async def async_get(client: httpx.AsyncClient, url: str, sem: asyncio.Semaphore):
    """GET with semaphore to avoid hammering our own API."""
    async with sem:
        r = await client.get(url)
    return r

async def fetch_segment_captions(client: httpx.AsyncClient, seg_id: str, fetch_sem: asyncio.Semaphore):
    r = await async_get(client, f"{API_URL}/api/annotations/segment/{seg_id}", fetch_sem)
    if r.status_code == 200:
        return [c for c in r.json() if c.get("knowledge_base_ids")]
    return []

async def fetch_video_captions(client: httpx.AsyncClient, vid: dict, fetch_sem: asyncio.Semaphore):
    vid_id = vid["id"]
    vid_name = vid.get("name", vid_id)

    r = await async_get(client, f"{API_URL}/api/videos/{vid_id}", fetch_sem)
    if r.status_code != 200:
        print(f"   ⚠️  Bỏ qua video {vid_name} (lỗi {r.status_code})")
        return []

    segments = r.json().get("segments", [])
    tasks = [fetch_segment_captions(client, seg["id"], fetch_sem) for seg in segments]
    results = await asyncio.gather(*tasks)
    found = sum(len(r) for r in results)
    captions = [cap for batch in results for cap in batch]
    print(f"   🎥 {vid_name}: {len(segments)} segs → {found} captions có KB")
    return captions

async def fetch_bulk_targets_async(token: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"}
    fetch_sem = asyncio.Semaphore(10)  # max 10 concurrent API calls when crawling

    async with httpx.AsyncClient(headers=headers, timeout=60) as client:
        print("📋 Đang lấy danh sách projects...")
        r = await client.get(f"{API_URL}/api/projects")
        r.raise_for_status()
        projects = r.json()
        print(f"   → {len(projects)} projects")

        all_captions = []
        for p_idx, proj in enumerate(projects):
            proj_id = proj["id"]
            proj_name = proj.get("name", proj_id)
            print(f"\n🗂  [{p_idx+1}/{len(projects)}] Project: {proj_name}")

            rv = await client.get(f"{API_URL}/api/videos/project/{proj_id}")
            if rv.status_code != 200:
                print(f"   ⚠️  Không lấy được danh sách video")
                continue
            videos = rv.json()
            print(f"   → {len(videos)} videos — đang quét song song...")

            # Fetch all videos in this project concurrently
            tasks = [fetch_video_captions(client, vid, fetch_sem) for vid in videos]
            results = await asyncio.gather(*tasks)
            proj_captions = [cap for batch in results for cap in batch]
            print(f"   ✅ Project xong: {len(proj_captions)} captions có KB")
            all_captions.extend(proj_captions)

    unique = {c["id"]: c for c in all_captions}
    data = list(unique.values())
    print(f"\n📦 Tổng captions có KB (dedup): {len(data)}")
    return data

# ===================== SYNC UPDATE =====================

def update_caption_sync(token: str, caption_id: str, payload: dict) -> bool:
    import requests as req
    url = f"{API_URL}/api/annotations/{caption_id}"
    resp = req.put(url, headers={"Authorization": f"Bearer {token}"}, json=payload, timeout=30)
    if not resp.ok:
        print(f"❌ Cập nhật thất bại caption {caption_id}: {resp.text[:200]}")
        return False
    return True

# ===================== GPT GENERATOR =====================

TRANSLATE_PROMPT = """Translate the following English text to Vietnamese.
Keep proper nouns, place names, and brand names as-is.
Output ONLY the translated Vietnamese text, no explanations."""

async def call_gpt_with_retry(
    client: AsyncOpenAI,
    messages: list,
    temperature: float,
    caption_id: str,
    step: str,
    usage_stats: dict,
    total_lock: asyncio.Lock,
    request_throttle: asyncio.Lock,
) -> str | None:
    """
    Gọi GPT với:
    - Throttle delay tối thiểu (MIN_REQUEST_DELAY_S) — tránh TPM spike
    - Exponential backoff + jitter khi gặp RateLimitError (429)
    - Xử lý riêng APIStatusError 400 (không retry) vs lỗi khác (retry)
    """
    # Throttle: đảm bảo delay tối thiểu giữa các request
    async with request_throttle:
        await asyncio.sleep(MIN_REQUEST_DELAY_S)

    for attempt in range(MAX_RETRIES):
        try:
            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=1000,
            )
            text = response.choices[0].message.content.strip()
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0

            async with total_lock:
                usage_stats["prompt_tokens"] += input_tokens
                usage_stats["completion_tokens"] += output_tokens

            print(f"      ✅ {step} [{caption_id[:12]}] | {input_tokens:>5} in / {output_tokens:>4} out tok")
            return text

        except RateLimitError:
            # 429 — đợi rồi retry với jitter
            delay = min(RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1), RETRY_MAX_DELAY)
            print(f"      ⏳ [{caption_id[:12]}] Rate limit ({step}, attempt {attempt+1}/{MAX_RETRIES}), đợi {delay:.1f}s...")
            await asyncio.sleep(delay)

        except APIStatusError as e:
            if e.status_code == 400:
                # Bad request — không retry
                print(f"      ❌ [{caption_id[:12]}] API Error 400 ({step}): {e.message}")
                return None
            # Lỗi 5xx — retry
            delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
            print(f"      ⏳ [{caption_id[:12]}] API Error {e.status_code} ({step}, attempt {attempt+1}/{MAX_RETRIES}), đợi {delay:.1f}s...")
            await asyncio.sleep(delay)

        except Exception as e:
            delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
            print(f"      ⏳ [{caption_id[:12]}] Lỗi: {e} ({step}, attempt {attempt+1}/{MAX_RETRIES}), đợi {delay:.1f}s...")
            await asyncio.sleep(delay)

    # Hết retry
    print(f"      ❌ [{caption_id[:12]}] Hết {MAX_RETRIES} lần retry ({step})")
    return None

async def process_caption(
    client: AsyncOpenAI, caption: dict, token: str,
    kb_index: dict, all_nodes: list,
    use_category: bool, sem: asyncio.Semaphore,
    counter: list, total_lock: asyncio.Lock, total: int,
    usage_stats: dict, request_throttle: asyncio.Lock,
):
    cap_id = caption["id"]
    kb_ids = caption.get("knowledge_base_ids", [])

    # Build knowledge text
    know_en_list, category_hint = [], "UNKNOWN"
    for idx, kb_id in enumerate(kb_ids):
        node = kb_index.get(kb_id)
        if node:
            if idx == 0:
                category_hint = detect_category(node, all_nodes)
            desc_en = str(node.get("description", "")).strip()
            if desc_en:
                know_en_list.append(desc_en)

    know_en = "\n\n".join(know_en_list)
    ctx_en = caption.get("contextual_caption") or caption.get("visual_caption") or ""

    if not ctx_en.strip() or not know_en.strip():
        return

    system_prompt = load_prompt(category_hint, use_category)

    async with sem:
        print(f"   🤖 [{cap_id[:12]}] category={category_hint} — sinh EN...")

        # Step 1: Generate EN
        combined_en = await call_gpt_with_retry(
            client,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Visual/Contextual Caption:\n{ctx_en}\n\nKnowledge Base Facts:\n{know_en}"},
            ],
            temperature=0.4,
            caption_id=cap_id,
            step="EN",
            usage_stats=usage_stats,
            total_lock=total_lock,
            request_throttle=request_throttle,
        )
        if not combined_en:
            return

        # Step 2: Translate EN → VI
        print(f"   🌐 [{cap_id[:12]}] — dịch VI...")
        combined_vi = await call_gpt_with_retry(
            client,
            messages=[
                {"role": "system", "content": TRANSLATE_PROMPT},
                {"role": "user", "content": combined_en},
            ],
            temperature=0.2,
            caption_id=cap_id,
            step="VI",
            usage_stats=usage_stats,
            total_lock=total_lock,
            request_throttle=request_throttle,
        )

    # Update API in thread executor (non-blocking)
    payload = {
        "combined_caption": combined_en,
        "combined_caption_vi": combined_vi or "",
        "skip_approval_reset": True,
    }
    loop = asyncio.get_event_loop()
    success = await loop.run_in_executor(None, update_caption_sync, token, cap_id, payload)
    if success:
        async with total_lock:
            counter[0] += 1
            done = counter[0]
        print(f"  [{done:>4}/{total}] ✅ {cap_id[:12]}")

# ===================== MAIN =====================

async def amain(args):
    start_time = time.time()

    print("🔐 Đang đăng nhập...")
    import requests as req
    r = req.post(f"{API_URL}/api/auth/login", json={"username": USERNAME, "password": PASSWORD}, timeout=30)
    r.raise_for_status()
    token = r.json().get("token") or r.json().get("access_token")
    print(f"✅ Đăng nhập thành công: {USERNAME}")

    print("\n📥 Đang tải KB nodes...")
    rk = req.get(f"{API_URL}/api/knowledge-base?tree=false", headers={"Authorization": f"Bearer {token}"}, timeout=60)
    rk.raise_for_status()
    all_nodes = rk.json()
    kb_index = {n["id"]: n for n in all_nodes if "id" in n}
    print(f"✅ {len(all_nodes)} KB nodes")

    print("\n🔍 Đang thu thập captions có KB (async, song song)...")
    captions = await fetch_bulk_targets_async(token)

    valid = [c for c in captions if (c.get("contextual_caption") or c.get("visual_caption"))]
    print(f"🎯 {len(valid)} captions đủ điều kiện")

    if args.limit:
        valid = valid[:args.limit]
        print(f"⚠️  Giới hạn thử {args.limit} captions")

    if not valid:
        print("✅ Không có gì cần cập nhật.")
        return

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    sem = asyncio.Semaphore(args.workers)
    request_throttle = asyncio.Lock()  # delay tối thiểu giữa các request
    counter = [0]
    total_lock = asyncio.Lock()
    total = len(valid)
    usage_stats = {"prompt_tokens": 0, "completion_tokens": 0}

    print(f"\n🚀 Bắt đầu sinh caption với {args.workers} workers song song...\n")
    tasks = [
        process_caption(client, cap, token, kb_index, all_nodes, args.use_category_prompts, sem, counter, total_lock, total, usage_stats, request_throttle)
        for cap in valid
    ]
    await asyncio.gather(*tasks)

    # Token Usage Report
    elapsed = time.time() - start_time
    ti, to = usage_stats["prompt_tokens"], usage_stats["completion_tokens"]
    PRICE_IN, PRICE_OUT = 0.150, 0.600
    cost = (ti / 1_000_000) * PRICE_IN + (to / 1_000_000) * PRICE_OUT
    throughput = counter[0] / (elapsed / 60) if elapsed > 0 else 0

    print("\n" + "=" * 52)
    print("         ====== TOKEN USAGE REPORT ======")
    print("=" * 52)
    print(f"   Model             : {OPENAI_MODEL}")
    print(f"   Workers           : {args.workers}")
    print(f"   Elapsed           : {elapsed:.1f}s ({elapsed/60:.1f} phút)")
    print(f"   Throughput        : {throughput:.1f} captions/phút")
    print("   " + "-" * 48)
    print(f"   Captions updated  : {counter[0]}/{total}")
    print("   " + "-" * 48)
    print(f"   Input tokens      : {ti:>10,}")
    print(f"   Output tokens     : {to:>10,}")
    print(f"   TOTAL tokens      : {ti+to:>10,}")
    print("   " + "-" * 48)
    print(f"   TOTAL COST (USD)  : ${cost:>8.4f}")
    print(f"   (${PRICE_INPUT_PER_1M}/1M in · ${PRICE_OUTPUT_PER_1M}/1M out)")
    print("=" * 52)
    print("\n✅ Hoàn tất!")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Số captions test tối đa")
    parser.add_argument("--workers", type=int, default=8, help="Số GPT requests song song (default: 8)")
    parser.add_argument("--use-category-prompts", action="store_true", help="Kết hợp 12 loại prompt theo danh mục")
    args = parser.parse_args()

    if not OPENAI_API_KEY:
        print("❌ Chưa cấu hình OPENAI_API_KEY trong .env")
        sys.exit(1)

    asyncio.run(amain(args))

if __name__ == "__main__":
    main()
