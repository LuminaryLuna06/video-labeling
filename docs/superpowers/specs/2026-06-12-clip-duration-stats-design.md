# Clip Duration Statistics Design

**Goal:** Hiển thị thống kê số lượng video gốc theo thời lượng (S/M/L) trên trang Dashboard, chỉ tính video project.

**Architecture:** Backend thêm endpoint MongoDB aggregation trả về bucket counts; Frontend gọi endpoint này khi load Dashboard và hiển thị stats bar ngay trên project grid.

**Tech Stack:** Flask + PyMongo (backend), Angular + Angular Material (frontend)

---

## Backend

### File mới: `backend/routes/stats.py`

Blueprint `stats_bp`, đăng ký tại `url_prefix='/api/stats'`.

**Endpoint:** `GET /api/stats/video-duration`

Yêu cầu auth (`@token_required` — giống các route khác).

**Logic:**
1. Lấy tất cả `project_id` của project có `project_type == 'video'`
2. Query collection `videos` lọc theo các `project_id` đó
3. Phân loại từng video theo `duration` (giây):
   - **S**: [30, 60)
   - **M**: [60, 300)
   - **L**: [300, 600)
   - **other**: < 30 hoặc ≥ 600 hoặc `duration` không tồn tại / bằng 0
4. Trả về JSON

**Response schema:**
```json
{
  "S": 12,
  "M": 45,
  "L": 8,
  "other": 3,
  "total": 68
}
```

Dùng MongoDB aggregation pipeline (`$match` → `$group` với `$switch` trên `duration`) để tính trên server, không kéo toàn bộ document về Python.

### Thay đổi `backend/app.py`

Thêm 2 dòng đăng ký blueprint:
```python
from routes.stats import stats_bp
app.register_blueprint(stats_bp, url_prefix='/api/stats')
```

---

## Frontend

### Type mới trong `frontend/src/app/core/models/index.ts`

```ts
export interface DurationStats {
  S: number;
  M: number;
  L: number;
  other: number;
  total: number;
}
```

### Method mới trong `frontend/src/app/core/services/video.service.ts`

```ts
getVideoDurationStats(): Observable<DurationStats> {
  return this.http.get<DurationStats>('/api/stats/video-duration');
}
```

### Thay đổi `frontend/src/app/pages/dashboard/dashboard.component.ts`

- Thêm property `durationStats: DurationStats | null = null`
- Gọi `videoService.getVideoDurationStats()` trong `ngOnInit()`, song song với `loadProjects()`
- Xử lý lỗi im lặng (nếu stats fail, ẩn stats bar, không block dashboard)

### Thay đổi `frontend/src/app/pages/dashboard/dashboard.component.html`

Thêm stats bar giữa page-header và projects-grid:

```
My Projects                                [New Project]
Manage your video and image annotation projects

┌──────────┬──────────┬──────────┬──────────┐
│  S       │  M       │  L       │  Total   │
│  12      │  45      │   8      │   68     │
│ 30s–1m   │ 1m–5m    │ 5m–10m   │  videos  │
└──────────┴──────────┴──────────┴──────────┘

[project cards...]
```

4 card nằm ngang, dùng Angular Material Card, chỉ hiển thị khi `durationStats !== null`.

---

## Error Handling

- Backend: nếu query MongoDB lỗi → trả `500` với `{ "error": "..." }`
- Frontend: nếu API lỗi → `durationStats` giữ nguyên `null`, stats bar không render (dashboard vẫn hoạt động bình thường)

## Scope không bao gồm

- Chart / biểu đồ (chỉ số thuần)
- Lọc theo project cụ thể
- Video "other" (< 30s hoặc ≥ 10m) không hiển thị riêng trên UI (gộp ẩn, chỉ có trong response JSON)
