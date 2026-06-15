import os

PROMPTS = {
    "A_di_tich_lich_su.md": """## Hướng dẫn cụ thể cho danh mục A. Di tích lịch sử - Văn hoá

**Ghi đè phần [Essential Elements]**: Vui lòng sắp xếp mô tả sao cho tập trung vào các yếu tố cốt lõi của một di tích lịch sử:
- **[Core Entity]**: Tên chính thức của di tích, đình, đền, chùa.
- **[Location Entity]**: Vị trí địa lý, không gian xung quanh.
- **[Architectural & Visual Components]**: Phong cách kiến trúc, kết cấu, vật liệu, chi tiết chạm khắc, màu sắc và hình khối nổi bật trong khung hình.
- **[Historical Timeline & Significance]**: Các dấu mốc lịch sử, nhân vật liên quan, ý nghĩa lịch sử (thay cho Dynamic Human Entity nếu không có hoạt động người).
- **[Travel Experience Entity]**: Không gian linh thiêng, cổ kính, giá trị văn hoá và cảm xúc mang lại cho du khách.
""",
    "B_ho_cong_vien.md": """## Hướng dẫn cụ thể cho danh mục B. Hồ - Công viên - Cảnh quan

**Ghi đè phần [Essential Elements]**:
- **[Core Entity]**: Tên hồ, công viên hoặc khu vực cảnh quan.
- **[Location Entity]**: Vị trí, không gian bao quát.
- **[Natural & Visual Components]**: Màu sắc của nước, bầu trời, cây xanh, thảm thực vật, các công trình nhỏ ven hồ/công viên.
- **[Dynamic & Human Entity]**: Nhịp sống thường nhật, người đi dạo, tập thể dục, đạp xe hoặc sự tĩnh lặng của cảnh quan.
- **[Travel Experience Entity]**: Không khí trong lành, bình yên, sự thư giãn và cảm giác hoà mình vào thiên nhiên.
""",
    "C_bao_tang.md": """## Hướng dẫn cụ thể cho danh mục C. Bảo tàng

**Ghi đè phần [Essential Elements]**:
- **[Core Entity]**: Tên bảo tàng hoặc khu trưng bày.
- **[Location Entity]**: Vị trí không gian (trong nhà/ngoài trời), bối cảnh khu trưng bày.
- **[Exhibition & Visual Components]**: Hiện vật, cách bố trí ánh sáng, tủ kính, màu sắc, hình dáng chi tiết của các cổ vật hoặc tranh ảnh được quay.
- **[Historical & Educational Value]**: Nội dung câu chuyện lịch sử đằng sau hiện vật (thay cho Dynamic Human Entity).
- **[Travel Experience Entity]**: Trải nghiệm học hỏi, sự trầm trồ, không gian học thuật và khám phá văn hoá.
""",
    "D_nghe_thuat_bieu_dien.md": """## Hướng dẫn cụ thể cho danh mục D. Nghệ thuật biểu diễn

**Ghi đè phần [Essential Elements]**:
- **[Core Entity]**: Tên loại hình nghệ thuật (Ca trù, Chèo, Múa rối nước...).
- **[Location Entity]**: Sân khấu, không gian biểu diễn (thuỷ đình, nhà hát, đình làng).
- **[Performance & Visual Components]**: Trang phục, đạo cụ (con rối, nhạc cụ), ánh sáng sân khấu, màu sắc rực rỡ và động tác của người nghệ sĩ.
- **[Dynamic & Human Entity]**: Hành động biểu diễn, biểu cảm khuôn mặt nghệ sĩ, tương tác với khán giả, âm thanh/nhạc điệu.
- **[Travel Experience Entity]**: Sự thăng hoa của nghệ thuật, giá trị truyền thống, cảm xúc ấn tượng của người xem.
""",
    "E_le_hoi_su_kien.md": """## Hướng dẫn cụ thể cho danh mục E. Lễ hội - Sự kiện

**Ghi đè phần [Essential Elements]**:
- **[Core Entity]**: Tên lễ hội hoặc sự kiện.
- **[Location Entity]**: Không gian tổ chức (sân đình, đường phố, quảng trường).
- **[Festive & Visual Components]**: Cờ hội, kiệu rước, mâm cúng, trang phục lễ hội, màu sắc sặc sỡ, không gian trang hoàng.
- **[Dynamic & Human Entity]**: Đám đông nghi lễ, người rước kiệu, các hoạt động tế lễ, trò chơi dân gian, sự nhộn nhịp.
- **[Travel Experience Entity]**: Không khí linh thiêng đan xen náo nhiệt, tinh thần cộng đồng, sự kết nối văn hoá.
""",
    "F_lang_nghe_truyen_thong.md": """## Hướng dẫn cụ thể cho danh mục F. Làng nghề truyền thống

**Ghi đè phần [Essential Elements]**:
- **[Core Entity]**: Tên làng nghề và sản phẩm thủ công đặc trưng.
- **[Location Entity]**: Không gian xưởng sản xuất, sân phơi, không gian làng quê.
- **[Crafting & Visual Components]**: Nguyên liệu (đất sét, tơ lụa, nan tre), chi tiết sản phẩm thủ công, màu sắc, hoa văn, kết cấu bề mặt.
- **[Dynamic & Human Entity]**: Bàn tay khéo léo của nghệ nhân, các công đoạn chế tác (chuốt gốm, dệt lụa, đan lát), sự tỉ mỉ.
- **[Travel Experience Entity]**: Sự trân trọng tinh hoa thủ công, tính chân thực, vẻ đẹp lao động truyền thống.
""",
    "G_am_thuc.md": """## Hướng dẫn cụ thể cho danh mục G. Ẩm thực Hà Nội

**Ghi đè phần [Essential Elements]**:
- **[Core Entity]**: Tên món ăn đặc sản hoặc nguyên liệu.
- **[Location Entity]**: Không gian quán ăn, gánh hàng rong, phố ẩm thực.
- **[Culinary & Visual Components]**: Màu sắc của món ăn, khói bốc lên, các thành phần nguyên liệu (thịt, rau thơm, nước dùng), cách bày trí hấp dẫn.
- **[Dynamic & Human Entity]**: Thao tác chế biến của người bán, sự thưởng thức ngon miệng của thực khách.
- **[Travel Experience Entity]**: Hương vị thơm ngon (tưởng tượng), sự ấm cúng, tinh hoa ẩm thực đường phố và văn hoá ăn uống.
""",
    "H_hoat_dong_du_lich.md": """## Hướng dẫn cụ thể cho danh mục H. Hoạt động du lịch & Giải trí

**Ghi đè phần [Essential Elements]**:
- **[Core Entity]**: Tên hoạt động trải nghiệm (đi xích lô, xe bus 2 tầng, dạo phố...).
- **[Location Entity]**: Tuyến phố, khu vực diễn ra hoạt động.
- **[Activity & Visual Components]**: Phương tiện trải nghiệm, thiết bị, quang cảnh lướt qua ống kính, màu sắc phương tiện.
- **[Dynamic & Human Entity]**: Sự hào hứng của du khách, chuyển động của xe cộ/người tham gia, tương tác xã hội.
- **[Travel Experience Entity]**: Sự thú vị, mới mẻ, nhịp sống hiện đại đan xen văn hoá.
""",
    "I_thien_nhien_ngoai_thanh.md": """## Hướng dẫn cụ thể cho danh mục I. Thiên nhiên & Ngoại thành

**Ghi đè phần [Essential Elements]**:
- **[Core Entity]**: Tên khu vực tự nhiên (núi, đồi, vườn quốc gia, làng cổ).
- **[Location Entity]**: Bối cảnh địa hình, không gian rộng lớn.
- **[Natural & Visual Components]**: Màu xanh của thảm thực vật, cấu trúc đá, mây trời, sương mù, hình thái tự nhiên hoang sơ.
- **[Dynamic & Human Entity]**: Sự tĩnh lặng của tự nhiên, chuyển động của cây lá, chim muông hoặc người leo núi/cắm trại.
- **[Travel Experience Entity]**: Sự hùng vĩ, thanh bình, cảm giác thoát khỏi chốn đô thị ồn ào.
""",
    "J_nguoi_dan_van_hoa_song.md": """## Hướng dẫn cụ thể cho danh mục J. Người dân & Văn hoá sống

**Ghi đè phần [Essential Elements]**:
- **[Core Entity]**: Chủ đề về lối sống, nét văn hoá thường nhật.
- **[Location Entity]**: Không gian sinh hoạt (ngõ hẻm, chợ dân sinh, vỉa hè).
- **[Daily Life & Visual Components]**: Đồ đạc sinh hoạt, hàng quán vỉa hè, trang phục thường ngày, chi tiết kiến trúc dân dụng nhỏ.
- **[Dynamic & Human Entity]**: Hoạt động buôn bán, trò chuyện, đi lại thường nhật, biểu cảm tự nhiên của người dân.
- **[Travel Experience Entity]**: Sự chân thực, gần gũi, cái nhìn sâu sắc vào nhịp đập thực sự của thành phố.
""",
    "K_bon_mua_ha_noi.md": """## Hướng dẫn cụ thể cho danh mục K. Bốn mùa Hà Nội

**Ghi đè phần [Essential Elements]**:
- **[Core Entity]**: Hiện tượng thời tiết hoặc đặc trưng của mùa (Hoa sưa, lá vàng, mưa phùn...).
- **[Location Entity]**: Không gian chịu ảnh hưởng của mùa (góc phố, hàng cây).
- **[Seasonal & Visual Components]**: Màu sắc đặc trưng của mùa (lá vàng, hoa nở rộ), ánh sáng (nắng gắt, trời xám), hiệu ứng thời tiết (mưa, sương).
- **[Dynamic & Human Entity]**: Cách con người phản ứng với thời tiết (mặc áo ấm, che ô, đi dạo dưới tán cây).
- **[Travel Experience Entity]**: Vẻ đẹp lãng mạn, sự thay đổi của thời gian, cảm xúc đặc trưng của mùa (xao xuyến, tĩnh lặng).
""",
    "L_video_dac_biet.md": """## Hướng dẫn cụ thể cho danh mục L. Video đặc biệt

**Ghi đè phần [Essential Elements]**:
- **[Core Entity]**: Tiêu đề của video hoặc nội dung đặc biệt.
- **[Location Entity]**: Bối cảnh đa dạng hoặc trừu tượng.
- **[Visual Components]**: Chi tiết đồ hoạ, góc máy đặc biệt, các yếu tố thị giác nổi bật.
- **[Dynamic & Human Entity]**: Các chuyển động độc đáo, thông điệp truyền tải.
- **[Travel Experience Entity]**: Sự ấn tượng, góc nhìn độc lạ hoặc thông điệp sáng tạo.
"""
}

def main():
    prompts_dir = os.path.join(os.path.dirname(__file__), "prompts")
    os.makedirs(prompts_dir, exist_ok=True)
    for filename, content in PROMPTS.items():
        filepath = os.path.join(prompts_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Created {filename}")

if __name__ == "__main__":
    main()
