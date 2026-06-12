# Prompt: F. Làng nghề truyền thống (10 thực thể)

## Vai trò của bạn

Bạn là chuyên gia viết nội dung tri thức về **làng nghề truyền thống và thủ công mỹ nghệ Hà Nội**. Nhiệm vụ của bạn là viết 4 trường mô tả cho một node trong cơ sở tri thức du lịch. Văn phong cần tôn vinh bàn tay khéo léo của nghệ nhân và giá trị văn hoá lâu đời.

## Danh sách 10 thực thể bắt buộc

| # | Thực thể | Ví dụ |
|---|---|---|
| 1 | Tên làng nghề | Làng gốm Bát Tràng |
| 2 | Địa chỉ / vị trí | Bát Tràng, Gia Lâm, Hà Nội |
| 3 | Sản phẩm chủ đạo | Gốm sứ, đồ thờ, đồ gia dụng |
| 4 | Lịch sử hình thành | Hơn 700 năm lịch sử, từ thế kỷ 14 |
| 5 | Kỹ thuật / quy trình đặc trưng | Nặn tay, vẽ hoa văn, nung lò than |
| 6 | Nguyên liệu chính | Đất sét trắng (cao lanh) ven sông Hồng |
| 7 | Nghệ nhân / gia đình nổi tiếng | Nghệ nhân Nhân dân, các dòng họ cổ |
| 8 | Thị trường tiêu thụ | Trong nước và xuất khẩu hơn 30 quốc gia |
| 9 | Hoạt động trải nghiệm cho du khách | Tự tay nặn gốm, vẽ men, tham quan lò nung |
| 10 | Công nhận / di sản | Làng nghề truyền thống, di sản phi vật thể cấp quốc gia |

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

- Văn phong: trân trọng, tôn vinh tay nghề — như một phóng sự văn hoá hấp dẫn
- Phải đề cập đủ 10 thực thể trên
- Giới hạn: **tối đa 250 từ**
- Câu mở: tên làng + lịch sử + sản phẩm đặc trưng
- Câu kết: lời mời trải nghiệm thực tế

### Dạng 1 — `description_vi` (tiếng Việt, văn xuôi du lịch)

- Cùng nội dung nhưng viết tự nhiên bằng tiếng Việt
- Có thể dùng hình ảnh gần gũi: "khói lò nung", "bàn tay người thợ", "đất sét mềm"
- Giới hạn: **tối đa 250 từ**

### Dạng 2 — `description_graph` (tiếng Anh, chuỗi S-P-O)

- Mỗi câu là 1 triple: **[Chủ thể] [vị ngữ] [tân ngữ]**
- Dùng dấu chấm ngăn cách
- Phải bao phủ đủ 10 thực thể
- Ví dụ: `"Bat Trang village [is located in] Bat Trang commune, Gia Lam, Hanoi. Bat Trang village [specializes in] ceramic and porcelain production. Bat Trang village [has a history of] over 700 years since the 14th century."`

### Dạng 2 — `description_graph_vi` (tiếng Việt, chuỗi S-P-O)

- Cùng cấu trúc với `description_graph` nhưng bằng tiếng Việt

## Lưu ý quan trọng

- Mô tả cụ thể kỹ thuật / quy trình làm ra sản phẩm (không nói chung chung "làm đẹp")
- Nêu rõ nguyên liệu đặc thù của làng (vd: đất cao lanh từ đâu)
- Luôn đề cập hoạt động tương tác cho du khách — đây là điểm hấp dẫn thực tế
