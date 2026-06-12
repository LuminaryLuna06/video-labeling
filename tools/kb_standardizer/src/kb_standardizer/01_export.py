#!/usr/bin/env python3
"""
01_export.py — Kéo toàn bộ KB nodes về file YAML để chuẩn hoá.

Cách chạy:
    uv run python src/kb_standardizer/01_export.py
    uv run python src/kb_standardizer/01_export.py --category "G. Ẩm thực Hà Nội"

Kết quả: output/kb_export_YYYYMMDD_HHMMSS.yaml
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Fix encoding on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import requests
import yaml
from dotenv import load_dotenv

# Load .env từ thư mục kb_standardizer (cha của src/)
load_dotenv(Path(__file__).parent.parent.parent / ".env")

API_URL = os.getenv("ANNOTATOR_API_URL", "https://annotator-api.stecom.vn")
USERNAME = os.getenv("ANNOTATOR_USERNAME", "")
PASSWORD = os.getenv("ANNOTATOR_PASSWORD", "")

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"


# ===================== AUTH =====================

def login() -> str:
    """Đăng nhập và lấy JWT token."""
    url = f"{API_URL}/api/auth/login"
    resp = requests.post(url, json={"username": USERNAME, "password": PASSWORD}, timeout=30)
    resp.raise_for_status()
    token = resp.json().get("token") or resp.json().get("access_token")
    if not token:
        raise RuntimeError(f"Không tìm thấy token trong response: {resp.json()}")
    print(f"✅ Đăng nhập thành công: {USERNAME}")
    return token


# ===================== FETCH KB =====================

def fetch_all_nodes(token: str) -> list[dict]:
    """Lấy toàn bộ KB nodes dạng flat list."""
    url = f"{API_URL}/api/knowledge-base?tree=false"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    nodes = resp.json()
    print(f"📦 Tổng số nodes kéo về: {len(nodes)}")
    return nodes


def detect_category(node: dict, all_nodes: list[dict]) -> str:
    """
    Tự động phát hiện danh mục của node bằng cách leo ngược cây KB.
    Thứ tự ưu tiên:
    1. Leo lên cây cha đến root → khớp từ khoá với từng ancestor
    2. So khớp từ khoá trong tên node (EN + VI)
    3. Fallback tags
    4. UNKNOWN
    """
    # Tạo index để tra nhanh theo id
    id_index = {n.get("id"): n for n in all_nodes if n.get("id")}

    # Map từ khóa → danh mục (ưu tiên từ dài đến ngắn)
    KEYWORD_MAP = [
        ("A. Di tích lịch sử - Văn hoá",   ["di tích", "lịch sử", "historic", "heritage", "monument", "communal house", "đình", "đền", "chùa", "miếu", "thành", "lăng", "bia", "pagoda", "temple", "shrine"]),
        ("B. Hồ - Công viên - Cảnh quan",   ["hồ", "công viên", "cảnh quan", "lake", "park", "garden", "vườn hoa"]),
        ("C. Bảo tàng",                      ["bảo tàng", "museum"]),
        ("D. Nghệ thuật biểu diễn",          ["nghệ thuật", "biểu diễn", "performing arts", "ca trù", "chèo", "tuồng", "múa rối", "water puppet", "rối nước", "xẩm"]),
        ("E. Lễ hội - Sự kiện",              ["lễ hội", "festival", "sự kiện", "hội làng"]),
        ("F. Làng nghề truyền thống",        ["làng nghề", "craft village", "silk village", "làng lụa", "làng gốm", "làng đúc", "nghề truyền thống", "thủ công"]),
        ("G. Ẩm thực Hà Nội",               ["ẩm thực", "food", "cuisine", "phở", "bún", "bánh", "chả", "nem", "bia hơi", "cốm", "kem tràng tiền", "quán ăn"]),
        ("H. Hoạt động du lịch & Giải trí", ["hoạt động du lịch", "giải trí", "activity", "tour", "trải nghiệm", "experience"]),
        ("I. Thiên nhiên & Ngoại thành",    ["thiên nhiên", "ngoại thành", "nature", "mountain", "núi", "rừng", "thác nước", "national park", "vườn quốc gia"]),
        ("J. Người dân & Văn hoá sống",     ["người dân", "văn hoá sống", "people", "lifestyle", "community", "phụ nữ", "women"]),
        ("K. Bốn mùa Hà Nội",              ["bốn mùa", "mùa xuân", "mùa hè", "mùa thu", "mùa đông", "spring", "summer", "autumn", "fall", "winter", "season"]),
        ("L. Video đặc biệt",               ["video", "tư liệu", "documentary", "special", "đặc biệt"]),
    ]

    def match_category(text: str) -> str | None:
        text_lower = text.lower()
        for category, keywords in KEYWORD_MAP:
            for kw in keywords:
                if kw in text_lower:
                    return category
        return None

    # Bước 1: Leo cây cha đến root
    visited = set()
    current_id = node.get("parent_id")
    ancestor_chain = []

    while current_id and current_id not in visited:
        visited.add(current_id)
        ancestor = id_index.get(current_id)
        if not ancestor:
            break
        ancestor_chain.append(ancestor)
        current_id = ancestor.get("parent_id")

    # Kiểm tra từ root xuống (ancestor xa nhất trước — thường là danh mục gốc)
    for ancestor in reversed(ancestor_chain):
        a_name = ancestor.get("name", "")
        a_vi = ancestor.get("name_vi", "")
        cat = match_category(a_name) or match_category(a_vi)
        if cat:
            return cat

    # Bước 2: So khớp tên node chính
    cat = match_category(node.get("name", "")) or match_category(node.get("name_vi", ""))
    if cat:
        return cat

    # Bước 3: So khớp tags
    for tag in node.get("tags", []):
        cat = match_category(tag)
        if cat:
            return cat

    return "UNKNOWN — cần gán thủ công"


# ===================== EXPORT =====================

def export_to_yaml(nodes: list[dict], all_nodes: list[dict], category_filter: str | None = None):
    """Xuất nodes ra file YAML."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = OUTPUT_DIR / f"kb_export_{timestamp}.yaml"

    # Lọc nếu cần
    if category_filter:
        # Lọc sẽ áp dụng sau khi detect category cho từng node
        pass

    export_nodes = []
    for node in nodes:
        category_hint = detect_category(node, all_nodes)

        # Lọc theo category nếu được chỉ định
        if category_filter and category_filter.lower() not in category_hint.lower():
            continue

        export_node = {
            "_id": node.get("id", ""),                      # MongoDB ObjectId — KHÔNG sửa
            "kb_id": node.get("kb_id", ""),                  # Slug — để verify
            "name": node.get("name", ""),
            "name_vi": node.get("name_vi", ""),
            "type": node.get("type", "concept"),
            "category_hint": category_hint,                  # Gợi ý chọn đúng prompt
            "description": node.get("description", ""),
            "description_vi": node.get("description_vi", ""),
            "description_graph": node.get("description_graph", ""),      # MỚI — GPT điền
            "description_graph_vi": node.get("description_graph_vi", ""), # MỚI — GPT điền
            "visual_cues": node.get("visual_cues", ""),
            "tags": node.get("tags", []),
        }
        export_nodes.append(export_node)

    output_data = {
        "metadata": {
            "exported_at": datetime.now().isoformat(),
            "total_nodes": len(export_nodes),
            "category_filter": category_filter or "ALL",
        },
        "nodes": export_nodes,
    }

    with open(filename, "w", encoding="utf-8") as f:
        yaml.dump(
            output_data,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=120,
        )

    print(f"\n✅ Đã xuất {len(export_nodes)} nodes → {filename}")
    print(f"📝 Bước tiếp theo:")
    print(f"   1. Kiểm tra file YAML trên, bổ sung/chỉnh sửa nếu cần")
    print(f"   2. Chạy: uv run python src/kb_standardizer/02_enrich.py --input {filename.name}")
    return filename


# ===================== MAIN =====================

def main():
    parser = argparse.ArgumentParser(description="Xuất KB nodes ra file YAML để chuẩn hoá")
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Lọc theo danh mục (vd: 'G. Ẩm thực', 'C. Bảo tàng'). Mặc định: xuất tất cả",
    )
    args = parser.parse_args()

    if not USERNAME or not PASSWORD:
        print("❌ Thiếu ANNOTATOR_USERNAME hoặc ANNOTATOR_PASSWORD trong .env")
        sys.exit(1)

    print(f"🔗 API URL: {API_URL}")
    token = login()
    nodes = fetch_all_nodes(token)
    export_to_yaml(nodes, nodes, category_filter=args.category)


if __name__ == "__main__":
    main()
