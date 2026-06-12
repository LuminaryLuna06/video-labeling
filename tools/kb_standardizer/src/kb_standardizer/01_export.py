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
    Tự động phát hiện danh mục của node dựa vào parent_id hoặc tags.
    Trả về chuỗi gợi ý như 'G. Ẩm thực Hà Nội'.
    """
    # Lấy thông tin cha để suy luận danh mục
    parent_id = node.get("parent_id")
    if parent_id:
        parent = next((n for n in all_nodes if n.get("id") == parent_id), None)
        if parent:
            parent_name = parent.get("name", "")
            parent_vi = parent.get("name_vi", "")
            # Map tên cha → danh mục
            category_map = {
                "Di tích lịch sử": "A. Di tích lịch sử - Văn hoá",
                "Historical": "A. Di tích lịch sử - Văn hoá",
                "Hồ": "B. Hồ - Công viên - Cảnh quan",
                "Công viên": "B. Hồ - Công viên - Cảnh quan",
                "Lake": "B. Hồ - Công viên - Cảnh quan",
                "Park": "B. Hồ - Công viên - Cảnh quan",
                "Bảo tàng": "C. Bảo tàng",
                "Museum": "C. Bảo tàng",
                "Nghệ thuật biểu diễn": "D. Nghệ thuật biểu diễn",
                "Performing Arts": "D. Nghệ thuật biểu diễn",
                "Lễ hội": "E. Lễ hội - Sự kiện",
                "Festival": "E. Lễ hội - Sự kiện",
                "Làng nghề": "F. Làng nghề truyền thống",
                "Craft Village": "F. Làng nghề truyền thống",
                "Ẩm thực": "G. Ẩm thực Hà Nội",
                "Food": "G. Ẩm thực Hà Nội",
                "Cuisine": "G. Ẩm thực Hà Nội",
                "Hoạt động": "H. Hoạt động du lịch & Giải trí",
                "Activity": "H. Hoạt động du lịch & Giải trí",
                "Thiên nhiên": "I. Thiên nhiên & Ngoại thành",
                "Nature": "I. Thiên nhiên & Ngoại thành",
                "Người dân": "J. Người dân & Văn hoá sống",
                "People": "J. Người dân & Văn hoá sống",
                "Bốn mùa": "K. Bốn mùa Hà Nội",
                "Season": "K. Bốn mùa Hà Nội",
                "Video đặc biệt": "L. Video đặc biệt",
                "Special": "L. Video đặc biệt",
            }
            for key, cat in category_map.items():
                if key.lower() in parent_name.lower() or key.lower() in parent_vi.lower():
                    return cat

    # Fallback: dùng tags
    tags = node.get("tags", [])
    for tag in tags:
        if "ẩm thực" in tag.lower() or "food" in tag.lower():
            return "G. Ẩm thực Hà Nội"
        if "lễ hội" in tag.lower() or "festival" in tag.lower():
            return "E. Lễ hội - Sự kiện"
        if "bảo tàng" in tag.lower() or "museum" in tag.lower():
            return "C. Bảo tàng"

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
