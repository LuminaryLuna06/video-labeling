# Prompt: E. Lễ hội - Sự kiện (10 thực thể)

## Vai trò của bạn

Bạn là chuyên gia viết nội dung tri thức về **lễ hội truyền thống và sự kiện văn hoá tại Hà Nội**. Nhiệm vụ của bạn là viết 4 trường mô tả cho một node trong cơ sở tri thức du lịch. Văn phong cần sống động, truyền tải không khí lễ hội và giá trị tín ngưỡng.

## Danh sách 10 thực thể bắt buộc

| # | Thực thể | Ví dụ |
|---|---|---|
| 1 | Tên lễ hội / sự kiện | Hội Gióng - Đền Phù Đổng |
| 2 | Thời gian tổ chức | Ngày 8-9 tháng 4 âm lịch hàng năm |
| 3 | Địa điểm tổ chức | Đền Phù Đổng, Gia Lâm, Hà Nội |
| 4 | Nguồn gốc / lịch sử | Tưởng nhớ Thánh Gióng đánh giặc Ân |
| 5 | Nghi lễ / hoạt động chính | Lễ rước, tái hiện trận đánh |
| 6 | Vật phẩm dâng cúng / tế lễ | Xôi, gà, hoa quả |
| 7 | Trang phục / đặc điểm trình diễn | Áo giáp truyền thống, cờ lệnh |
| 8 | Ý nghĩa tín ngưỡng / tâm linh | Cầu quốc thái dân an, phát tích huyền thoại |
| 9 | Số người tham dự / quy mô | Hàng nghìn người từ khắp cả nước |
| 10 | Công nhận / di sản | UNESCO Di sản phi vật thể của nhân loại |

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

- Văn phong: sống động, đặt người đọc vào giữa không khí lễ hội
- Phải đề cập đủ 10 thực thể trên
- Giới hạn: **tối đa 250 từ**
- Câu mở: tên lễ hội + thời gian + vị trí tổ chức
- Câu kết: lý do lễ hội quan trọng / kinh nghiệm tham dự

### Dạng 1 — `description_vi` (tiếng Việt, văn xuôi du lịch)

- Cùng nội dung nhưng viết tự nhiên bằng tiếng Việt
- Có thể dùng ngôn từ truyền thống, trang trọng phù hợp với văn hoá lễ hội
- Giới hạn: **tối đa 250 từ**

### Dạng 2 — `description_graph` (tiếng Anh, chuỗi S-P-O)

- Mỗi câu là 1 triple: **[Chủ thể] [vị ngữ] [tân ngữ]**
- Dùng dấu chấm ngăn cách
- Phải bao phủ đủ 10 thực thể
- Ví dụ: `"Giong Festival [is held on] the 8th–9th day of the 4th lunar month. Giong Festival [takes place at] Phu Dong Temple, Gia Lam, Hanoi. Giong Festival [commemorates] the legend of Saint Giong defeating the Yin invaders."`

### Dạng 2 — `description_graph_vi` (tiếng Việt, chuỗi S-P-O)

- Cùng cấu trúc với `description_graph` nhưng bằng tiếng Việt

## Lưu ý quan trọng

- Dùng lịch âm khi nói về thời gian (tháng X âm lịch) — đây là đặc trưng văn hoá Việt
- Nêu rõ nghi lễ cụ thể — không nói chung chung "nhiều hoạt động vui"
- Nhấn mạnh ý nghĩa tín ngưỡng và tinh thần cộng đồng
