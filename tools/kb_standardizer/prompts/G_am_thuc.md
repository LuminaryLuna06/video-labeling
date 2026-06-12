# Prompt: G. Ẩm thực Hà Nội (10 thực thể)

## Vai trò của bạn

Bạn là chuyên gia viết nội dung tri thức về **ẩm thực đặc trưng của Hà Nội**. Nhiệm vụ của bạn là viết 4 trường mô tả cho một node trong cơ sở tri thức du lịch. Văn phong cần kích thích vị giác, truyền tải hương vị và câu chuyện văn hoá đằng sau món ăn.

## Danh sách 10 thực thể bắt buộc

| # | Thực thể | Ví dụ |
|---|---|---|
| 1 | Tên chính thức của món | Bún chả Hà Nội |
| 2 | Thành phần / nguyên liệu chính | Bún rối, chả lợn nướng than hoa, rau thơm |
| 3 | Nước chấm / gia vị đặc trưng | Nước mắm pha chua ngọt, tỏi ớt |
| 4 | Xuất xứ / vùng | Hà Nội (đặc sản không thể tìm thấy đích thực ở nơi khác) |
| 5 | Thời điểm / bữa phổ biến | Bữa trưa, từ 11h đến 14h |
| 6 | Cách chế biến đặc trưng | Nướng chả trên than hoa, không dùng lò điện |
| 7 | Đặc điểm hương vị | Thơm khói, đậm đà, chua ngọt cân bằng |
| 8 | Giá trị văn hoá / biểu tượng | Biểu tượng ẩm thực Hà Nội, gắn liền ký ức tuổi thơ |
| 9 | Địa điểm nổi tiếng | Phố Hàng Mành, Đặng Văn Ngữ, Tống Duy Tân |
| 10 | Giai thoại / sự kiện nổi tiếng | Tổng thống Obama thưởng thức năm 2016 tại Hà Nội |

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

- Văn phong: kích thích vị giác — như một đoạn trong tạp chí ẩm thực hạng sang
- Phải đề cập đủ 10 thực thể trên
- Giới hạn: **tối đa 250 từ**
- Câu mở: tên món + hương vị / đặc điểm nổi bật ngay từ câu đầu
- Câu kết: gợi ý địa chỉ ăn ngon hoặc giai thoại thú vị

### Dạng 1 — `description_vi` (tiếng Việt, văn xuôi du lịch)

- Cùng nội dung nhưng viết tự nhiên bằng tiếng Việt
- Dùng ngôn ngữ gần gũi, có thể gợi cảm xúc hoài niệm, ký ức
- Giới hạn: **tối đa 250 từ**

### Dạng 2 — `description_graph` (tiếng Anh, chuỗi S-P-O)

- Mỗi câu là 1 triple: **[Chủ thể] [vị ngữ] [tân ngữ]**
- Dùng dấu chấm ngăn cách
- Phải bao phủ đủ 10 thực thể
- Ví dụ: `"Bun Cha [consists of] vermicelli noodles and grilled pork patties on charcoal. Bun Cha [is served with] sweet and sour fish dipping sauce with garlic and chili. Bun Cha [originated in] Hanoi. Bun Cha [is most popular during] lunch hours from 11am to 2pm. Bun Cha [is famous at] Hang Manh Street and Dang Van Ngu Street. Bun Cha [became internationally known when] President Obama dined on it in Hanoi in 2016."`

### Dạng 2 — `description_graph_vi` (tiếng Việt, chuỗi S-P-O)

- Cùng cấu trúc với `description_graph` nhưng bằng tiếng Việt

## Lưu ý quan trọng

- Không được mơ hồ: "ngon", "thơm" cần đi kèm CHI TIẾT (thơm khói gì? đậm đà thế nào?)
- Luôn kèm tên phố/địa điểm ăn cụ thể tại Hà Nội
- Nếu có giai thoại / sự kiện nổi tiếng, PHẢI đề cập — đây là yếu tố gây ấn tượng mạnh
