# Clip Duration Statistics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm stats bar trên Dashboard hiển thị số lượng video gốc theo bucket thời lượng S/M/L, chỉ tính video project.

**Architecture:** Backend thêm `GET /api/stats/video-duration` dùng MongoDB aggregation; Frontend gọi endpoint này khi Dashboard load, hiển thị 4 card (S, M, L, Total) trên project grid.

**Tech Stack:** Flask + PyMongo, Angular 17 + Angular Material, MongoDB aggregation pipeline

---

## File Map

| Action | Path |
|--------|------|
| Create | `backend/routes/stats.py` |
| Modify | `backend/app.py` (thêm 2 dòng register blueprint) |
| Modify | `frontend/src/app/core/models/index.ts` (thêm interface) |
| Modify | `frontend/src/app/core/services/video.service.ts` (thêm method) |
| Modify | `frontend/src/app/pages/dashboard/dashboard.component.ts` |
| Modify | `frontend/src/app/pages/dashboard/dashboard.component.html` |
| Modify | `frontend/src/app/pages/dashboard/dashboard.component.scss` |

---

### Task 1: Backend — stats endpoint

**Files:**
- Create: `backend/routes/stats.py`
- Modify: `backend/app.py:62-82`

- [ ] **Step 1: Tạo file `backend/routes/stats.py`**

```python
from flask import Blueprint, jsonify, current_app
from utils.auth_middleware import token_required

stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/video-duration', methods=['GET'])
@token_required
def video_duration_stats():
    try:
        video_projects = list(current_app.db.projects.find(
            {'project_type': 'video'}, {'_id': 1}
        ))
        project_ids = [p['_id'] for p in video_projects]

        if not project_ids:
            return jsonify({'S': 0, 'M': 0, 'L': 0, 'other': 0, 'total': 0})

        pipeline = [
            {'$match': {'project_id': {'$in': project_ids}}},
            {'$group': {
                '_id': {
                    '$switch': {
                        'branches': [
                            {
                                'case': {'$and': [{'$gte': ['$duration', 30]}, {'$lt': ['$duration', 60]}]},
                                'then': 'S'
                            },
                            {
                                'case': {'$and': [{'$gte': ['$duration', 60]}, {'$lt': ['$duration', 300]}]},
                                'then': 'M'
                            },
                            {
                                'case': {'$and': [{'$gte': ['$duration', 300]}, {'$lt': ['$duration', 600]}]},
                                'then': 'L'
                            },
                        ],
                        'default': 'other'
                    }
                },
                'count': {'$sum': 1}
            }}
        ]

        results = list(current_app.db.videos.aggregate(pipeline))
        stats: dict = {'S': 0, 'M': 0, 'L': 0, 'other': 0}
        for r in results:
            bucket = r['_id']
            if bucket in stats:
                stats[bucket] = r['count']
        stats['total'] = sum(stats.values())
        return jsonify(stats)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

- [ ] **Step 2: Đăng ký blueprint trong `backend/app.py`**

Tìm block import blueprints (khoảng dòng 62-70), thêm dòng `from routes.stats import stats_bp` vào cuối block import:

```python
    from routes.stats import stats_bp
```

Tìm block register_blueprint (khoảng dòng 73-82), thêm dòng sau cùng:

```python
    app.register_blueprint(stats_bp, url_prefix='/api/stats')
