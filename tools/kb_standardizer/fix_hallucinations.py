import yaml
import sys
from pathlib import Path

file_path = Path(r"d:\work\AI\video-labeling\tools\kb_standardizer\output\kb_enriched_20260612_141438.yaml")

with open(file_path, "r", encoding="utf-8") as f:
    data = yaml.safe_load(f)

for node in data.get("nodes", []):
    kb_id = node.get("kb_id", "")
    
    # Node 1: archaeological_pit
    if kb_id == "archaeological_pit":
        node["description"] = node["description"].replace(
            "built at lightning speed in 1964, right at the moment when the war of destruction against the North began to escalate fiercely",
            "built in late 1964 and completed in early 1965, at the very beginning of the US air war of destruction against the North"
        )
        node["description_vi"] = node["description_vi"].replace(
            "Hầm được xây dựng thần tốc vào năm 1964, đúng thời điểm chiến tranh phá hoại miền Bắc bắt đầu leo thang ác liệt.",
            "Hầm được xây dựng từ cuối năm 1964 đến đầu năm 1965, ngay từ những ngày đầu Mỹ gây chiến tranh phá hoại miền Bắc."
        )

    # Node 2: bay_mau_lake_shore
    elif kb_id == "bay_mau_lake_shore":
        node["description"] = node["description"].replace(
            "Tracing back history to the sixties of the last century",
            "Tracing back history to the late 1950s"
        )
        node["description_vi"] = node["description_vi"].replace(
            "Ngược dòng lịch sử về những năm sáu mươi của thế kỷ trước",
            "Ngược dòng lịch sử về những năm cuối thập niên năm mươi của thế kỷ trước"
        )

    # Node 3: dai_thanh_courtyard
    elif kb_id == "dai_thanh_courtyard":
        node["description"] = "Dai Thanh Courtyard is the expansive, culturally profound yard located in front of the Dai Thanh Sanctuary within the Temple of Literature (Văn Miếu – Quốc Tử Giám). It is a solemn space where scholars once gathered and where ancient ceremonies paying respect to Confucius and prominent figures of Vietnamese education were held."
        node["description_vi"] = "Sân Đại Thành là khoảng sân rộng lớn và mang đậm dấu ấn văn hóa nằm ngay trước điện Đại Thành trong khuôn viên Văn Miếu – Quốc Tử Giám. Nơi đây là không gian trang nghiêm, xưa kia là nơi các sĩ tử tụ họp và diễn ra các nghi lễ quan trọng tôn vinh Khổng Tử cùng các bậc hiền tài của nền giáo dục nước nhà."
        if "description_graph" in node and "[faces]" in node["description_graph"]:
            lines = node["description_graph"].split("\n")
            node["description_graph"] = "\n".join([line for line in lines if "[faces] West Lake" not in line and "West Lake" not in line])

    # Node 4: flag_tower_of_hanoi
    elif kb_id == "flag_tower_of_hanoi":
        node["description"] = node["description"].replace(
            "a relic built in 1812 under the reign of King Gia Long",
            "a relic begun in 1805 and completed in 1812 under the reign of King Gia Long"
        )
        node["description_vi"] = node["description_vi"].replace(
            "Cột cờ Hà Nội là di tích được xây dựng năm 1812 dưới triều vua Gia Long",
            "Cột cờ Hà Nội là di tích được khởi công năm 1805 và hoàn thành năm 1812 dưới triều vua Gia Long"
        )

    # Node 5: khue_van_cac
    elif kb_id == "khue_van_cac":
        if "description_graph" in node:
            node["description_graph"] = node["description_graph"].replace(
                "Khuê Van Cac [was erected by] Emperor Gia Long",
                "Khuê Van Cac [was erected by] Tổng trấn Nguyễn Văn Thành under Emperor Gia Long"
            )
            node["description_graph"] = node["description_graph"].replace(
                "Khue Van Cac [was erected by] Emperor Gia Long",
                "Khue Van Cac [was erected by] Tổng trấn Nguyễn Văn Thành under Emperor Gia Long"
            )
        if "description_graph_vi" in node:
            node["description_graph_vi"] = node["description_graph_vi"].replace(
                "Khuê Văn Các [do] vua Gia Long [cho dựng]",
                "Khuê Văn Các [do] Tổng trấn Nguyễn Văn Thành [cho dựng] dưới triều vua Gia Long"
            )
            node["description_graph_vi"] = node["description_graph_vi"].replace(
                "Khuê Văn Các [được dựng bởi] vua Gia Long",
                "Khuê Văn Các [được dựng bởi] Tổng trấn Nguyễn Văn Thành dưới triều vua Gia Long"
            )

    # Node 6: tran_quoc_pagoda
    elif kb_id == "tran_quoc_pagoda":
        node["description"] = node["description"].replace(
            "with the name Khai Quốc, carrying the meaning of expanding the national territory",
            "with the name Khai Quốc, carrying the meaning of 'founding the nation', commemorating the establishment of the Vạn Xuân kingdom"
        )
        node["description_vi"] = node["description_vi"].replace(
            "với tên gọi Khai Quốc, mang theo nghĩa mở mang bờ cõi",
            "với tên gọi Khai Quốc, mang nghĩa khai sinh đất nước, gắn với sự kiện Lý Nam Đế lập nước Vạn Xuân"
        )

    # Node 7: truc_bach_lake
    elif kb_id == "truc_bach_lake":
        if "The beautiful, delicate silk fabrics dried on the bamboo growing along the banks gave rise to the moniker 'trúc lụa trắng'" in node.get("description", ""):
            node["description"] = node["description"].replace(
                "The beautiful, delicate silk fabrics dried on the bamboo growing along the banks gave rise to the moniker 'trúc lụa trắng'",
                "The beautiful white silk they wove became known as 'lụa làng Trúc' (Trúc village silk), and the lake separated from Hồ Tây took on the same name: Trúc Bạch"
            )
        else:
            # Nếu string không khớp, thay cụm có liên quan
            import re
            node["description"] = re.sub(
                r"(?i)The beautiful, delicate silk fabrics.*?trúc lụa trắng'?",
                "The beautiful white silk they wove became known as 'lụa làng Trúc' (Trúc village silk), and the lake separated from Hồ Tây took on the same name: Trúc Bạch",
                node["description"]
            )
        
        # Tiếng việt
        if "description_vi" in node:
            node["description_vi"] = node["description_vi"].replace(
                "Những tấm lụa trắng muốt, tinh khôi được phơi trên những rặng trúc ven bờ đã tạo nên danh xưng 'trúc lụa trắng'.",
                "Loại lụa trắng đẹp mà họ dệt ra được gọi là 'lụa làng Trúc', và phần hồ bị ngăn cách với Hồ Tây cũng mang tên là Trúc Bạch."
            )
            node["description_vi"] = node["description_vi"].replace(
                "Những tấm lụa trắng muốt được phơi trên những cành trúc ven hồ tạo nên vẻ đẹp nên thơ, từ đó có tên là 'trúc lụa trắng'.",
                "Loại lụa trắng đẹp mà họ dệt ra được gọi là 'lụa làng Trúc', và phần hồ bị ngăn cách với Hồ Tây cũng mang tên là Trúc Bạch."
            )

    # Node 8: thap_rua
    elif kb_id == "thap_rua":
        node["description"] = node["description"].replace(
            "In the 1950s, this statue was demolished when the Vietnamese government of Prime Minister Trần Trọng Kim took power",
            "In 1945, this statue was demolished when the Vietnamese government under Prime Minister Trần Trọng Kim took power"
        )
        node["description_vi"] = node["description_vi"].replace(
            "Sang thập niên 1950 tượng này bị phá bỏ khi chính phủ Việt Nam của thủ tướng Trần Trọng Kim nắm chính quyền thay cho quân Pháp.",
            "Năm 1945, tượng này bị phá bỏ khi chính phủ Việt Nam của thủ tướng Trần Trọng Kim nắm chính quyền."
        )

with open(file_path, "w", encoding="utf-8") as f:
    yaml.dump(
        data,
        f,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=120,
    )

print("Fixed YAML file successfully!")
