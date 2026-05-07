# Kế Hoạch Triển Khai Chức Năng: Export Video & JSON theo Subpart (Dung lượng lớn 5-7GB)

## 1. Phân Tích Bài Toán
- **Hiện trạng:** Hệ thống đang cho phép xuất dữ liệu nguyên khối (toàn bộ video và một file data.json) thông qua một request đồng bộ (synchronous). 
- **Vấn đề:** Với dung lượng lớn (5-7GB/lần export), request đồng bộ qua web sẽ gây ra nghẽn mạng (Timeout 504), trình duyệt bị treo, tràn RAM hoặc sinh ra file rác trên ổ cứng nếu bị ngắt kết nối.
- **Yêu cầu mới:** 
  1. Phân loại video và metadata theo từng **Subpart** (gói công việc) và nén vào một file ZIP `(Ví dụ: Subpart_1/video.mp4, Subpart_1/data.json)`.
  2. Hệ thống phải chịu tải được file cực lớn (5-7GB) mà không nghẽn request.

---

## 2. Kiến Trúc Giải Pháp Đề Xuất
Kiến trúc **"Background Task + Database Polling"** thay vì request đồng bộ.

- Không sử dụng hàng đợi ngoài (Celery/Redis/RabbitMQ) để hạn chế phức tạp hóa hạ tầng cho dự án hiện tại. 
- Thay vào đó sẽ sử dụng `Threading` của Python tích hợp trực tiếp chung với trạng thái xử lý lưu trên cơ sở dữ liệu `MongoDB`.

---

## 3. Các Bước Triển Khai Chi Tiết

### 3.1. Backend (Python/Flask + MongoDB)
Thực hiện tại: `backend/routes/projects.py` (hoặc tạo route mới phụ trách export)

**Mục tiêu:** Chuyển đổi export thành 3 Endpoint rời rạc.

* **API 1: `POST /api/projects/<id>/export/subparts/start`**
  - **Nhiệm vụ:** Tiếp nhận yêu cầu.
  - **Xử lý:** 
    - Tạo một Task record tạm trong MongoDB (Collection mới `export_tasks`): `{ "project_id": <id>, "status": "processing", "progress": 0, "file_path": "" }`.
    - Tạo một thư mục tạm trên ổ cứng: `backend/uploads/exports/`.
    - Kích hoạt một hàm chạy trong mạng luồng nền `threading.Thread(target=process_export_task, args=(task_id, project_id))` để hệ thống không bị block.
  - **Kết quả trả về:** Trả về ngay lập tức `{ "task_id": "xxx" }`.

* **Luồng chạy dưới Server (Background Thread `process_export_task`)**:
  - Truy vấn toàn bộ Subpart của Project.
  - Truy vấn toàn bộ Video, kết nối (JOIN) xem chúng thuộc Subpart nào.
  - Mở tạo `zipfile.ZipFile("backend/uploads/exports/proj_XYZ.zip", 'w', zipfile.ZIP_STORED)`.
  - **Streaming Copy:** Lặp qua từng video. Mở luồng đọc từ vị trí storage gốc và ghi (write) từng block (chunk) nối tiếp vào file Zip với cấu trúc giả lập (Ví dụ `Subpart_1/video1.mp4`).  (Việc ghi từng block giúp RAM chỉ tiêu tốn 10MB dù file lên tới 5GB).
  - Xử lý xong 1 video sẽ đi gọi lệnh Update lên MongoDB record cũ: `progress = (số video đã copy / tổng số video) * 100`.
  - Copy xong Video thì tạo JSON dump (`data.json`) metadata ghép cho từng subpart và ghi tiếp vào ZIP.
  - Đóng hoàn tất file ZIP. Đổi Status task trong MongoDB thành: `status: "completed"`, cập nhật đường dẫn `file_path`.
  - **Tính năng Dọn Rác (Lazy Cleanup):** Ở đầu hoặc cuối hàm, quét và xóa các file zip sinh ra trước đó trên 24 giờ.

* **API 2: `GET /api/projects/export/status/<task_id>`**
  - **Nhiệm vụ:** Phục vụ FE hỏi đáp.
  - **Xử lý:** Query MongoDB lấy status task hiện tại.
  - **Kết quả trả về:** `{ "status": "processing", "progress": 45 }`.

* **API 3: `GET /api/projects/export/download/<task_id>`**
  - **Nhiệm vụ:** Đẩy file xuống máy người dùng.
  - **Xử lý:** Kiểm tra task `completed`, lấy đường dẫn `file_path`.
  - Dùng `send_file(path, as_attachment=True)` của Flask để streaming file zip 7GB xuống cho người dùng.

---

### 3.2. Frontend (Angular)
Thực hiện tại: `project.service.ts` và component quản lý màn hình dự án.

**Mục tiêu:** Thay đổi UI UX để tương tác mượt mà với quy trình xử lý không đồng bộ.

1. **Giao Diện - Thêm Nút Bấm và Trạng Thái:**
   - Thay đổi nút bấm: Khi đang click Export, nút bấm bị *Disable* ghi "Đang xử lý xuất dữ liệu...".
   - Bổ sung `<progress-bar>` hiển thị % chạy tiến độ thực tế (ví dụ: 15%, 85%).

2. **Dịch Vụ API - Thêm các hàm phụ trợ:** 
   - `startExportTask()`, `checkTaskStatus()`, `downloadFileByTask()`.

3. **Luồng Logic RXJS (Component):**
   - Click -> Xử lý gọi `startExportTask()` -> sinh ra `taskId`.
   - Ngay lập tức gọi bộ định thời `setInterval` hoặc `timer` của RxJS: Cứ **3 giây gọi Backend `checkTaskStatus()` một lần**.
   - Nhận `%`: Update UI tiến trình trên thanh Progress Bar.
   - Nhận `status === 'completed'`: Xóa bỏ Interval/timer định thời.
     - Hiển thị thông báo Toast "Đã nén xong 7GB! Đang tải về...".
     - Giả lập thẻ `<a href="API 3: API tải file">` và trigger click ngầm hoặc dùng `window.open` để khởi động trình tải file của hệ điều hành.
   - Xử lý ngoại lệ lỗi mạng hoặc huỷ Component: Có lệnh hủy hàm theo dõi trong hàm `ngOnDestroy` khi user chuyển trang khác. 

---

## 4. Đặc Tính Hệ Thống Đảm Bảo Được:
* Giải quyết bài toán không đủ dung lượng RAM khi xuất file 7GB trên server Python.
* Giải quyết triệt để HTTP Timeout 504 khi chờ trên Web tĩnh quá lâu.
* An toàn trước thao tác F5 / Hủy request của User (Không sinh file rác tồn đọng chết).
* Có trạng thái trực quan rõ ràng % tạo cảm giác an tâm cho người sử dụng ứng dụng.