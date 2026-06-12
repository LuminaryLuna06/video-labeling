# KB Standardizer — Bộ công cụ chuẩn hoá Knowledge Base

Bộ công cụ 3 bước để chuẩn hoá và làm giàu nội dung các node trong Knowledge Base du lịch Hà Nội. 
Toàn bộ quá trình hỗ trợ xử lý song song, an toàn với Rate Limit của OpenAI, và có cơ chế kiểm duyệt chặt chẽ để chống Hallucination (ảo giác AI).

## Quy trình làm việc & Kiến trúc

```
[01_export.py] → YAML nháp 
   ↓
[02_enrich.py (Async, Rate-Limit Safe)] → YAML đã làm giàu (Enriched)
   ↓
[Con người thẩm định / Script sửa Hallucination] → Cập nhật file YAML
   ↓
[03_import.py] → Server Database
```

**Tại sao 3 bước?** Để con người kiểm soát hoàn toàn — GPT chỉ là công cụ trợ lý, không tự động cập nhật lên server, tránh việc AI đưa sai sự kiện lịch sử lên hệ thống.

---

## Các tính năng & Kiến trúc kỹ thuật nổi bật

### 1. Frontend & Giao diện quản lý
- Tích hợp 2 trường mới: `description_graph` và `description_graph_vi`.
- Các trường này được sử dụng riêng để lưu trữ chuỗi thông tin S-P-O (Subject-Predicate-Object) phục vụ cho Knowledge Graph Embedding.
- UI Dialog được cập nhật thêm CSS badge `graph-badge` màu tím đặc trưng để phân biệt các trường mô tả dùng cho Graph so với văn xuôi thông thường.

### 2. Xử lý song song an toàn (Async & Rate Limiting) trong `02_enrich.py`
- **Asyncio + Semaphore:** Giới hạn xử lý song song (mặc định 5 workers) thay vì chạy tuần tự, giúp giảm thời gian từ vài chục phút xuống chỉ còn khoảng ~2 phút cho ~100 nodes.
- **Throttle (750ms/request):** Giữ tốc độ gọi API an toàn (< 500 RPM và < 200,000 TPM) tuân thủ giới hạn OpenAI Tier 1 cho model `gpt-5.4-mini`.
- **Exponential Backoff:** Tự động retry tối đa 5 lần với độ trễ tăng dần nếu gặp lỗi `429 RateLimitError`.
- **Ghi file 1 lần duy nhất:** Tránh lock file bằng cách lưu mọi kết quả vào memory và chỉ xuất file YAML một lần khi toàn bộ tiến trình kết thúc.
- **Đếm Token chính xác:** Đọc `response.usage` để báo cáo chi phí (input/output tokens) thực tế thay vì ước lượng.

### 3. Quy trình chống Hallucination (Kiểm định sự thật)
- Sau khi AI sinh nội dung, con người cần đọc đối chiếu các thông tin sự kiện, niên đại. 
- *Ví dụ thực tế:* AI có thể nhầm thời điểm khởi công Hầm T1, nhầm Sân Đại Thành của Văn Miếu sang Phủ Tây Hồ, hoặc giải thích sai nguồn gốc tên hồ Trúc Bạch.
- Nếu phát hiện lỗi: Viết một đoạn script Python nhỏ để parse YAML, `replace` chuỗi bị sai, rồi lưu đè lại (hoặc tự sửa bằng tay). Sau đó mới chạy bước Import.

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
```

**Kết quả:** `output/kb_export_YYYYMMDD_HHMMSS.yaml`

**Việc cần làm sau bước 1:**
- Mở file YAML, kiểm tra `category_hint` đã phân loại đúng chưa.
- Nếu `category_hint: "UNKNOWN"`, hãy gán thủ công đúng danh mục (A–L).
- Có thể xoá nodes không cần chuẩn hoá.

---

### Bước 2: Làm giàu mô tả bằng GPT (Chạy Song Song)

```bash
# Xử lý tất cả nodes còn trống (tự chọn file export mới nhất)
uv run python src/kb_standardizer/02_enrich.py

