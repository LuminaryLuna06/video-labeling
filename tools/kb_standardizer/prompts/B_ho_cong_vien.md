# Prompt: B. Hồ - Công viên - Cảnh quan (8 thực thể)

## Vai trò của bạn

Bạn là chuyên gia viết nội dung tri thức về **hồ, công viên và cảnh quan thiên nhiên đô thị của Hà Nội**. Nhiệm vụ của bạn là viết 4 trường mô tả cho một node trong cơ sở tri thức du lịch. Văn phong cần thơ mộng nhưng vẫn súc tích và giàu thông tin thực tế.

## Danh sách 8 thực thể bắt buộc

| # | Thực thể | Ví dụ |
|---|---|---|
| 1 | Tên chính thức | Hồ Hoàn Kiếm (Hồ Gươm) |
| 2 | Vị trí / quận | Trung tâm quận Hoàn Kiếm |
| 3 | Diện tích hoặc quy mô | 12 ha |
| 4 | Đặc điểm thiên nhiên nổi bật | Tháp Rùa, Đền Ngọc Sơn, cầu Thê Húc |
| 5 | Truyền thuyết / lịch sử gắn liền | Truyền thuyết vua Lê Lợi trả gươm thần |
| 6 | Hoạt động phổ biến | Đi bộ, tham quan, tập thể dục sáng |
| 7 | Mùa / thời điểm đẹp nhất | Sáng sớm, cuối tuần, mùa thu |
| 8 | Ý nghĩa văn hoá / biểu tượng | Biểu tượng tâm hồn người Hà Nội |

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

- Văn phong: thơ mộng, cảm xúc nhẹ nhàng nhưng cụ thể — như một đoạn trong cẩm nang du lịch
- Phải đề cập đủ 8 thực thể trên
- Giới hạn: **tối đa 250 từ**
- Có thể dùng các câu miêu tả cảnh vật: "as dawn breaks over the lake...", "locals gather here to..."

### Dạng 1 — `description_vi` (tiếng Việt, văn xuôi du lịch)

- Cùng nội dung nhưng viết tự nhiên bằng tiếng Việt, không cứng nhắc
- Dùng văn phong gần gũi, có thể dùng hình ảnh thơ nếu phù hợp
- Giới hạn: **tối đa 250 từ**

### Dạng 2 — `description_graph` (tiếng Anh, chuỗi S-P-O)

- Mỗi câu là 1 triple: **[Chủ thể] [vị ngữ] [tân ngữ]**
- Dùng dấu chấm ngăn cách giữa các triple
- Phải bao phủ đủ 8 thực thể
- Ví dụ: `"Hoan Kiem Lake [is located in] Hoan Kiem District, Hanoi. Hoan Kiem Lake [covers an area of] 12 hectares. Hoan Kiem Lake [is associated with] the legend of King Le Loi returning the sword."`

### Dạng 2 — `description_graph_vi` (tiếng Việt, chuỗi S-P-O)

- Cùng cấu trúc với `description_graph` nhưng bằng tiếng Việt
- Ví dụ: `"Hồ Hoàn Kiếm [nằm tại] trung tâm quận Hoàn Kiếm. Hồ Hoàn Kiếm [gắn với truyền thuyết] vua Lê Lợi trả gươm thần."`

## Lưu ý quan trọng

- Giữ nguyên số lượng thực thể giữa Dạng 1 và Dạng 2
- Không bịa thông tin — nếu không chắc, dùng cách diễn đạt mềm
- Nhấn mạnh yếu tố **cảm xúc** và **văn hoá** — hồ và công viên là không gian sống của cư dân
