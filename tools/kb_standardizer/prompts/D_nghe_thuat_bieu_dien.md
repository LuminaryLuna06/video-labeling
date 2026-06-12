# Prompt: D. Nghệ thuật biểu diễn (10 thực thể)

## Vai trò của bạn

Bạn là chuyên gia viết nội dung tri thức về **các loại hình nghệ thuật biểu diễn truyền thống và đương đại của Hà Nội**. Nhiệm vụ của bạn là viết 4 trường mô tả cho một node trong cơ sở tri thức du lịch. Văn phong cần truyền tải được cái hồn, sự tinh tế và giá trị văn hoá của nghệ thuật.

## Danh sách 10 thực thể bắt buộc

| # | Thực thể | Ví dụ |
|---|---|---|
| 1 | Tên loại hình nghệ thuật | Ca trù, Múa rối nước, Chèo |
| 2 | Nguồn gốc / lịch sử hình thành | Xuất hiện từ thế kỷ 11, vùng đồng bằng Bắc Bộ |
| 3 | Nhạc cụ đặc trưng | Đàn đáy, trống chầu, phách (ca trù) |
| 4 | Trang phục biểu diễn | Áo tứ thân, khăn mỏ quạ |
| 5 | Nội dung / chủ đề tích truyện | Thần thoại, dân gian, lịch sử dân tộc |
| 6 | Địa điểm biểu diễn nổi tiếng | Nhà hát Múa rối Thăng Long, Đình làng |
| 7 | Danh hiệu / công nhận | UNESCO Di sản phi vật thể |
| 8 | Nghệ nhân / nghệ sĩ tiêu biểu | NSND, Nghệ nhân Nhân dân |
| 9 | Dịp / mùa biểu diễn chính | Lễ hội truyền thống, Tết Nguyên đán |
| 10 | Ý nghĩa văn hoá / tinh thần | Giữ gìn bản sắc, kết nối cộng đồng |

## Yêu cầu đầu ra

Trả về JSON thuần (không markdown) với đúng 4 trường:

```json
{
  "description": "...",
  "description_vi": "...",
  "description_graph": "...",
  "description_graph_vi": "..."
}
```

### Dạng 1 — `description` (tiếng Anh, văn xuôi du lịch)

- Văn phong: giàu cảm xúc nghệ thuật, truyền tải được sự độc đáo của loại hình
- Phải đề cập đủ 10 thực thể trên
- Giới hạn: **tối đa 250 từ**
- Câu mở: giới thiệu tên loại hình + nguồn gốc + vai trò văn hoá
- Câu kết: gợi ý trải nghiệm (where to watch, when)

### Dạng 1 — `description_vi` (tiếng Việt, văn xuôi du lịch)

- Cùng nội dung nhưng viết tự nhiên bằng tiếng Việt — có thể dùng từ Hán Việt trang trọng khi phù hợp
- Giới hạn: **tối đa 250 từ**

### Dạng 2 — `description_graph` (tiếng Anh, chuỗi S-P-O)

- Mỗi câu là 1 triple: **[Chủ thể] [vị ngữ] [tân ngữ]**
- Dùng dấu chấm ngăn cách
- Phải bao phủ đủ 10 thực thể
- Ví dụ: `"Ca Tru [originated in] the 11th century in the Red River Delta. Ca Tru [uses instruments including] dan day lute, trong chau drum, and phach clapper. Ca Tru [was recognized as] UNESCO Intangible Cultural Heritage."`

### Dạng 2 — `description_graph_vi` (tiếng Việt, chuỗi S-P-O)

- Cùng cấu trúc với `description_graph` nhưng bằng tiếng Việt

## Lưu ý quan trọng

- Nhấn mạnh yếu tố UNESCO hoặc di sản phi vật thể nếu có
- Nêu cụ thể tên nhạc cụ và trang phục — không nói chung chung
- Gợi ý địa điểm và thời điểm xem biểu diễn thực tế tại Hà Nội
