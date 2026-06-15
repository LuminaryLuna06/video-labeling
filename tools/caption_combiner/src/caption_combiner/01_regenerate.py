#!/usr/bin/env python3
"""
01_regenerate.py — Batch generate combined captions using OpenAI GPT.

Usage:
    uv run python src/caption_combiner/01_regenerate.py
    uv run python src/caption_combiner/01_regenerate.py --limit 10
    uv run python src/caption_combiner/01_regenerate.py --use-category-prompts
"""

import argparse
import asyncio
import os
import sys
import json
from pathlib import Path

# Fix encoding on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import requests
from dotenv import load_dotenv
from openai import AsyncOpenAI, RateLimitError, APIStatusError

# Load .env
load_dotenv(Path(__file__).parent.parent.parent / ".env")

API_URL = os.getenv("ANNOTATOR_API_URL", "https://annotator-api.stecom.vn")
USERNAME = os.getenv("ANNOTATOR_USERNAME", "")
PASSWORD = os.getenv("ANNOTATOR_PASSWORD", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

# Rate limiting settings
MIN_REQUEST_DELAY_S = 0.5
MAX_RETRIES = 5
RETRY_BASE_DELAY = 2.0
RETRY_MAX_DELAY = 60.0

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
        ("A. Di tích lịch sử - Văn hoá", ["di tích", "lịch sử", "historic", "heritage", "monument", "communal house", "đình", "đền", "chùa", "miếu", "thành", "lăng", "bia", "pagoda", "temple", "shrine"]),
        ("B. Hồ - Công viên - Cảnh quan", ["hồ", "công viên", "cảnh quan", "lake", "park", "garden", "vườn hoa"]),
        ("C. Bảo tàng", ["bảo tàng", "museum"]),
        ("D. Nghệ thuật biểu diễn", ["nghệ thuật", "biểu diễn", "performing arts", "ca trù", "chèo", "tuồng", "múa rối", "water puppet", "rối nước", "xẩm"]),
        ("E. Lễ hội - Sự kiện", ["lễ hội", "festival", "sự kiện", "hội làng"]),
        ("F. Làng nghề truyền thống", ["làng nghề", "craft village", "silk village", "làng lụa", "làng gốm", "làng đúc", "nghề truyền thống", "thủ công"]),
        ("G. Ẩm thực Hà Nội", ["ẩm thực", "food", "cuisine", "phở", "bún", "bánh", "chả", "nem", "bia hơi", "cốm", "kem tràng tiền", "quán ăn"]),
        ("H. Hoạt động du lịch & Giải trí", ["hoạt động du lịch", "giải trí", "activity", "tour", "trải nghiệm", "experience"]),
        ("I. Thiên nhiên & Ngoại thành", ["thiên nhiên", "ngoại thành", "nature", "mountain", "núi", "rừng", "thác nước", "national park", "vườn quốc gia"]),
        ("J. Người dân & Văn hoá sống", ["người dân", "văn hoá sống", "people", "lifestyle", "community", "phụ nữ", "women"]),
        ("K. Bốn mùa Hà Nội", ["bốn mùa", "mùa xuân", "mùa hè", "mùa thu", "mùa đông", "spring", "summer", "autumn", "fall", "winter", "season"]),
        ("L. Video đặc biệt", ["video", "tư liệu", "documentary", "special", "đặc biệt"]),
    ]

    def match_category(text: str) -> str | None:
        if not text: return None
        text_lower = text.lower()
        for category, keywords in KEYWORD_MAP:
            for kw in keywords:
                if kw in text_lower:
                    return category
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
        a_name = ancestor.get("name", "")
        a_vi = ancestor.get("name_vi", "")
        cat = match_category(a_name) or match_category(a_vi)
        if cat: return cat

    cat = match_category(node.get("name", "")) or match_category(node.get("name_vi", ""))
    if cat: return cat
    for tag in node.get("tags", []):
        cat = match_category(tag)
        if cat: return cat

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

# ===================== API =====================

def login() -> str:
    url = f"{API_URL}/api/auth/login"
    resp = requests.post(url, json={"username": USERNAME, "password": PASSWORD}, timeout=30)
    resp.raise_for_status()
    token = resp.json().get("token") or resp.json().get("access_token")
    print(f"✅ Đăng nhập thành công: {USERNAME}")
    return token

def fetch_kb_nodes(token: str) -> list[dict]:
    url = f"{API_URL}/api/knowledge-base?tree=false"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=60)
    resp.raise_for_status()
    nodes = resp.json()
    print(f"📦 Tổng số KB nodes: {len(nodes)}")
    return nodes