# Thử nghiệm với 5 nodes đầu tiên, chạy 5 workers song song
uv run python src/kb_standardizer/02_enrich.py --max 5 --workers 5
```

**Kết quả:** `output/kb_enriched_YYYYMMDD_HHMMSS.yaml`

**Ví dụ báo cáo:**
```
====================================================
         ====== TOKEN USAGE REPORT ======
====================================================
   Model             : gpt-5.4-mini
   Workers parallel  : 5
   Elapsed time      : 118.6s (2.0 phút)
   Throughput        : 48.6 nodes/phút
   ------------------------------------------------
   Nodes processed   : 96
   Input tokens      :    291,696
   Output tokens     :     70,111
   TOTAL COST (USD)  : $  0.5343
====================================================
```

**Việc cần làm sau bước 2:**
- Đọc kỹ file `kb_enriched_*.yaml` và kiểm tra chống hallucination (ảo giác).
- Chỉnh sửa thủ công hoặc dùng script để tự động thay thế văn bản nếu phát hiện sai lệch sự kiện lịch sử/niên đại.
- **CHỈ khi đã hài lòng**, mới chạy bước 3.

---

### Bước 3: Nhập dữ liệu lên server (có double-check an toàn)

```bash
# Chạy thử (không cập nhật thật)
uv run python src/kb_standardizer/03_import.py --dry-run

# Chạy thật (tự động pick file enriched mới nhất)
uv run python src/kb_standardizer/03_import.py
```

**Cơ chế an toàn (double-check):**
1. Script fetch node từ server bằng `_id` trong YAML.
2. So sánh `kb_id` trong YAML với `kb_id` trên server.
3. Nếu **không khớp** → báo lỗi, **BỎ QUA** node đó, tiếp tục node tiếp theo.
4. Nếu khớp → gọi `PUT /api/knowledge-base/<_id>` cập nhật.

---

## 12 Danh mục và số lượng thực thể cần viết

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
- **Văn phong:** Hướng dẫn viên du lịch chuyên nghiệp, hấp dẫn, súc tích (khoảng 250 từ).
- **Mục tiêu:** Truyền cảm hứng, hiển thị trực quan trong App / Chatbot.

### Dạng 2 — `description_graph` / `description_graph_vi` (S-P-O cho Knowledge Graph)
- **Văn phong:** Tách bạch thành chuỗi câu cấu trúc Subject-Predicate-Object.
- **Mục tiêu:** Tối ưu hóa embedding, nạp vào Đồ thị tri thức (Knowledge Graph / GraphRAG).
- **Ví dụ:** `"Bún chả [có thành phần chính] bún rối và chả lợn nướng than hoa. Bún chả [ăn kèm] nước mắm pha chua ngọt."`

---

## Bảng giá (gpt-5.4-mini)

| Loại token | Giá |
|---|---|
| Input (prompt) | $0.75 / 1M tokens |
| Output (completion) | $4.50 / 1M tokens |

*Lưu ý: API parameters của model `gpt-5.4-mini` yêu cầu dùng `max_completion_tokens` thay vì `max_tokens`.*

---

## Cấu trúc thư mục

```
tools/kb_standardizer/
├── pyproject.toml          # uv project manifest
├── .python-version         # Python 3.11
├── README.md               # Tài liệu tổng quan
├── fix_hallucinations.py   # [Mới] Script tự động vá lỗi hallucination sự kiện lịch sử 
├── src/
│   └── kb_standardizer/
│       ├── 01_export.py    # Kéo dữ liệu về YAML
│       ├── 02_enrich.py    # Async GPT gọi API bổ sung mô tả
│       └── 03_import.py    # Đẩy lên server API
├── prompts/                # Các file prompt base + 12 danh mục (A-L)
└── output/                 # Folder chứa file YAML nháp và YAML đã enrich
```
