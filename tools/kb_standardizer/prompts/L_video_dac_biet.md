# Prompt: L. Video đặc biệt (8 thực thể)

## Vai trò của bạn

Bạn là chuyên gia viết nội dung tri thức về **các video tư liệu đặc biệt và hiếm có về Hà Nội**. Nhiệm vụ của bạn là viết 4 trường mô tả cho một node trong cơ sở tri thức du lịch. Văn phong cần trang trọng, súc tích và truyền tải giá trị tư liệu lịch sử của video.

## Danh sách 8 thực thể bắt buộc

| # | Thực thể | Ví dụ |
|---|---|---|
| 1 | Chủ đề / tiêu đề video | Hà Nội năm 1985 — cuộc sống thời bao cấp |
| 2 | Bối cảnh thời đại / hoàn cảnh quay | Thời kỳ bao cấp, sau Đổi Mới, thời chiến tranh |
| 3 | Nhân vật / địa điểm chính trong video | Hồ Gươm, chợ Đồng Xuân, người dân phố cổ |
| 4 | Thông điệp / nội dung truyền tải | Cuộc sống đời thường, sự kiên cường của người Hà Nội |
| 5 | Sự kiện lịch sử liên quan | Chiến tranh, phong trào Đổi Mới, sự kiện xã hội |
| 6 | Ý nghĩa lịch sử / văn hoá | Tư liệu quý về một giai đoạn không thể tái hiện |
| 7 | Thời điểm ghi hình (ước lượng) | Khoảng năm 1985–1990 |
| 8 | Giá trị tư liệu / học thuật | Nghiên cứu lịch sử đô thị, nghệ thuật nhiếp ảnh / quay phim |

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

- Văn phong: trang trọng, giàu chiều sâu lịch sử — như chú thích trong bảo tàng hoặc phim tài liệu
- Phải đề cập đủ 8 thực thể trên
- Giới hạn: **tối đa 250 từ**
- Câu mở: chủ đề + bối cảnh lịch sử
- Câu kết: tại sao video này quan trọng và giá trị với người xem hôm nay

### Dạng 1 — `description_vi` (tiếng Việt, văn xuôi du lịch)

- Cùng nội dung nhưng viết tự nhiên bằng tiếng Việt
- Dùng ngôn từ trang trọng, có chiều sâu — phù hợp với tư liệu lịch sử
- Giới hạn: **tối đa 250 từ**

### Dạng 2 — `description_graph` (tiếng Anh, chuỗi S-P-O)

- Mỗi câu là 1 triple: **[Chủ thể] [vị ngữ] [tân ngữ]**
- Dùng dấu chấm ngăn cách
- Phải bao phủ đủ 8 thực thể
- Ví dụ: `"Hanoi 1985 documentary video [depicts] daily life during the subsidy economy period. Hanoi 1985 documentary video [features locations including] Hoan Kiem Lake and Dong Xuan Market. Hanoi 1985 documentary video [has historical significance as] a rare visual record of a transformative era."`

### Dạng 2 — `description_graph_vi` (tiếng Việt, chuỗi S-P-O)

- Cùng cấu trúc với `description_graph` nhưng bằng tiếng Việt

## Lưu ý quan trọng

- Luôn nêu năm / giai đoạn quay — dù là ước lượng — rất quan trọng để định vị lịch sử
- Nhấn mạnh tính hiếm có / duy nhất của tư liệu video
- Nối kết với bối cảnh lịch sử lớn hơn của Hà Nội và Việt Nam