def fetch_bulk_targets(token: str) -> list[dict]:
    """Crawl projects -> videos -> segments -> segment captions to find captions with KB"""
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.get(f"{API_URL}/api/projects", headers=headers, timeout=30)
    resp.raise_for_status()
    projects = resp.json()
    
    captions_with_kb = []
    
    print(f"🔍 Quét dữ liệu từ {len(projects)} projects...")
    for proj in projects:
        proj_id = proj["id"]
        v_resp = requests.get(f"{API_URL}/api/videos/project/{proj_id}", headers=headers, timeout=30)
        if not v_resp.ok: continue
        videos = v_resp.json()
        
        for vid in videos:
            vid_id = vid["id"]
            vd_resp = requests.get(f"{API_URL}/api/videos/{vid_id}", headers=headers, timeout=30)
            if not vd_resp.ok: continue
            video_data = vd_resp.json()
            
            for seg in video_data.get("segments", []):
                seg_id = seg["id"]
                # Get all captions for this segment (both segment-level and region-level)
                sc_resp = requests.get(f"{API_URL}/api/annotations/segment/{seg_id}", headers=headers, timeout=30)
                if sc_resp.ok:
                    for cap in sc_resp.json():
                        if cap.get("knowledge_base_ids"):
                            captions_with_kb.append(cap)

    unique_captions = {c["id"]: c for c in captions_with_kb}
    data = list(unique_captions.values())
    print(f"📦 Tổng số captions có KB tìm thấy: {len(data)}")
    return data

def update_caption(token: str, caption_id: str, payload: dict) -> bool:
    url = f"{API_URL}/api/annotations/{caption_id}"
    resp = requests.put(url, headers={"Authorization": f"Bearer {token}"}, json=payload, timeout=30)
    if not resp.ok:
        print(f"❌ Cập nhật thất bại caption {caption_id}: {resp.text}")
        return False
    return True

# ===================== GPT GENERATOR =====================

TRANSLATE_PROMPT = """Translate the following English text to Vietnamese.
Keep proper nouns, place names, and brand names as-is.
Output ONLY the translated Vietnamese text, no explanations."""

async def call_gpt(client, system_prompt, visual_caption, knowledge_text):
    user_message = f"Visual/Contextual Caption:\n{visual_caption}\n\nKnowledge Base Facts:\n{knowledge_text}"
    response = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.4,
        max_completion_tokens=1000,
    )
    tokens = {
        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
        "completion_tokens": response.usage.completion_tokens if response.usage else 0,
    }
    return response.choices[0].message.content.strip(), tokens

async def translate_to_vi(client, en_text):
    response = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": TRANSLATE_PROMPT},
            {"role": "user", "content": en_text},
        ],
        temperature=0.2,
        max_completion_tokens=1000,
    )
    tokens = {
        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
        "completion_tokens": response.usage.completion_tokens if response.usage else 0,
    }
    return response.choices[0].message.content.strip(), tokens

async def process_caption(
    client, caption, token, kb_index, all_nodes, 
    use_category, sem, request_throttle, counter, total_lock, total, usage_stats
):
    kb_ids = caption.get("knowledge_base_ids", [])
    
    # 1. Build Knowledge Text locally
    know_en_list = []
    know_vi_list = []
    category_hint = "UNKNOWN"
    
    for idx, kb_id in enumerate(kb_ids):
        node = kb_index.get(kb_id)
        if node:
            if idx == 0:
                category_hint = detect_category(node, all_nodes)
            desc_en = str(node.get("description", "")).strip()
            desc_vi = str(node.get("description_vi", "")).strip()
            if desc_en: know_en_list.append(desc_en)
            if desc_vi: know_vi_list.append(desc_vi)
            
    know_en = "\n\n".join(know_en_list)
    know_vi = "\n\n".join(know_vi_list)

    system_prompt = load_prompt(category_hint, use_category)

    # EN: combine from EN contextual + EN knowledge
    ctx_en = caption.get("contextual_caption") or caption.get("visual_caption") or ""

    updates = {}
    combined_en = None

    async with sem:
        # Step 1: Generate English combined caption
        if ctx_en.strip() and know_en.strip():
            async with request_throttle:
                await asyncio.sleep(MIN_REQUEST_DELAY_S)
            for attempt in range(MAX_RETRIES):
                try:
                    combined_en, tokens_en = await call_gpt(client, system_prompt, ctx_en, know_en)
                    updates["combined_caption"] = combined_en
                    async with total_lock:
                        usage_stats["prompt_tokens"] += tokens_en["prompt_tokens"]
                        usage_stats["completion_tokens"] += tokens_en["completion_tokens"]
                    break
                except Exception as e:
                    if attempt == MAX_RETRIES - 1:
                        print(f"❌ Lỗi GPT (EN) ở caption {caption['id']}: {e}")
                    await asyncio.sleep(RETRY_BASE_DELAY * (2 ** attempt))

        # Step 2: Translate EN result to VI (not using VI inputs independently)
        if combined_en:
            async with request_throttle:
                await asyncio.sleep(MIN_REQUEST_DELAY_S)
            for attempt in range(MAX_RETRIES):
                try:
                    combined_vi, tokens_vi = await translate_to_vi(client, combined_en)
                    updates["combined_caption_vi"] = combined_vi
                    async with total_lock:
                        usage_stats["prompt_tokens"] += tokens_vi["prompt_tokens"]
                        usage_stats["completion_tokens"] += tokens_vi["completion_tokens"]
                    break
                except Exception as e:
                    if attempt == MAX_RETRIES - 1:
                        print(f"❌ Lỗi dịch (VI) ở caption {caption['id']}: {e}")
                    await asyncio.sleep(RETRY_BASE_DELAY * (2 ** attempt))

    if updates:
        # skip_approval_reset=True to preserve video approval status when running in bulk
        updates["skip_approval_reset"] = True
        success = update_caption(token, caption["id"], updates)
        if success:
            async with total_lock:
                counter[0] += 1
                done = counter[0]
            print(f"  [{done:>3}/{total}] ✅ Đã cập nhật caption {caption['id']}")

