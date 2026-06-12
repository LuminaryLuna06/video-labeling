# KB Standardizer — Bộ công cụ chuẩn hoá Knowledge Base

Bộ công cụ 3 bước để chuẩn hoá và làm giàu nội dung các node trong Knowledge Base du lịch Hà Nội.

## Quy trình làm việc

```
[01_export] → YAML nháp → [Con người thẩm định] → [02_enrich] → YAML đã làm giàu → [Con người review] → [03_import]
```

**Tại sao 3 bước?** Để con người kiểm soát hoàn toàn — GPT chỉ là công cụ trợ lý, không tự động cập nhật lên server.

---

## Cài đặt

### Yêu cầu

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) — quản lý package

### Cài đặt uv (nếu chưa có)

```bash
pip install uv
```

### Cài đặt dependencies

```bash
cd tools/kb_standardizer
uv sync
```

### Cấu hình môi trường

```bash
cp .env.example .env
```

Chỉnh sửa file `.env`:

```env
ANNOTATOR_API_URL=https://annotator-api.stecom.vn
ANNOTATOR_USERNAME=your_username
ANNOTATOR_PASSWORD=your_password
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4-mini
```

> ⚠️ File `.env` đã được git-ignored. Không commit lên git.

---

## Hướng dẫn sử dụng

### Bước 1: Xuất dữ liệu KB ra YAML

```bash
# Xuất tất cả nodes
uv run python src/kb_standardizer/01_export.py

# Xuất theo danh mục (lọc)
uv run python src/kb_standardizer/01_export.py --category "G. Ẩm thực"
uv run python src/kb_standardizer/01_export.py --category "C. Bảo tàng"
```

**Kết quả:** `output/kb_export_YYYYMMDD_HHMMSS.yaml`

**Việc cần làm sau bước 1:**
- Mở file YAML, kiểm tra `category_hint` đã phân loại đúng chưa
- Nếu `category_hint: "UNKNOWN"`, hãy gán thủ công đúng danh mục (A–L)
- Có thể xoá nodes không cần chuẩn hoá

---

### Bước 2: Làm giàu mô tả bằng GPT

```bash
# Xử lý tất cả nodes còn trống
uv run python src/kb_standardizer/02_enrich.py --input kb_export_20260612_120000.yaml

# Thử nghiệm với 5 nodes đầu tiên
uv run python src/kb_standardizer/02_enrich.py --input kb_export_20260612_120000.yaml --max 5
```

**Script sẽ:**
- Chỉ xử lý nodes có ít nhất 1 trường description đang trống
- Load đúng prompt theo `category_hint` (A–L)
- Gọi GPT sinh ra 4 trường: `description`, `description_vi`, `description_graph`, `description_graph_vi`
- In báo cáo token và chi phí khi kết thúc

**Kết quả:** `output/kb_enriched_YYYYMMDD_HHMMSS.yaml`

**Ví dụ báo cáo:**
```
====== TOKEN USAGE REPORT ======
Model             : gpt-5.4-mini
Nodes processed   : 42
Input tokens      : 18,540
Output tokens     : 6,210
Total tokens      : 24,750
Est. cost (USD)   : $0.042  (gpt-5.4-mini: $0.75/1M in, $4.50/1M out)
================================
```

**Việc cần làm sau bước 2:**
- Đọc kỹ file `kb_enriched_*.yaml`
- Kiểm tra chất lượng mô tả: đủ thực thể không? Có sai thực tế không?
- Chỉnh sửa thủ công nếu cần
- **CHỈ khi đã hài lòng**, mới chạy bước 3

---

### Bước 3: Nhập dữ liệu lên server (có double-check an toàn)

```bash
# Chạy thử (không cập nhật thật)
uv run python src/kb_standardizer/03_import.py --input kb_enriched_20260612_120000.yaml --dry-run

# Chạy thật
uv run python src/kb_standardizer/03_import.py --input kb_enriched_20260612_120000.yaml
```

**Cơ chế an toàn (double-check):**
1. Script fetch node từ server bằng `_id` trong YAML
2. So sánh `kb_id` trong YAML với `kb_id` trên server
3. Nếu **không khớp** → báo lỗi, **BỎ QUA** node đó, tiếp tục node tiếp theo
4. Nếu khớp → gọi `PUT /api/knowledge-base/<_id>` cập nhật

> ⛔ Không bao giờ cập nhật nhầm node vì cơ chế double-check này.

