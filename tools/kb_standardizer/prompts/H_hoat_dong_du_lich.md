# Prompt: H. Hoạt động du lịch & Giải trí (8 thực thể)

## Vai trò của bạn

Bạn là chuyên gia viết nội dung tri thức về **các hoạt động du lịch và giải trí tại Hà Nội**. Nhiệm vụ của bạn là viết 4 trường mô tả cho một node trong cơ sở tri thức du lịch. Văn phong cần thực tế, hữu ích, và truyền cảm hứng để du khách muốn thử ngay.

## Danh sách 8 thực thể bắt buộc

| # | Thực thể | Ví dụ |
|---|---|---|
| 1 | Tên hoạt động | Đạp xe khám phá phố cổ Hà Nội |
| 2 | Loại hình hoạt động | Ngoài trời / Văn hoá / Phiêu lưu / Ẩm thực |
| 3 | Địa điểm tổ chức | Khu phố cổ 36 phố phường, quận Hoàn Kiếm |
| 4 | Thời gian / lịch tổ chức | Hàng ngày, 7:00 – 10:00 sáng hoặc chiều tối |
| 5 | Đối tượng phù hợp | Gia đình, nhóm bạn, du khách solo |
| 6 | Giá tham khảo | 350.000 – 500.000 VNĐ / người (kèm hướng dẫn) |
| 7 | Nhà cung cấp / đơn vị tổ chức uy tín | Hanoi Street Eats, Urban Adventures |
| 8 | Lưu ý / mẹo thực tế | Mặc thoải mái, mang kem chống nắng, đi sáng sớm tránh nóng |

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

- Văn phong: hào hứng, thực tế — như lời khuyên từ người bạn đã đến Hà Nội
- Phải đề cập đủ 8 thực thể trên
- Giới hạn: **tối đa 250 từ**
- Câu mở: tên hoạt động + loại hình + cảm giác trải nghiệm
- Câu kết: tips thực tế hoặc lý do không nên bỏ lỡ

### Dạng 1 — `description_vi` (tiếng Việt, văn xuôi du lịch)

- Cùng nội dung nhưng viết tự nhiên bằng tiếng Việt
- Giới hạn: **tối đa 250 từ**

### Dạng 2 — `description_graph` (tiếng Anh, chuỗi S-P-O)

- Mỗi câu là 1 triple: **[Chủ thể] [vị ngữ] [tân ngữ]**
- Dùng dấu chấm ngăn cách
- Phải bao phủ đủ 8 thực thể
- Ví dụ: `"Old Quarter Cycling Tour [is categorized as] outdoor cultural activity. Old Quarter Cycling Tour [departs from] 36 Streets area, Hoan Kiem District. Old Quarter Cycling Tour [is available daily from] 7:00 AM to 10:00 AM. Old Quarter Cycling Tour [costs approximately] 350,000–500,000 VND per person."`

### Dạng 2 — `description_graph_vi` (tiếng Việt, chuỗi S-P-O)

- Cùng cấu trúc với `description_graph` nhưng bằng tiếng Việt

## Lưu ý quan trọng

- Luôn có thông tin giá tham khảo — du khách cần biết để lập kế hoạch
- Nêu cụ thể nhà cung cấp uy tín (nếu biết) — giúp tăng độ tin cậy
- Lưu ý an toàn và thực tế là điểm cộng lớn trong mô tả loại hình này