```

- [ ] **Step 3: Verify endpoint bằng curl**

Lấy JWT token trước (thay `YOUR_TOKEN` bằng token thực từ login):

```bash
# Login để lấy token
TOKEN=$(curl -s -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Gọi endpoint
curl -s http://localhost:5000/api/stats/video-duration \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected output (số tuỳ data thực):
```json
{
    "L": 0,
    "M": 3,
    "S": 1,
    "other": 2,
    "total": 6
}
```

- [ ] **Step 4: Commit**

```bash
git add backend/routes/stats.py backend/app.py
git commit -m "feat: add GET /api/stats/video-duration endpoint"
```

---

### Task 2: Frontend — model + service

**Files:**
- Modify: `frontend/src/app/core/models/index.ts`
- Modify: `frontend/src/app/core/services/video.service.ts`

- [ ] **Step 1: Thêm interface `DurationStats` vào cuối `models/index.ts`**

Mở file, append vào cuối:

```typescript
export interface DurationStats {
  S: number;
  M: number;
  L: number;
  other: number;
  total: number;
}
```

- [ ] **Step 2: Thêm method vào `video.service.ts`**

Dòng import đầu file hiện là:
```typescript
import { VideoItem, VideoSegment, ObjectRegion, SegmentationResponse, Caption, Category } from '../models';
```

Thêm `DurationStats` vào import:
```typescript
import { VideoItem, VideoSegment, ObjectRegion, SegmentationResponse, Caption, Category, DurationStats } from '../models';
```

Thêm constant `STATS_API` sau `CATEGORIES_API`:
```typescript
  private readonly STATS_API = '/api/stats';
```

Append method vào cuối class (trước dấu `}`):
```typescript
  getVideoDurationStats(): Observable<DurationStats> {
    return this.http.get<DurationStats>(`${this.STATS_API}/video-duration`);
  }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/core/models/index.ts \
        frontend/src/app/core/services/video.service.ts
git commit -m "feat: add DurationStats model and getVideoDurationStats service method"
```

---

### Task 3: Frontend — Dashboard UI

**Files:**
- Modify: `frontend/src/app/pages/dashboard/dashboard.component.ts`
- Modify: `frontend/src/app/pages/dashboard/dashboard.component.html`
- Modify: `frontend/src/app/pages/dashboard/dashboard.component.scss`

- [ ] **Step 1: Cập nhật `dashboard.component.ts`**

Thêm `DurationStats` vào import models (dòng import hiện có `Project`):
```typescript
import { Project, DurationStats } from '../../core/models';
```

Thêm property sau `loading = true;`:
```typescript
  durationStats: DurationStats | null = null;
```

Thêm call `this.loadDurationStats()` vào `ngOnInit`:
```typescript
  ngOnInit(): void {
    this.loadProjects();
    this.loadDurationStats();
  }
```

Thêm method `loadDurationStats` sau `loadProjects()`:
```typescript
  loadDurationStats(): void {
    this.videoService.getVideoDurationStats().subscribe({
      next: (stats) => { this.durationStats = stats; },
      error: () => { /* silent fail — stats bar stays hidden */ }
    });
  }
```

- [ ] **Step 2: Thêm stats bar vào `dashboard.component.html`**

Tìm comment `<!-- Loading -->` trong file. Chèn đoạn sau ngay phía trên comment đó (sau thẻ đóng `</div>` của `.page-header`):

```html
  <!-- Duration Stats Bar -->
  <div class="duration-stats" *ngIf="durationStats !== null">
    <div class="duration-card">
      <span class="duration-count">{{ durationStats!.S }}</span>
      <span class="duration-label">S</span>
      <span class="duration-range">30s – 1m</span>
    </div>
    <div class="duration-card">
      <span class="duration-count">{{ durationStats!.M }}</span>
      <span class="duration-label">M</span>
      <span class="duration-range">1m – 5m</span>
    </div>
    <div class="duration-card">
      <span class="duration-count">{{ durationStats!.L }}</span>
      <span class="duration-label">L</span>
      <span class="duration-range">5m – 10m</span>
    </div>
    <div class="duration-card total">
      <span class="duration-count">{{ durationStats!.total }}</span>
      <span class="duration-label">Total</span>
      <span class="duration-range">videos</span>
    </div>
  </div>
```

- [ ] **Step 3: Thêm styles vào `dashboard.component.scss`**

Append vào cuối file:

```scss
.duration-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

.duration-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.duration-card.total {
  border-color: rgba(59, 130, 246, 0.3);
  background: rgba(59, 130, 246, 0.06);
}

.duration-count {
  font-size: 32px;
  font-weight: 700;
  color: #f1f5f9;
  line-height: 1;
}

.duration-label {
  font-size: 13px;
  font-weight: 600;
  color: #3b82f6;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.duration-range {
  font-size: 12px;
  color: #64748b;
}
```

- [ ] **Step 4: Verify trên browser**

Mở `http://localhost:4200/dashboard`. Kiểm tra:
- Stats bar hiện ra với 4 card (S / M / L / Total)
- Số liệu khớp với output curl từ Task 1 Step 3
- Nếu không có video project nào → tất cả hiện `0`
- Khi resize cửa sổ nhỏ → 4 card không bị tràn (nếu tràn, đổi `grid-template-columns` sang `repeat(2, 1fr)` với media query)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/dashboard/dashboard.component.ts \
        frontend/src/app/pages/dashboard/dashboard.component.html \
        frontend/src/app/pages/dashboard/dashboard.component.scss
git commit -m "feat: show video duration stats bar on dashboard"
```
