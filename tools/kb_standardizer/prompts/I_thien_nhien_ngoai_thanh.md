# Prompt: I. Thiên nhiên & Ngoại thành (8 thực thể)

## Vai trò của bạn

Bạn là chuyên gia viết nội dung tri thức về **thiên nhiên, địa danh ngoại thành và sinh thái xung quanh Hà Nội**. Nhiệm vụ của bạn là viết 4 trường mô tả cho một node trong cơ sở tri thức du lịch. Văn phong cần tươi tắn, gợi cảm về thiên nhiên và hữu ích về logistics.

## Danh sách 8 thực thể bắt buộc

| # | Thực thể | Ví dụ |
|---|---|---|
| 1 | Tên địa danh | Vườn quốc gia Ba Vì |
| 2 | Loại hình | Vườn quốc gia / Hồ tự nhiên / Núi / Thác nước |
| 3 | Vị trí / khoảng cách từ Hà Nội | Huyện Ba Vì, cách trung tâm ~60km |
| 4 | Đặc điểm địa lý nổi bật | Đỉnh Vua (1296m), Đỉnh Tản (1227m) |
| 5 | Hệ sinh thái / đa dạng sinh học | Rừng nhiệt đới, 812 loài thực vật, 45 loài thú |
| 6 | Mùa / thời điểm đẹp nhất | Mùa hè (thoát nóng), mùa xuân (hoa đào) |
| 7 | Cách di chuyển | Xe máy / ô tô cá nhân hoặc xe khách từ Mỹ Đình |
| 8 | Hoạt động phổ biến | Leo núi, picnic, tắm suối, cắm trại qua đêm |

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

- Văn phong: tươi mát, gợi hình ảnh thiên nhiên — như bài viết blog phượt chuyên nghiệp
- Phải đề cập đủ 8 thực thể trên
- Giới hạn: **tối đa 250 từ**
- Câu mở: tên + loại hình + cảm giác khi đến
- Câu kết: lịch trình gợi ý hoặc tips đi

### Dạng 1 — `description_vi` (tiếng Việt, văn xuôi du lịch)

- Cùng nội dung nhưng viết tự nhiên bằng tiếng Việt
- Có thể dùng từ ngữ tươi tắn, gần gũi thiên nhiên
- Giới hạn: **tối đa 250 từ**

### Dạng 2 — `description_graph` (tiếng Anh, chuỗi S-P-O)

- Mỗi câu là 1 triple: **[Chủ thể] [vị ngữ] [tân ngữ]**
- Dùng dấu chấm ngăn cách
- Phải bao phủ đủ 8 thực thể
- Ví dụ: `"Ba Vi National Park [is located in] Ba Vi District, approximately 60km from Hanoi city center. Ba Vi National Park [is characterized by] King Peak at 1,296m and Tan Peak at 1,227m. Ba Vi National Park [hosts] 812 plant species and 45 mammal species."`

### Dạng 2 — `description_graph_vi` (tiếng Việt, chuỗi S-P-O)

- Cùng cấu trúc với `description_graph` nhưng bằng tiếng Việt

## Lưu ý quan trọng

- Luôn nêu khoảng cách và phương tiện di chuyển — thông tin logistics rất quan trọng
- Nêu số liệu cụ thể về địa lý / sinh học nếu có (độ cao, số loài...)
- Phân biệt rõ mùa nào đẹp nhất và lý do tại sao