**Ví dụ báo cáo:**
```
====== IMPORT REPORT ======
File              : kb_enriched_20260612_120000.yaml
Dry Run           : NO
Total nodes       : 42
✅ Thành công      : 40
⏭️  Bỏ qua         : 1 (đã có đủ mô tả)
❌ Thất bại        : 1
  Chi tiết lỗi:
    - [bun_cha_sai] kb_id KHÔNG KHỚP: YAML='bun_cha_sai' vs Server='bun_cha'
===========================
```

---

## Cấu trúc file YAML

```yaml
metadata:
  exported_at: "2026-06-12T12:00:00"
  total_nodes: 42
  category_filter: ALL

nodes:
  - _id: "6643efb692ce01d8ab609abc"     # MongoDB ObjectId — KHÔNG sửa
    kb_id: "bun_cha"                     # Slug — để verify
    name: "Bun Cha"
    name_vi: "Bún chả"
    type: "concept"
    category_hint: "G. Ẩm thực Hà Nội"  # Gợi ý chọn đúng prompt
    description: ""                      # GPT sẽ điền (Dạng 1 EN)
    description_vi: ""                   # GPT sẽ điền (Dạng 1 VI)
    description_graph: ""               # GPT sẽ điền (Dạng 2 EN — S-P-O)
    description_graph_vi: ""            # GPT sẽ điền (Dạng 2 VI — S-P-O)
    visual_cues: ""
    tags: []
```

---

## 12 Danh mục và số thực thể

| Ký hiệu | Danh mục | Số thực thể |
|---|---|---|
| A | Di tích lịch sử - Văn hoá | 10 |
| B | Hồ - Công viên - Cảnh quan | 8 |
| C | Bảo tàng | 9 |
| D | Nghệ thuật biểu diễn | 10 |
| E | Lễ hội - Sự kiện | 10 |
| F | Làng nghề truyền thống | 10 |
| G | Ẩm thực Hà Nội | 10 |
| H | Hoạt động du lịch & Giải trí | 8 |
| I | Thiên nhiên & Ngoại thành | 8 |
| J | Người dân & Văn hoá sống | 9 |
| K | Bốn mùa Hà Nội | 8 |
| L | Video đặc biệt | 8 |

---

## Hai dạng mô tả

### Dạng 1 — `description` / `description_vi` (Văn xuôi du lịch)
- Văn phong: hướng dẫn viên du lịch chuyên nghiệp
- Mục tiêu: hấp dẫn, súc tích, truyền cảm hứng
- Sử dụng: hiển thị trong app, chatbot du lịch

### Dạng 2 — `description_graph` / `description_graph_vi` (S-P-O cho Knowledge Graph)
- Văn phong: chuỗi câu Subject-Predicate-Object
- Mục tiêu: phù hợp embedding vào Knowledge Graph / GraphRAG
- Sử dụng: đồ thị tri thức, retrieval-augmented generation
- Ví dụ: `"Bún chả [có thành phần chính] bún rối và chả lợn nướng than hoa. Bún chả [ăn kèm] nước mắm pha chua ngọt."`

---

## Bảng giá (gpt-5.4-mini)

| Loại token | Giá |
|---|---|
| Input (prompt) | $0.75 / 1M tokens |
| Cached input | $0.075 / 1M tokens |
| Output (completion) | $4.50 / 1M tokens |

Ước tính: ~100 nodes × 300 tokens output = 30K tokens output ≈ **$0.135**

---

## Cấu trúc thư mục

```
tools/kb_standardizer/
├── pyproject.toml          # uv project manifest
├── .python-version         # Python 3.11
├── .env.example            # Mẫu biến môi trường
├── .env                    # [IGNORED] Thông tin thật
├── .gitignore
├── README.md               # Tài liệu này
├── src/
│   └── kb_standardizer/
│       ├── __init__.py
│       ├── 01_export.py    # Kéo dữ liệu về YAML
│       ├── 02_enrich.py    # GPT làm giàu mô tả
│       └── 03_import.py    # Đẩy lên server
├── prompts/                # 12 file prompt theo danh mục
│   ├── A_di_tich_lich_su.md
│   ├── B_ho_cong_vien.md
│   ├── C_bao_tang.md
│   ├── D_nghe_thuat_bieu_dien.md
│   ├── E_le_hoi_su_kien.md
│   ├── F_lang_nghe_truyen_thong.md
│   ├── G_am_thuc.md
│   ├── H_hoat_dong_du_lich.md
│   ├── I_thien_nhien_ngoai_thanh.md
│   ├── J_nguoi_dan_van_hoa_song.md
│   ├── K_bon_mua_ha_noi.md
│   └── L_video_dac_biet.md
└── output/                 # File YAML (git-ignored)
    └── .gitignore
```
