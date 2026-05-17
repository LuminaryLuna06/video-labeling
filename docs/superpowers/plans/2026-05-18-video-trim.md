# Video Trim (Cut + Save) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users mark ranges to remove from a video in the editor, then save a frame-accurate trimmed copy as a new `VideoItem` in the same subpart — all without leaving the web app.

**Architecture:** Frontend collects cut ranges (scratch state, no DB). On Save, frontend POSTs `{video_url, cut_ranges}` to a new DAM `/trim` endpoint; DAM downloads the source, runs ffmpeg `filter_complex` (trim + atrim + concat, re-encode), and streams back the trimmed mp4. Frontend wraps the blob in a `File` and uploads it via the existing `POST /api/videos/upload`. No backend changes.

**Tech Stack:** FastAPI + ffmpeg (CLI) on the DAM side. Angular 17 + RxJS + Material on the frontend. No new dependencies.

**Verification strategy:** No test framework exists in this project (consistent with the existing `2026-05-11-frontend-direct-dam.md` plan). Each frontend task ends with a TypeScript typecheck (`pnpm exec ng build --configuration development` from `frontend/`), and the final task runs a manual end-to-end smoke against a real DAM server. The DAM endpoint is smoke-tested with `curl` against a known short mp4 — adding pytest for one endpoint is not justified.

**Reference spec:** `docs/superpowers/specs/2026-05-18-video-trim-design.md`

---

## Prereqs