import time

async def amain(args):
    start_time = time.time()
    print("🔄 Đang chuẩn bị dữ liệu...")
    token = login()
    all_nodes = fetch_kb_nodes(token)
    kb_index = {n["id"]: n for n in all_nodes if "id" in n}

    captions = fetch_bulk_targets(token)
    
    # Filter only those that have visual/contextual caption
    valid_captions = []
    for c in captions:
        has_ctx_en = bool(c.get("contextual_caption") or c.get("visual_caption"))
        has_ctx_vi = bool(c.get("contextual_caption_vi") or c.get("visual_caption_vi"))
        
        # We already filtered captions to only those having knowledge_base_ids
        if has_ctx_en or has_ctx_vi:
            valid_captions.append(c)
            
    print(f"🎯 Có {len(valid_captions)} captions đủ điều kiện (có visual/contextual + knowledge).")

    if args.limit:
        valid_captions = valid_captions[:args.limit]
        print(f"⚠️ Giới hạn chạy {args.limit} captions.")

    if not valid_captions:
        print("✅ Xong.")
        return

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    sem = asyncio.Semaphore(args.workers)
    request_throttle = asyncio.Lock()
    counter = [0]
    total_lock = asyncio.Lock()
    total = len(valid_captions)
    usage_stats = {"prompt_tokens": 0, "completion_tokens": 0}

    tasks = [
        process_caption(
            client, cap, token, kb_index, all_nodes, 
            args.use_category_prompts, sem, request_throttle, 
            counter, total_lock, total, usage_stats
        )
        for cap in valid_captions
    ]
    
    print("\n🚀 Bắt đầu gọi GPT và cập nhật...")
    await asyncio.gather(*tasks)
    
    elapsed = time.time() - start_time
    total_input_tokens = usage_stats["prompt_tokens"]
    total_output_tokens = usage_stats["completion_tokens"]
    PRICE_INPUT_PER_1M = 0.150
    PRICE_OUTPUT_PER_1M = 0.600
    cost_input = (total_input_tokens / 1_000_000) * PRICE_INPUT_PER_1M
    cost_output = (total_output_tokens / 1_000_000) * PRICE_OUTPUT_PER_1M
    total_cost = cost_input + cost_output
    throughput = counter[0] / (elapsed / 60) if elapsed > 0 else 0

    print("\n" + "=" * 52)
    print("         ====== TOKEN USAGE REPORT ======")
    print("=" * 52)
    print(f"   Model             : {OPENAI_MODEL}")
    print(f"   Workers parallel  : {args.workers}")
    print(f"   Elapsed time      : {elapsed:.1f}s ({elapsed/60:.1f} phút)")
    print(f"   Throughput        : {throughput:.1f} captions/phút")
    print("   " + "-" * 48)
    print(f"   Captions updated  : {counter[0]}/{total}")
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
    print("\n✅ Hoàn tất!")
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Số lượng caption test tối đa")
    parser.add_argument("--workers", type=int, default=5, help="Số lượng concurrent request")
    parser.add_argument("--use-category-prompts", action="store_true", help="Bật để kết hợp 12 loại prompt")
    args = parser.parse_args()

    if not OPENAI_API_KEY:
        print("❌ Chưa cấu hình OPENAI_API_KEY trong .env")
        sys.exit(1)

    asyncio.run(amain(args))

if __name__ == "__main__":
    main()
