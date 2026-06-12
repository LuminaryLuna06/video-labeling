# Prompt: K. Bốn mùa Hà Nội (8 thực thể)

## Vai trò của bạn

Bạn là chuyên gia viết nội dung tri thức về **đặc trưng khí hậu và sinh hoạt theo từng mùa tại Hà Nội**. Nhiệm vụ của bạn là viết 4 trường mô tả cho một node trong cơ sở tri thức du lịch. Văn phong cần thơ mộng, gợi cảm xúc và hữu ích cho du khách khi lên kế hoạch.

## Danh sách 8 thực thể bắt buộc

| # | Thực thể | Ví dụ |
|---|---|---|
| 1 | Tên mùa | Mùa thu Hà Nội / Mùa đông / Mùa hè / Mùa xuân |
| 2 | Tháng / thời điểm trong năm | Tháng 9–11 (mùa thu) |
| 3 | Đặc điểm khí hậu | Mát mẻ 20–25°C, trời xanh cao, gió heo may |
| 4 | Loài hoa / cây đặc trưng mùa | Cúc hoạ mi, hoa sữa, hoa ban |
| 5 | Ẩm thực đặc trưng của mùa | Cốm xanh Vòng, chả cá Lã Vọng, bánh cốm |
| 6 | Hoạt động / lối sống mùa đó | Đạp xe buổi sáng, ăn kem Tràng Tiền tối hè |
| 7 | Cảnh đẹp / địa điểm nổi bật mùa | Đường Phan Đình Phùng rụng lá, Hồ Tây sương mù |
| 8 | Cảm xúc văn hoá / tinh thần | Mùa thu Hà Nội gắn với thơ, nhạc và nỗi nhớ |

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

- Văn phong: thơ mộng, gợi hình ảnh, mang cảm xúc rõ rệt — như bài viết trong tạp chí du lịch cao cấp
- Phải đề cập đủ 8 thực thể trên
- Giới hạn: **tối đa 250 từ**
- Câu mở: tên mùa + cảm xúc chủ đạo + thời điểm
- Câu kết: lời mời đến Hà Nội vào mùa đó

### Dạng 1 — `description_vi` (tiếng Việt, văn xuôi du lịch)

- Cùng nội dung nhưng viết tự nhiên bằng tiếng Việt
- Có thể dùng hình ảnh thơ, từ ngữ cảm xúc như người Hà Nội thường nói về mùa của mình
- Giới hạn: **tối đa 250 từ**

### Dạng 2 — `description_graph` (tiếng Anh, chuỗi S-P-O)

- Mỗi câu là 1 triple: **[Chủ thể] [vị ngữ] [tân ngữ]**
- Dùng dấu chấm ngăn cách
- Phải bao phủ đủ 8 thực thể
- Ví dụ: `"Hanoi Autumn [spans from] September to November. Hanoi Autumn [has temperatures of] 20–25°C with clear blue skies and northeast winds. Hanoi Autumn [is associated with] white chrysanthemum flowers and milk flowers. Hanoi Autumn [features seasonal foods including] green rice (com xanh) and steamed rice cakes."`

### Dạng 2 — `description_graph_vi` (tiếng Việt, chuỗi S-P-O)

- Cùng cấu trúc với `description_graph` nhưng bằng tiếng Việt

## Lưu ý quan trọng

- Nêu nhiệt độ / đặc điểm thời tiết cụ thể — du khách cần biết mặc gì, mang gì
- Tên loài hoa, món ăn mùa PHẢI cụ thể theo tên thực — đây là thông tin có giá trị cao
- Cảm xúc văn hoá là yếu tố phân biệt Hà Nội với các nơi khác — phải nêu rõ
