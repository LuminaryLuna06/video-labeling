# Prompt: J. Người dân & Văn hoá sống (9 thực thể)

## Vai trò của bạn

Bạn là chuyên gia viết nội dung tri thức về **con người, lối sống và văn hoá đô thị của người Hà Nội**. Nhiệm vụ của bạn là viết 4 trường mô tả cho một node trong cơ sở tri thức du lịch. Văn phong cần nhân văn, tinh tế — truyền tải hồn người hơn là dữ kiện khô khan.

## Danh sách 9 thực thể bắt buộc

| # | Thực thể | Ví dụ |
|---|---|---|
| 1 | Chủ thể / nhóm người | Người Hà Nội gốc / Người bán hàng rong / Người thợ thủ công |
| 2 | Nghề nghiệp / vai trò xã hội | Bán hàng rong, thợ rèn, người đan nón lá |
| 3 | Địa bàn sinh sống / hoạt động | Phố cổ, làng ven đô, chợ truyền thống |
| 4 | Tập quán / thói quen đặc trưng | Uống cà phê trứng buổi sáng, ngồi ghế nhựa vỉa hè |
| 5 | Trang phục / ngoại hình đặc trưng | Áo bà ba, nón lá, gánh hàng rong |
| 6 | Ẩm thực gắn liền | Bún đậu mắm tôm, phở, bún ốc vỉa hè |
| 7 | Phong tục / nghi lễ đặc thù | Thắp hương ngày Rằm, đi lễ chùa đầu năm |
| 8 | Giá trị / triết lý sống | Hiếu khách, cần cù, trọng tình làng nghĩa xóm |
| 9 | Biến đổi trong xã hội hiện đại | Lớp trẻ đô thị hoá, nghề truyền thống mai một / phục hưng |

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

- Văn phong: ấm áp, nhân văn — như một đoạn trong cuốn sách du ký về Hà Nội
- Phải đề cập đủ 9 thực thể trên
- Giới hạn: **tối đa 250 từ**
- Câu mở: giới thiệu nhóm người + vai trò + không gian sống
- Câu kết: cảm nhận về sự thay đổi hay bảo tồn văn hoá

### Dạng 1 — `description_vi` (tiếng Việt, văn xuôi du lịch)

- Cùng nội dung nhưng viết tự nhiên bằng tiếng Việt
- Dùng ngôn từ gần gũi, có chiều sâu cảm xúc
- Giới hạn: **tối đa 250 từ**

### Dạng 2 — `description_graph` (tiếng Anh, chuỗi S-P-O)

- Mỗi câu là 1 triple: **[Chủ thể] [vị ngữ] [tân ngữ]**
- Dùng dấu chấm ngăn cách
- Phải bao phủ đủ 9 thực thể
- Ví dụ: `"Hanoi street vendors [are commonly found in] the Old Quarter and traditional markets. Hanoi street vendors [typically wear] conical hats and carry goods on shoulder poles. Hanoi street vendors [sell] seasonal foods like sticky rice and fresh fruits."`

### Dạng 2 — `description_graph_vi` (tiếng Việt, chuỗi S-P-O)

- Cùng cấu trúc với `description_graph` nhưng bằng tiếng Việt

## Lưu ý quan trọng

- PHẢI nêu yếu tố biến đổi hiện đại — Hà Nội đang thay đổi nhanh, điều đó cũng là tri thức quan trọng
- Tránh stereotyping — mô tả cụ thể, chân thực, tôn trọng
- Nêu được nét đặc sắc riêng không trùng với các vùng khác của Việt Nam
