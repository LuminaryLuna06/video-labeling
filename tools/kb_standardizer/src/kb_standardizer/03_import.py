#!/usr/bin/env python3
"""
03_import.py — Đẩy YAML đã review lên server với cơ chế double-check an toàn.

Cách chạy:
    uv run python src/kb_standardizer/03_import.py --input output/kb_enriched_20260612_120000.yaml
    uv run python src/kb_standardizer/03_import.py --input output/kb_enriched_20260612_120000.yaml --dry-run

Cơ chế an toàn:
    Trước khi cập nhật, script sẽ fetch node từ server và kiểm tra kb_id trùng khớp.
    Nếu không trùng → báo lỗi và BỎ QUA, không bao giờ cập nhật nhầm node.
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Fix encoding on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import requests
import yaml
from dotenv import load_dotenv

# Load .env từ thư mục kb_standardizer
load_dotenv(Path(__file__).parent.parent.parent / ".env")

API_URL = os.getenv("ANNOTATOR_API_URL", "https://annotator-api.stecom.vn")
USERNAME = os.getenv("ANNOTATOR_USERNAME", "")
PASSWORD = os.getenv("ANNOTATOR_PASSWORD", "")

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"

# Trường cần cập nhật lên server
FIELDS_TO_UPDATE = [
    "description",
    "description_vi",
    "description_graph",
    "description_graph_vi",
]


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


# ===================== VERIFY & UPDATE =====================

def verify_node(node_id: str, expected_kb_id: str, headers: dict) -> tuple[bool, str]:
    """
    Fetch node từ server và kiểm tra kb_id có trùng khớp không.
    Trả về (True, '') nếu an toàn, (False, reason) nếu có vấn đề.
    """
    url = f"{API_URL}/api/knowledge-base/{node_id}"
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 404:
            return False, f"Node {node_id} không tồn tại trên server"
        resp.raise_for_status()
        server_node = resp.json()
        server_kb_id = server_node.get("kb_id", "")
        if server_kb_id != expected_kb_id:
            return False, (
                f"kb_id KHÔNG KHỚP: YAML='{expected_kb_id}' vs Server='{server_kb_id}'. "
                f"Có thể _id trong YAML bị sai. Bỏ qua!"
            )
        return True, ""
    except requests.exceptions.HTTPError as e:
        return False, f"HTTP Error khi verify: {e}"
    except Exception as e:
        return False, f"Lỗi không xác định khi verify: {e}"


def update_node(node_id: str, update_payload: dict, headers: dict) -> tuple[bool, str]:
    """Gọi PUT để cập nhật node."""
    url = f"{API_URL}/api/knowledge-base/{node_id}"
    try:
        resp = requests.put(url, json=update_payload, headers=headers, timeout=30)
        resp.raise_for_status()
        return True, ""
    except requests.exceptions.HTTPError as e:
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, str(e)


# ===================== IMPORT =====================

def import_yaml(input_file: Path, dry_run: bool = False):
    """Đọc YAML và cập nhật từng node lên server với double-check."""
    with open(input_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    nodes = data.get("nodes", [])
    print(f"📂 Đọc {len(nodes)} nodes từ {input_file.name}")

    if dry_run:
        print("🧪 [DRY RUN MODE] — Không thực sự cập nhật server, chỉ kiểm tra logic\n")

    if not dry_run:
        token = login()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    else:
        headers = {}

    success_count = 0
    fail_count = 0
    skip_count = 0
    fail_details = []

    for i, node in enumerate(nodes):
        node_id = node.get("_id", "")
        kb_id = node.get("kb_id", "")
        name = node.get("name", "?")

        print(f"[{i + 1}/{len(nodes)}] 🔍 {name} ({kb_id})")

        if not node_id:
            msg = "Thiếu trường _id — bỏ qua"
            print(f"  ⚠️  {msg}")
            skip_count += 1
            fail_details.append({"kb_id": kb_id, "reason": msg})
            continue

        # Kiểm tra có trường nào cần cập nhật không
        update_payload = {
            field: node[field]
            for field in FIELDS_TO_UPDATE
            if field in node and node[field]
        }

        if not update_payload:
            print(f"  ⏭️  Không có trường nào cần cập nhật — bỏ qua")
            skip_count += 1
            continue

        if dry_run:
            print(f"  [DRY RUN] Sẽ cập nhật {list(update_payload.keys())}")
            success_count += 1
            continue

        # ===== DOUBLE-CHECK AN TOÀN =====
        is_safe, reason = verify_node(node_id, kb_id, headers)
        if not is_safe:
            print(f"  ❌ VERIFY FAILED: {reason}")
            fail_count += 1
            fail_details.append({"kb_id": kb_id, "node_id": node_id, "reason": reason})
            continue

        # ===== CẬP NHẬT =====
        ok, err = update_node(node_id, update_payload, headers)
        if ok:
            print(f"  ✅ Cập nhật thành công | fields: {list(update_payload.keys())}")
            success_count += 1
        else:
            print(f"  ❌ Cập nhật thất bại: {err}")
            fail_count += 1
            fail_details.append({"kb_id": kb_id, "node_id": node_id, "reason": err})

        # Delay nhỏ để không spam API
        time.sleep(0.2)

    # ========= BÁO CÁO =========
    print("\n" + "=" * 45)
    print("   ====== IMPORT REPORT ======")
    print(f"   File              : {input_file.name}")
    print(f"   Dry Run           : {'YES' if dry_run else 'NO'}")
    print(f"   Total nodes       : {len(nodes)}")
    print(f"   ✅ Thành công      : {success_count}")
    print(f"   ⏭️  Bỏ qua         : {skip_count}")
    print(f"   ❌ Thất bại        : {fail_count}")
    if fail_details:
        print("\n   Chi tiết lỗi:")
        for d in fail_details:
            print(f"     - [{d.get('kb_id', '?')}] {d.get('reason', '')}")
    print("=" * 45)


# ===================== MAIN =====================

def find_latest_file(pattern: str) -> Path | None:
    """Tìm file YAML mới nhất trong output/ khớp với pattern."""
    files = sorted(OUTPUT_DIR.glob(pattern), reverse=True)
    return files[0] if files else None


def main():
    parser = argparse.ArgumentParser(
        description="Đẩy YAML đã review lên server với double-check an toàn"
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Tên file YAML trong thư mục output/ (vd: kb_enriched_20260612_120000.yaml). "
             "Nếu bỏ trống, tự động chọn file kb_enriched_*.yaml mới nhất.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chạy thử không gọi API thật — chỉ kiểm tra logic",
    )
    args = parser.parse_args()

    if not USERNAME or not PASSWORD:
        print("❌ Thiếu ANNOTATOR_USERNAME hoặc ANNOTATOR_PASSWORD trong .env")
        sys.exit(1)

    # Resolve đường dẫn input
    if args.input:
        input_path = Path(args.input)
        if not input_path.is_absolute():
            input_path = OUTPUT_DIR / input_path
    else:
        # Tự động tìm file kb_enriched_*.yaml mới nhất
        input_path = find_latest_file("kb_enriched_*.yaml")
        if not input_path:
            # Fallback: thử tìm kb_export_*.yaml (trường hợp import thẳng từ export)
            input_path = find_latest_file("kb_export_*.yaml")
            if not input_path:
                print("❌ Không tìm thấy file YAML nào trong output/")
                print("   Hãy chạy trước: uv run python src/kb_standardizer/01_export.py")
                sys.exit(1)
            print(f"⚠️  Không có kb_enriched_*.yaml, dùng file export: {input_path.name}")
        else:
            print(f"ℹ️  Tự động chọn file mới nhất: {input_path.name}")

    if not input_path.exists():
        print(f"❌ Không tìm thấy file: {input_path}")
        sys.exit(1)

    print(f"🚀 Bắt đầu import: {input_path.name}")
    import_yaml(input_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
