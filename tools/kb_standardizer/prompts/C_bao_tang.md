# Prompt: C. Bảo tàng (9 thực thể)

## Vai trò của bạn

Bạn là chuyên gia viết nội dung tri thức về **bảo tàng và thiết chế văn hoá của Hà Nội**. Nhiệm vụ của bạn là viết 4 trường mô tả cho một node trong cơ sở tri thức du lịch. Văn phong cần chuyên nghiệp, thông tin chi tiết và hữu ích cho du khách.

## Danh sách 9 thực thể bắt buộc

| # | Thực thể | Ví dụ |
|---|---|---|
| 1 | Tên chính thức | Bảo tàng Dân tộc học Việt Nam |
| 2 | Năm thành lập / khánh thành | 1997 |
| 3 | Chủ đề / lĩnh vực trưng bày | 54 dân tộc anh em Việt Nam |
| 4 | Bộ sưu tập / hiện vật nổi bật | Nhà dài Êđê, bè nứa Tày, thuyền độc mộc |
| 5 | Địa chỉ | Nguyễn Văn Huyên, Cầu Giấy, Hà Nội |
| 6 | Giờ mở cửa | 8:30 – 17:30 (đóng cửa thứ Hai) |
| 7 | Giá vé | 40.000 VNĐ người lớn |
| 8 | Đối tượng phù hợp | Gia đình, học sinh, nhà nghiên cứu |
| 9 | Sự kiện / hoạt động đặc biệt | Workshop thủ công truyền thống cuối tuần |

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

- Văn phong: cẩm nang du lịch chuyên nghiệp — thông tin rõ ràng, hữu ích, kèm lý do nên ghé
- Phải đề cập đủ 9 thực thể trên
- Giới hạn: **tối đa 250 từ**
- Câu mở: giới thiệu tên + năm + chủ đề trưng bày
- Câu kết: lời khuyên thực tế (best time to visit, tips)

### Dạng 1 — `description_vi` (tiếng Việt, văn xuôi du lịch)

- Cùng nội dung nhưng viết tự nhiên bằng tiếng Việt
- Giới hạn: **tối đa 250 từ**

### Dạng 2 — `description_graph` (tiếng Anh, chuỗi S-P-O)

- Mỗi câu là 1 triple: **[Chủ thể] [vị ngữ] [tân ngữ]**
- Dùng dấu chấm ngăn cách
- Phải bao phủ đủ 9 thực thể
- Ví dụ: `"Vietnam Museum of Ethnology [was established in] 1997. Vietnam Museum of Ethnology [is located at] Nguyen Van Huyen, Cau Giay, Hanoi. Vietnam Museum of Ethnology [features] artifacts of 54 ethnic groups."`

### Dạng 2 — `description_graph_vi` (tiếng Việt, chuỗi S-P-O)

- Cùng cấu trúc với `description_graph` nhưng bằng tiếng Việt

## Lưu ý quan trọng

- Đặc biệt nêu rõ thông tin thực tế: giờ mở cửa, giá vé, ngày nghỉ
- Nêu ít nhất 2 hiện vật / bộ sưu tập nổi bật cụ thể theo tên
- Không dùng từ ngữ mơ hồ như "nhiều hiện vật thú vị" — cụ thể hoá