- ffmpeg and ffprobe on PATH on the DAM host (`ffmpeg -version` / `ffprobe -version` should both succeed).
- DAM server runnable locally: `cd describe-anything && python dam_server.py` (or however it's normally started in this repo).
- Frontend dev server runnable: `cd frontend && pnpm install && pnpm start`. Proxy at `proxy.conf.json` already routes `/api/*` and `/uploads/*` for you.
- A short test mp4 (5–30 s, with at least one audio track) saved somewhere reachable, e.g. uploaded through the project UI so it has a `/uploads/videos/<uuid>.mp4` URL.
- The `DAM URL` in the app's Settings dialog points at your local DAM (e.g. `http://localhost:8000`).

---

## Task 1: DAM `/trim` endpoint

**Files:**
- Modify: `describe-anything/dam_server.py` — add `subprocess` import, add `CutRange` / `TrimRequest` models, add `/trim` route.

- [ ] **Step 1: Add the `subprocess` import**

Find the existing block of stdlib imports at the top of `describe-anything/dam_server.py` (around lines 21–29) and add `subprocess` alongside `os`, `tempfile`, etc.:

```python
import subprocess
```

Place it next to `import shutil` (line 46) so it sits with the other process/file utilities.

- [ ] **Step 2: Add the Pydantic request models**

Place these immediately after the existing `SceneDetectRequest` model (currently lines 120–124 of `dam_server.py`):

```python
class CutRange(BaseModel):
    start_sec: float
    end_sec: float


class TrimRequest(BaseModel):
    video_url: str
    cut_ranges: List[CutRange]
```

- [ ] **Step 3: Add the `/trim` route**

Insert this whole block immediately *before* the `@app.get("/health")` route (currently at line 735 of `dam_server.py`):

```python
def _normalize_cuts(cut_ranges: List[CutRange], duration: float) -> List[tuple[float, float]]:
    """Clamp to [0, duration], drop zero-length / inverted, sort, merge overlaps."""
    cleaned: List[tuple[float, float]] = []
    for r in cut_ranges:
        s = max(0.0, min(r.start_sec, r.end_sec))
        e = min(duration, max(r.start_sec, r.end_sec))
        if e - s > 0.001:
            cleaned.append((s, e))
    cleaned.sort(key=lambda t: t[0])
    merged: List[tuple[float, float]] = []
    for s, e in cleaned:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def _keep_ranges(cuts: List[tuple[float, float]], duration: float) -> List[tuple[float, float]]:
    """Complement of cuts within [0, duration]."""
    keep: List[tuple[float, float]] = []
    cursor = 0.0
    for s, e in cuts:
        if s > cursor:
            keep.append((cursor, s))
        cursor = e
    if cursor < duration:
        keep.append((cursor, duration))
    return keep


def _probe_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True
    )
    return float(out.stdout.strip())


def _has_audio(path: str) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True
    )
    return bool(out.stdout.strip())


def _build_filter_complex(keeps: List[tuple[float, float]], with_audio: bool) -> tuple[str, List[str]]:
    """Build a `-filter_complex` arg and the corresponding `-map` args."""
    parts: List[str] = []
    concat_inputs: List[str] = []
    for i, (s, e) in enumerate(keeps):
        parts.append(
            f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}]"
        )
        concat_inputs.append(f"[v{i}]")
        if with_audio:
            parts.append(
                f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{i}]"
            )
            concat_inputs.append(f"[a{i}]")
    n = len(keeps)
    if with_audio:
        parts.append(f"{''.join(concat_inputs)}concat=n={n}:v=1:a=1[outv][outa]")
        maps = ["-map", "[outv]", "-map", "[outa]"]
    else:
        parts.append(f"{''.join(concat_inputs)}concat=n={n}:v=1:a=0[outv]")
        maps = ["-map", "[outv]"]
    return ";".join(parts), maps


@app.post("/trim")
async def trim_video(req: TrimRequest):
    if not req.cut_ranges:
        return JSONResponse(status_code=400, content={"error": "cut_ranges is required"})

    src_path = None
    out_path = None
    try:
        # 1. Download source
        try:
            print(f"[trim] Downloading {req.video_url}")
            r = requests.get(req.video_url, stream=True, timeout=(5, 60))
            r.raise_for_status()
        except Exception as e:
            return JSONResponse(status_code=502, content={"error": f"failed to fetch source video: {e}"})

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            for chunk in r.iter_content(chunk_size=8192):
                tmp.write(chunk)
            src_path = tmp.name

        # 2. Probe duration + audio presence
        try:
            duration = _probe_duration(src_path)
            with_audio = _has_audio(src_path)
        except subprocess.CalledProcessError as e:
            return JSONResponse(status_code=500, content={"error": f"ffprobe failed: {e.stderr or e}"})

        # 3. Compute keep ranges
        cuts = _normalize_cuts(req.cut_ranges, duration)
        keeps = _keep_ranges(cuts, duration)
        if not keeps:
            return JSONResponse(status_code=400, content={"error": "nothing left after cuts"})

        # 4. Run ffmpeg
        filter_str, maps = _build_filter_complex(keeps, with_audio)
        out_fd, out_path = tempfile.mkstemp(suffix=".mp4")
        os.close(out_fd)
        cmd = [
            "ffmpeg", "-y", "-i", src_path,
            "-filter_complex", filter_str,
            *maps,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        ]
        if with_audio:
            cmd += ["-c:a", "aac"]
        cmd.append(out_path)

        print(f"[trim] Running: {' '.join(cmd)}")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            tail = (proc.stderr or "")[-500:]
            return JSONResponse(status_code=500, content={"error": f"ffmpeg failed: {tail}"})

        # 5. Stream back
        def file_iter():
            with open(out_path, "rb") as f:
                while True:
                    chunk = f.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
        return StreamingResponse(
            file_iter(),
            media_type="video/mp4",
            headers={"Content-Disposition": 'attachment; filename="trimmed.mp4"'}
        )

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

    finally:
        for p in (src_path, out_path):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception as e:
                    print(f"[trim] warning: failed to delete {p}: {e}")
```

- [ ] **Step 4: Restart DAM and smoke-test with curl**

Restart `dam_server.py`. Then, from a shell where you have a short reachable mp4 URL, run:

```bash
curl -X POST http://localhost:8000/trim \
  -H "Content-Type: application/json" \
  -d '{"video_url":"http://localhost:5000/uploads/videos/<known-uuid>.mp4","cut_ranges":[{"start_sec":1.0,"end_sec":3.0}]}' \
  --output trimmed.mp4 -i
```

Expected:
- HTTP `200 OK` with `Content-Type: video/mp4`.
- `trimmed.mp4` is created locally and is roughly `source_duration - 2 s` long (check with `ffprobe trimmed.mp4`).

Also verify two error paths:

```bash
# empty cuts
curl -X POST http://localhost:8000/trim -H "Content-Type: application/json" \
  -d '{"video_url":"...","cut_ranges":[]}' -i
# Expected: 400 {"error":"cut_ranges is required"}

# whole-video cut
curl -X POST http://localhost:8000/trim -H "Content-Type: application/json" \
  -d '{"video_url":"...","cut_ranges":[{"start_sec":0,"end_sec":99999}]}' -i
# Expected: 400 {"error":"nothing left after cuts"}
```

- [ ] **Step 5: Commit**

```bash
git add describe-anything/dam_server.py
git commit -m "feat(dam-server): add /trim endpoint (ffmpeg re-encode)

POST /trim accepts {video_url, cut_ranges[]}, downloads the source,
computes keep ranges as the complement of normalized cuts, runs
ffmpeg filter_complex (trim+atrim+concat, libx264 veryfast crf 20),
streams the result back as video/mp4. Handles audio-less sources via
ffprobe stream detection. 400 on empty cuts or whole-video cuts, 502
on download failure, 500 on ffmpeg/ffprobe failure with stderr tail.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: Pure cut-range helpers

**Files:**
- Create: `frontend/src/app/core/utils/cut-ranges.ts`

- [ ] **Step 1: Create the file with `normalizeCuts` + `keepRanges`**

```ts
// frontend/src/app/core/utils/cut-ranges.ts

export interface CutRange {
  id?: string;
  start: number;
  end: number;
}

/**
 * Clamp each range to [0, duration], swap inverted starts/ends, drop
 * sub-millisecond ranges, sort by start, and merge any overlaps.
 * Used both client-side (button disable logic) and as a reference for
 * the server-side equivalent in dam_server.py.
 */
export function normalizeCuts(cuts: CutRange[], duration: number): CutRange[] {
  const cleaned = cuts
    .map((c) => {
      const lo = Math.min(c.start, c.end);
      const hi = Math.max(c.start, c.end);
      return { ...c, start: Math.max(0, lo), end: Math.min(duration, hi) };
    })
    .filter((c) => c.end - c.start > 0.001)
    .sort((a, b) => a.start - b.start);

  const merged: CutRange[] = [];
  for (const c of cleaned) {
    const last = merged[merged.length - 1];
    if (last && c.start <= last.end) {
      last.end = Math.max(last.end, c.end);
    } else {
      merged.push({ ...c });
    }
  }
  return merged;
}

/**
 * Complement of `cuts` within [0, duration] — the ranges that survive.
 * Returns [] when cuts cover the whole video; returns [{0,duration}] for no cuts.
 */
export function keepRanges(cuts: CutRange[], duration: number): CutRange[] {
  const normalized = normalizeCuts(cuts, duration);
  const keep: CutRange[] = [];
  let cursor = 0;
  for (const c of normalized) {
    if (c.start > cursor) keep.push({ start: cursor, end: c.start });
    cursor = c.end;
  }
  if (cursor < duration) keep.push({ start: cursor, end: duration });
  return keep;
}
```

- [ ] **Step 2: Typecheck**

From `frontend/`:

```bash
pnpm exec ng build --configuration development 2>&1 | tail -5
```

Expected: `Application bundle generation complete.` with no TS errors. (The build is the cheapest way to typecheck — there is no separate `ng test` configured.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/core/utils/cut-ranges.ts
git commit -m "feat(frontend): add cut-ranges helpers (normalizeCuts, keepRanges)

Pure functions for the video trim feature: clamp/sort/merge user cut
ranges and compute their complement within the video duration. Server
performs equivalent normalization; client uses these for button-state
checks (e.g. disable Save when cuts cover the whole video).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: Service plumbing (`DamService.trimVideo` + `VideoService.trimVideo`)

**Files:**
- Modify: `frontend/src/app/core/services/dam.service.ts`
- Modify: `frontend/src/app/core/services/video.service.ts`

- [ ] **Step 1: Add `trimVideo` to `DamService`**

In `frontend/src/app/core/services/dam.service.ts`, insert this method immediately after the existing `detectScenes` method (currently around lines 68–81):

```ts
/**
 * Send source URL + cut ranges to DAM /trim; returns the trimmed mp4 bytes.
 * URL is absolutized here to mirror detectScenes().
 */
trimVideo(videoUrl: string, cutRanges: { start_sec: number; end_sec: number }[]): Observable<Blob> {
  const url = `${this.getDamUrl()}/trim`;
  let absoluteVideoUrl = videoUrl;
  if (!absoluteVideoUrl.startsWith('http')) {
    absoluteVideoUrl = window.location.origin + absoluteVideoUrl;
  }
  return this.http.post(url, {
    video_url: absoluteVideoUrl,
    cut_ranges: cutRanges
  }, { responseType: 'blob' as 'blob' }).pipe(
    catchError((err) => throwError(() => new Error(this.formatError(url, err))))
  );
}
```

(`catchError` and `throwError` are already imported at the top of the file.)

- [ ] **Step 2: Add `trimVideo` delegation to `VideoService`**

In `frontend/src/app/core/services/video.service.ts`, insert this method immediately after `uploadVideo` (currently lines 17–25):

```ts
/**
 * Trim a source video via DAM and return the trimmed bytes.
 * Caller is responsible for wrapping the Blob in a File and calling uploadVideo().
 */
trimVideo(videoUrl: string, cutRanges: { start_sec: number; end_sec: number }[]): Observable<Blob> {
  return this.dam.trimVideo(videoUrl, cutRanges);
}
```

- [ ] **Step 3: Typecheck**

From `frontend/`:

```bash
pnpm exec ng build --configuration development 2>&1 | tail -5
```

Expected: `Application bundle generation complete.` with no TS errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/core/services/dam.service.ts frontend/src/app/core/services/video.service.ts
git commit -m "feat(frontend): add trimVideo to DamService and VideoService

DamService.trimVideo POSTs {video_url, cut_ranges} to DAM /trim and
returns the response Blob. VideoService.trimVideo delegates, matching
the segmentObject/detectScenes pattern. Caller is responsible for
uploading the returned bytes as a new VideoItem.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: Editor wiring (state + methods + template + styles)

**Files:**
- Modify: `frontend/src/app/pages/video-editor/video-editor.component.ts`
- Modify: `frontend/src/app/pages/video-editor/video-editor.component.html`
- Modify: `frontend/src/app/pages/video-editor/video-editor.component.scss`

This task ships UI plus its TS + SCSS together because they have no value in isolation.

- [ ] **Step 1: Import the helpers and add component state**

In `video-editor.component.ts`, add this import near the other utility imports (the file already imports from `'../../core/models'` etc. — put it just below those, around line 30):

```ts
import { normalizeCuts, keepRanges, CutRange } from '../../core/utils/cut-ranges';
```

Then add these fields next to the existing `// Segments` block (around lines 81–85, right after `segmentEnd: number | null = null;`):

```ts
// Trim (cut ranges to remove)
cutRanges: CutRange[] = [];
pendingCutStart: number | null = null;
trimming = false;
```

- [ ] **Step 2: Reset the new state in `resetState()`**

`resetState()` lives in `video-editor.component.ts` around line 354. Find the `// Segments & regions` block (line 361) and add the trim reset right after `this.segmentEnd = null;` (line 365):

```ts
// Trim
this.cutRanges = [];
this.pendingCutStart = null;
this.trimming = false;
```

- [ ] **Step 3: Add trim methods to the component**

Add this whole block immediately after the existing `addSegment()` method (currently ends around line 560 of `video-editor.component.ts`, just before `autoSplit()` at line 562):

```ts
// ============ Trim Operations ============
markCutStart(): void {
  this.pendingCutStart = this.currentTime;
  this.snackBar.open(`▶ Cut start at ${this.formatTime(this.currentTime)}`, '', { duration: 1500 });
}

markCutEnd(): void {
  if (this.pendingCutStart === null) {
    this.snackBar.open('Mark the cut start first', '', { duration: 1500 });
    return;
  }
  const start = Math.min(this.pendingCutStart, this.currentTime);
  const end = Math.max(this.pendingCutStart, this.currentTime);
  if (end - start < 0.05) {
    this.snackBar.open('Cut is too short', '', { duration: 1500 });
    return;
  }
  this.cutRanges = [...this.cutRanges, { id: crypto.randomUUID(), start, end }];
  this.pendingCutStart = null;
  this.snackBar.open(`Cut added: ${this.formatTime(start)} → ${this.formatTime(end)}`, '', { duration: 1500 });
}

removeCut(id: string | undefined): void {
  if (!id) return;
  this.cutRanges = this.cutRanges.filter(c => c.id !== id);
}

canSaveTrimmed(): boolean {
  return !this.trimming
    && this.cutRanges.length > 0
    && this.pendingCutStart === null
    && keepRanges(this.cutRanges, this.duration).length > 0;
}

private deriveTrimmedName(original: string): string {
  const dot = original.lastIndexOf('.');
  const base = dot > 0 ? original.slice(0, dot) : original;
  return `${base}_trimmed.mp4`;
}

saveTrimmed(): void {
  if (!this.video || this.trimming || this.cutRanges.length === 0) return;
  if (this.pendingCutStart !== null) return;

  const keeps = keepRanges(this.cutRanges, this.duration);
  if (keeps.length === 0) {
    this.snackBar.open('Cuts cover the whole video — nothing left to save', '', { duration: 3000 });
    return;
  }

  this.trimming = true;
  const ranges = this.cutRanges.map(c => ({ start_sec: c.start, end_sec: c.end }));
  const trimmedDuration = keeps.reduce((sum, k) => sum + (k.end - k.start), 0);
  const sourceVideo = this.video;

  this.videoService.trimVideo(sourceVideo.url, ranges).subscribe({
    next: (blob) => {
      const trimmedName = this.deriveTrimmedName(sourceVideo.original_name);
      const file = new File([blob], trimmedName, { type: 'video/mp4' });
      if (!sourceVideo.project_id) {
        this.trimming = false;
        this.snackBar.open('Cannot save: source video has no project', '', { duration: 3000, panelClass: 'snack-error' });
        return;
      }
      this.videoService.uploadVideo(
        sourceVideo.project_id,
        file,
        sourceVideo.subpart_id,
        trimmedDuration
      ).subscribe({
        next: (res) => {
          this.trimming = false;
          this.snackBar
            .open(`Saved as '${trimmedName}'`, 'Open', { duration: 5000, panelClass: 'snack-success' })
            .onAction().subscribe(() => this.router.navigate(['/editor', res.id]));
        },
        error: () => {
          this.trimming = false;
          this.snackBar.open('Trim succeeded but upload failed', '', { duration: 4000, panelClass: 'snack-error' });
        }
      });
    },
    error: (err) => {
      this.trimming = false;
      this.snackBar.open(`Trim failed: ${err?.message || 'unknown error'}`, '', { duration: 4000, panelClass: 'snack-error' });
    }
  });
}
```

- [ ] **Step 4: Add the trim panel + timeline overlays to the template**

Open `frontend/src/app/pages/video-editor/video-editor.component.html`.

**Sub-step 4a — trim panel above the existing segment actions.**
Find the `<!-- Segment Actions -->` block at line 201–216. Insert this block **immediately before** it (so the trim panel sits above the existing Mark Start / Mark End / Add Segment row):

```html
<!-- Trim source video panel -->
<div class="trim-panel">
  <div class="trim-header">
    <h4>Trim source video</h4>
    <span class="hint">Mark ranges to REMOVE. Saved as a new video in the same subpart.</span>
  </div>
  <div class="trim-actions">
    <button mat-stroked-button (click)="markCutStart()" [disabled]="trimming">
      <mat-icon>content_cut</mat-icon> Mark cut start
    </button>
    <button mat-stroked-button (click)="markCutEnd()" [disabled]="pendingCutStart === null || trimming">
      <mat-icon>stop</mat-icon> Mark cut end
    </button>
    <button mat-flat-button color="warn"
            [disabled]="!canSaveTrimmed()"
            (click)="saveTrimmed()">
      <mat-icon>save</mat-icon>
      <span *ngIf="!trimming">Save trimmed as new video</span>
      <span *ngIf="trimming">Trimming…</span>
    </button>
  </div>
  <ul class="cut-list" *ngIf="cutRanges.length > 0">
    <li *ngFor="let c of cutRanges">
      <span class="cut-range-text">
        {{ formatTime(c.start) }} → {{ formatTime(c.end) }}
        <span class="cut-range-dur">({{ formatTime(c.end - c.start) }})</span>
      </span>
      <button mat-icon-button (click)="removeCut(c.id)" [disabled]="trimming">
        <mat-icon>close</mat-icon>
      </button>
    </li>
  </ul>
</div>
```

**Sub-step 4b — cut markers on the seek bar.**
Inside the `<div class="seek-bar" ...>` block (lines 170–194), append these inside the same `seek-bar` div, *after* the existing `pending-segment-marker` div (line 193, just before `</div>` closing the seek-bar at line 194):

```html
<!-- Trim cut markers -->
<div *ngFor="let c of cutRanges" class="cut-marker"
  [style.left.%]="(c.start / duration) * 100"
  [style.width.%]="((c.end - c.start) / duration) * 100">
</div>
<!-- Pending trim cut start (vertical line) -->
<div *ngIf="pendingCutStart !== null" class="pending-cut-start"
  [style.left.%]="(pendingCutStart / duration) * 100">
</div>
```

**Sub-step 4c — cut markers on the timeline track.**
Inside `<div class="timeline-track" ...>` (line 255–287), append these *before* the `<!-- Time markers -->` block at line 281:

```html
<!-- Trim cuts on timeline -->
<div *ngFor="let c of cutRanges" class="timeline-cut"
  [style.left.%]="(c.start / duration) * 100"
  [style.width.%]="((c.end - c.start) / duration) * 100">
  <span class="tl-cut-name">cut</span>
</div>
<div *ngIf="pendingCutStart !== null" class="timeline-pending-cut-start"
  [style.left.%]="(pendingCutStart / duration) * 100">
</div>
```

- [ ] **Step 5: Add SCSS for the new elements**

Open `frontend/src/app/pages/video-editor/video-editor.component.scss`.

Append the following at the **end of the file** (so it's easy to find and remove later if the panel moves):

```scss
// ============ Trim panel ============
.trim-panel {
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid rgba(244, 67, 54, 0.35); // warn-tinted
  border-radius: 6px;
  background: rgba(244, 67, 54, 0.04);

  .trim-header {
    display: flex;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 8px;

    h4 { margin: 0; font-size: 14px; }
    .hint { font-size: 12px; opacity: 0.7; }
  }

  .trim-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }

  .cut-list {
    list-style: none;
    margin: 0;
    padding: 0;

    li {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 12px;
      font-variant-numeric: tabular-nums;

      &:nth-child(odd) { background: rgba(0,0,0,0.03); }

      .cut-range-text { color: #c62828; }
      .cut-range-dur  { opacity: 0.7; margin-left: 6px; }
    }
  }
}

// ============ Cut markers on seek bar ============
.cut-marker {
  position: absolute;
  top: -2px;
  height: 10px;
  background: rgba(244, 67, 54, 0.45);
  border-left: 2px solid #d32f2f;
  border-right: 2px solid #d32f2f;
  pointer-events: none;
  z-index: 3;
}

.pending-cut-start {
  position: absolute;
  top: -4px;
  width: 3px;
  height: 14px;
  background: #d32f2f;
  z-index: 4;
  pointer-events: none;
}

// ============ Cut markers on timeline track ============
.timeline-cut {
  position: absolute;
  top: 4px;
  bottom: 24px;
  background: rgba(244, 67, 54, 0.35);
  border-left: 2px solid #d32f2f;
  border-right: 2px solid #d32f2f;
  pointer-events: none;
  display: flex;
  align-items: center;
  justify-content: center;

  .tl-cut-name {
    color: #b71c1c;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
}

.timeline-pending-cut-start {
  position: absolute;
  top: 2px;
  bottom: 22px;
  width: 3px;
  background: #d32f2f;
  pointer-events: none;
}
```

- [ ] **Step 6: Typecheck**

From `frontend/`:

```bash
pnpm exec ng build --configuration development 2>&1 | tail -10
```

Expected: `Application bundle generation complete.` with no TS or template errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/pages/video-editor/video-editor.component.ts \
        frontend/src/app/pages/video-editor/video-editor.component.html \
        frontend/src/app/pages/video-editor/video-editor.component.scss
git commit -m "feat(video-editor): add trim source panel and cut markers

New 'Trim source video' panel above the segment actions on the
Segment Video tab. Mark Cut Start / Cut End add CutRange entries
shown as a list and as red overlays on both the seek bar and the
timeline. 'Save trimmed as new video' calls DAM /trim, then uploads
the result as a sibling VideoItem in the same subpart with a
'<name>_trimmed.mp4' label. Snackbar 'Open' action navigates to the
new video. State resets when navigating between videos.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: End-to-end manual smoke

**Files:** none modified — this task is verification only.

Per repository CLAUDE rule: UI work must be exercised in a browser before being declared done.

- [ ] **Step 1: Start everything**

In separate shells:

```bash
# DAM server
cd describe-anything && python dam_server.py

# Backend (whatever you normally use, e.g.)
cd backend && python app.py

# Frontend dev server
cd frontend && pnpm start
```

Open `http://localhost:4200` and sign in.

- [ ] **Step 2: Golden path — one cut**

1. Pick a project / subpart with a video ≥ ~15 s. Open it in the editor.
2. Land on the **Segment Video** tab. Verify the **Trim source video** panel appears above the Mark Start / Mark End / Add Segment row.
3. Scrub to ~5 s. Click **Mark cut start**. Verify a red vertical line appears at the playhead on both the seek bar and the timeline.
4. Scrub to ~8 s. Click **Mark cut end**. Verify a red translucent band fills [5, 8] on both bars, the list shows `0:05 → 0:08 (0:03)`, and the pending vertical line disappears.
5. Click **Save trimmed as new video**. Spinner / "Trimming…" label should appear.
6. On success: a success snackbar with an **Open** button. The project's subpart now has a new video named `<original>_trimmed.mp4` with duration `original − 3 s`.
7. Click **Open** → editor loads the trimmed video; scrubber shows the new shorter duration; the original video is still intact with its segments/regions/captions when revisited.

- [ ] **Step 3: Edge cases**

Run each, expecting the listed behavior:

1. **Mark End before Start** — click Mark cut end without a pending start. Snackbar: "Mark the cut start first". No state change.
2. **Pending start blocks Save** — Mark cut start only. Save button stays disabled.
3. **No cuts** — fresh load. Save button stays disabled.
4. **Whole-video cut** — Mark cut start at 0, Mark cut end at the very end. Click Save. Snackbar: "Cuts cover the whole video — nothing left to save". No DAM request fires.
5. **Two non-overlapping cuts** — add `[2, 4]` and `[10, 12]`. Save. New video duration ≈ `original − 4 s`.
6. **Overlapping cuts** — add `[5, 10]` and `[8, 15]`. Save. New video duration ≈ `original − 10 s` (server merges to `[5, 15]`).
7. **Remove a cut** — add two cuts, click × on one. List entry vanishes and overlay disappears from both bars.
8. **Navigate away during trim** — start a trim, immediately navigate to another video. No JS errors in console; trimmed video still appears in the source's subpart on the next page refresh.

- [ ] **Step 4: Cross-tab regression**

Briefly confirm the existing flows are untouched:
- Segment Video — Mark Start / Mark End / Add Segment / Auto Split still work.
- Object Region tab — segmentation still works.
- Captioning tab — caption generation still works.
- Next/Previous video navigation still works.

- [ ] **Step 5: Stop, declare done**

If all checks pass, the implementation is complete. No commit — this task is verification only.

If any check fails, file the failure as a follow-up — do not patch it into the existing commits unless it's a trivial typo.

---

## Roll-back

Each task above is a single commit. To unwind in reverse order:

```bash
git revert <task-4-commit> <task-3-commit> <task-2-commit> <task-1-commit>
```

The DAM `/trim` route is additive — removing it only affects the new feature.
