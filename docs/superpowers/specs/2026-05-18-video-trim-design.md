# Video Trim (Cut + Save) Design

Date: 2026-05-18
Status: Approved

## Goal

Let users trim out unwanted ranges from a source video — typically dead air or off-content sections — directly in the web editor and save the result as a new video in the project. Eliminates the round-trip through an external NLE (download → cut → export → re-upload).

## Scope

In scope:
- A "Trim source" panel on the existing **Segment Video** tab that lets the user mark one or more ranges to *remove* from the current video.
- A new `POST /trim` endpoint on `dam_server.py` that, given a source URL and a list of cut ranges, returns the trimmed video bytes (frame-accurate, re-encoded).
- Saving the trimmed bytes back to the project as a sibling video in the same subpart via the existing `POST /api/videos/upload`.

Out of scope:
- Persisting cut ranges in the database (they are scratch state on the editor page).
- Replacing the original video in-place (we always save as a new `VideoItem`).
- Frame-accurate scrubbing UI improvements — the existing timeline scrubber is reused as-is.
- Per-clip exports (one file per kept range). Output is always a single concatenated file.
- Re-trimming the trimmed video (works trivially since the trimmed video is just another `VideoItem`, but not a featured flow).
- Cancellation of an in-flight trim request.
- Generating a thumbnail for the trimmed video on upload. The `uploadVideo` call omits the `thumbnail` arg; the project grid will show its placeholder until the user opens the trimmed video (existing behavior for thumbnail-less videos).

## Why "remove" ranges (not "keep" ranges or reusing segments)

Three UX shapes were considered:

1. **Remove ranges** (chosen) — user marks dead spots; everything else is kept. Matches the source intent ("cut the part that doesn't have content"). Usually 1–3 marks for a typical video.
2. **Keep ranges** — user marks good spots; everything else is dropped. Requires more marks for the common case where most of the video is content.
3. **Reuse existing segments as keep ranges** — zero new UI, but conflates two distinct lifecycles: annotation segments carry IDs, regions, and captions; trim cuts are throwaway pre-processing. Trimming would force a decision about annotation units before the user is ready, and re-trimming would invalidate downstream annotation work.

Option 1 keeps trim as a clean pre-annotation step with no impact on segment/region/caption data.

## Why save-as-new (not replace)

Replacing the source in place would invalidate every existing segment, region, and caption timestamp on that video, requiring either a cascade-delete or a complex timestamp remap. Save-as-new sidesteps all of that: the original is untouched, the trimmed copy starts with a clean annotation slate, and the user can compare both if needed.

## Why re-encode (not stream-copy)

ffmpeg's `-c copy` mode is ~10× faster but can only cut on keyframes (a typical GOP of 1–2 s). For dead-air removal, snapping a cut to a keyframe up to 2 s away defeats the purpose — the user would still see/hear the dead audio at the seam. Re-encoding via `filter_complex trim+atrim+concat` is frame-accurate; the cost is roughly real-time (≈1× source duration). The trimmed video is then used for annotation, where accuracy matters more than the one-time encode wait.

## Backend

### Endpoint: `POST /trim` on `dam_server.py`

Mirrors the `/scene-detect` flow (download to temp → process → return → cleanup).

**Request:**

```json
{
  "video_url": "https://host/uploads/videos/<uuid>.mp4",
  "cut_ranges": [
    {"start_sec": 5.0, "end_sec": 12.3},
    {"start_sec": 45.0, "end_sec": 47.5}
  ]
}
```

**Response (success):** binary `video/mp4` (streamed) with header `Content-Disposition: attachment; filename="trimmed.mp4"`.

**Response (error):** `application/json` with `{"error": "..."}` and one of:
- `400` — `cut_ranges` empty, or cuts cover the entire video.
- `502` — failed to download source URL (timeout / non-2xx).
- `500` — ffmpeg non-zero exit (stderr tail included in `error`).

### Pydantic model

```python
class CutRange(BaseModel):
    start_sec: float
    end_sec: float

class TrimRequest(BaseModel):
    video_url: str
    cut_ranges: List[CutRange]
```

### Server-side logic

1. Validate `cut_ranges` non-empty (else 400).
2. Download source to a temp file (same `requests.get(..., stream=True, timeout=(5, 60))` shape as `/scene-detect`).
3. Probe duration with `ffprobe -v quiet -show_entries format=duration -of csv=p=0 <file>`.
4. Normalize `cut_ranges`:
   - For each range, clamp to `[0, duration]` and ensure `start_sec < end_sec` (drop zero-length / inverted).
   - Sort by `start_sec`.
   - Merge overlaps (`prev.end_sec >= curr.start_sec` → fold).
5. Compute **keep ranges** as the complement of normalized cuts within `[0, duration]`. If empty, return 400 `"nothing left after cuts"`.
6. Build an ffmpeg command with `filter_complex`:
   ```
   ffmpeg -y -i <src> -filter_complex
     "[0:v]trim=start=K1s:end=K1e,setpts=PTS-STARTPTS[v0];
      [0:a]atrim=start=K1s:end=K1e,asetpts=PTS-STARTPTS[a0];
      ...
      [v0][a0][v1][a1]...concat=n=N:v=1:a=1[outv][outa]"
     -map "[outv]" -map "[outa]" -c:v libx264 -preset veryfast -crf 20 -c:a aac <out>
   ```
   - `-preset veryfast -crf 20` balances size and encode time. Tunable later if file size becomes an issue.
7. Stream the output file back via FastAPI's `StreamingResponse` (`media_type="video/mp4"`).
8. `finally:` delete both temp files (source download and output). Match the `/scene-detect` try/finally cleanup style.

### Audio-less videos

If `ffprobe` shows no audio stream, drop the `atrim`/`a` filter halves and `concat=n=N:v=1:a=0` instead. (Detect via `ffprobe -select_streams a -show_streams`.)

### Why not stream the response with `-f mp4 pipe:1`?

Streaming the encode output directly back through HTTP would save the temp write, but the trimmed file is also useful to keep until the frontend confirms upload (so we could add retry without re-encoding in a future iteration). Writing to disk first is simpler and the cost is negligible.

## Frontend

### Where: existing video editor, Segment Video tab

Add a new "Trim source" panel above the segment marker toolbar in the Segment Video step of `video-editor.component.html`. The cuts lane sits below the existing segments lane on the same timeline track so the user sees segments and cuts together.

### Component state (scratch — no DB persistence)

In `video-editor.component.ts`:

```ts
interface CutRange { id: string; start: number; end: number; }

cutRanges: CutRange[] = [];
pendingCutStart: number | null = null;
trimming = false;
```

State is wiped by `resetState()` (the existing helper that clears `segments`, `segmentStart`, etc. when navigating between videos).

### Marker actions

Modeled on the existing `markSegmentStart` / `markSegmentEnd` / `addSegment` trio:

```ts
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
  this.cutRanges.push({ id: crypto.randomUUID(), start, end });
  this.pendingCutStart = null;
}

removeCut(id: string): void {
  this.cutRanges = this.cutRanges.filter(c => c.id !== id);
}
```

### Pure helpers (in `frontend/src/app/core/utils/cut-ranges.ts`, new file)

```ts
export interface CutRange { id?: string; start: number; end: number; }

export function normalizeCuts(cuts: CutRange[], duration: number): CutRange[] {
  return cuts
    .map(c => ({ ...c, start: Math.max(0, Math.min(c.start, c.end)), end: Math.min(duration, Math.max(c.start, c.end)) }))
    .filter(c => c.end - c.start > 0.001)
    .sort((a, b) => a.start - b.start)
    .reduce<CutRange[]>((acc, c) => {
      const last = acc[acc.length - 1];
      if (last && c.start <= last.end) {
        last.end = Math.max(last.end, c.end);
      } else {
        acc.push({ ...c });
      }
      return acc;
    }, []);
}

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

The keep-range computation lives client-side only for the disabled-state check (so the Save button knows when cuts cover the whole video). The server does its own normalization — frontend cannot be trusted.

### `saveTrimmed()` flow

```ts
saveTrimmed(): void {
  if (!this.video || this.trimming) return;
  if (this.cutRanges.length === 0) return;
  if (this.pendingCutStart !== null) return;

  const keeps = keepRanges(this.cutRanges, this.duration);
  if (keeps.length === 0) {
    this.snackBar.open('Cuts cover the whole video — nothing left to save', '', { duration: 3000 });
    return;
  }

  this.trimming = true;
  const ranges = this.cutRanges.map(c => ({ start_sec: c.start, end_sec: c.end }));
  const trimmedDuration = keeps.reduce((sum, k) => sum + (k.end - k.start), 0);

  this.videoService.trimVideo(this.video.url, ranges).subscribe({
    next: (blob) => {
      const trimmedName = this.deriveTrimmedName(this.video!.original_name);
      const file = new File([blob], trimmedName, { type: 'video/mp4' });
      if (!this.video!.project_id) {
        this.trimming = false;
        this.snackBar.open('Cannot save: source video has no project', '', { duration: 3000, panelClass: 'snack-error' });
        return;
      }
      this.videoService.uploadVideo(
        this.video!.project_id,
        file,
        this.video!.subpart_id,
        trimmedDuration
      ).subscribe({
        next: (res) => {
          this.trimming = false;
          this.snackBar.open(`Saved as '${trimmedName}'`, 'Open', { duration: 5000, panelClass: 'snack-success' })
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
      this.snackBar.open(`Trim failed: ${err.message || 'unknown error'}`, '', { duration: 4000, panelClass: 'snack-error' });
    }
  });
}

private deriveTrimmedName(original: string): string {
  const dot = original.lastIndexOf('.');
  const base = dot > 0 ? original.slice(0, dot) : original;
  return `${base}_trimmed.mp4`;
}
```

### Service: `VideoService.trimVideo` (delegates to DAM)

In `frontend/src/app/core/services/dam.service.ts`:

```ts
trimVideo(videoUrl: string, cutRanges: { start_sec: number; end_sec: number }[]): Observable<Blob> {
  const url = `${this.getDamUrl()}/trim`;
  let absoluteVideoUrl = videoUrl;
  if (!absoluteVideoUrl.startsWith('http')) {
    absoluteVideoUrl = window.location.origin + absoluteVideoUrl;
  }
  return this.http.post(url, { video_url: absoluteVideoUrl, cut_ranges: cutRanges }, { responseType: 'blob' }).pipe(
    catchError((err) => throwError(() => new Error(this.formatError(url, err))))
  );
}
```

URL absolutization is done here (not in the component) to mirror the existing `detectScenes` pattern in the same file.

In `frontend/src/app/core/services/video.service.ts`:

```ts
trimVideo(videoUrl: string, cutRanges: { start_sec: number; end_sec: number }[]): Observable<Blob> {
  return this.dam.trimVideo(videoUrl, cutRanges);
}
```

This mirrors the existing `segmentObject` / `detectScenes` delegation pattern.

### Template (panel HTML)

Add above the existing segment toolbar in `video-editor.component.html`:

```html
<div class="trim-panel" *ngIf="currentStep === 1">
  <div class="trim-header">
    <h4>Trim source video</h4>
    <span class="hint">Mark ranges to remove. Saved as a new video.</span>
  </div>
  <div class="trim-actions">
    <button mat-stroked-button (click)="markCutStart()">
      <mat-icon>content_cut</mat-icon> Mark cut start
    </button>
    <button mat-stroked-button (click)="markCutEnd()" [disabled]="pendingCutStart === null">
      <mat-icon>stop</mat-icon> Mark cut end
    </button>
    <button mat-flat-button color="warn"
            [disabled]="cutRanges.length === 0 || pendingCutStart !== null || trimming"
            (click)="saveTrimmed()">
      <mat-icon>save</mat-icon>
      <span *ngIf="!trimming">Save trimmed as new video</span>
      <span *ngIf="trimming">Trimming…</span>
    </button>
  </div>
  <ul class="cut-list" *ngIf="cutRanges.length > 0">
    <li *ngFor="let c of cutRanges">
      <span>{{ formatTime(c.start) }} → {{ formatTime(c.end) }} ({{ formatTime(c.end - c.start) }})</span>
      <button mat-icon-button (click)="removeCut(c.id)" [disabled]="trimming">
        <mat-icon>close</mat-icon>
      </button>
    </li>
  </ul>
</div>
```

### Timeline overlay

The existing timeline already paints segment markers. Add a red, semi-transparent overlay for each `CutRange` on the same track, positioned the same way as the segment markers (percentage of `duration`). The pending cut start (if any) gets a vertical red line. Mechanics mirror the existing segment overlay code in `video-editor.component.html` / `.scss` — no new abstraction needed.

## Data model

No schema changes. `cut_ranges` are scratch state on the component; the trimmed video is just another `videos` document inserted by the existing upload route, distinguished only by its `original_name` suffix.

## Error handling

**Frontend pre-submit (button states & inline messages):**
- No cuts → button disabled.
- Pending cut start with no end → button disabled.
- Cuts together cover entire video → snackbar at click time.
- Cut shorter than 50 ms → rejected with snackbar (user wobble on click).

**Server validation (`/trim`):**
- `cut_ranges` empty → 400 `"cut_ranges is required"`.
- After normalize, keep-ranges empty → 400 `"nothing left after cuts"`.
- Source download failure → 502 `"failed to fetch source video: <reason>"`.
- ffmpeg non-zero exit → 500 with last ~500 chars of stderr in the error body.
- Always cleanup temp files in `finally:`.

**Frontend post-trim:**
- DAM network/HTTP error → snackbar with server message if present, else generic.
- Backend upload error → snackbar "Trim succeeded but upload failed" (the trimmed blob is in memory and lost on retry; this is acceptable for v1 — retry would re-run the trim).

**During-trim UX:**
- Button shows "Trimming…" and disables itself.
- No cancellation in v1; if the user navigates away, the request continues on the DAM server but the result is discarded.

## Permissions

Same as everything else on the editor page. DAM `/trim` does not enforce auth (same as `/scene-detect`, `/segment`, `/chat/completions`); the backend `/api/videos/upload` is gated by `@token_required`, which is the actual save-side gate.

## Test plan

**Unit (frontend, pure):**
- `normalizeCuts` handles inverted (`end < start`), zero-length, out-of-range, overlapping, and adjacent inputs.
- `keepRanges` returns full `[0, duration]` for no cuts; returns `[]` for cuts spanning entire duration; returns correct complement for typical inputs.

**DAM `/trim` (manual smoke):**
- Single cut in the middle of a ~30 s test mp4 → output duration ≈ source − cut length; visual check that the seam is clean.
- Two non-overlapping cuts → arithmetic holds.
- Overlapping cuts (e.g. `5–10` + `8–15`) → behaves identically to a single `5–15` cut.
- Cuts covering the entire video → 400.
- Video without audio track → still produces a valid output.

**End-to-end (browser, manual):**
- Open a video in the editor → Trim panel visible only on Segment Video tab.
- Mark cut start without an end → Save button disabled.
- Mark a single cut → list entry shows correct timestamps.
- Click Save → spinner appears, new `VideoItem` appears in the same subpart's video list (verify via project page or the next/prev navigation), `original_name` is `"<source>_trimmed.mp4"`.
- Click the "Open" snackbar action → navigates to the trimmed video's editor, scrubber shows shorter duration.
- Original video still opens with its segments/regions/captions intact.

No pytest harness exists for `dam_server.py`; adding one for this single endpoint is not justified. The DAM checks above stay manual.

## Files touched

DAM server:
- `describe-anything/dam_server.py` — new `TrimRequest` / `CutRange` Pydantic models, new `/trim` route.

Frontend:
- `frontend/src/app/core/utils/cut-ranges.ts` — new file, `normalizeCuts` + `keepRanges`.
- `frontend/src/app/core/services/dam.service.ts` — new `trimVideo` method.
- `frontend/src/app/core/services/video.service.ts` — new `trimVideo` delegation.
- `frontend/src/app/pages/video-editor/video-editor.component.ts` — `cutRanges` / `pendingCutStart` / `trimming` state; `markCutStart`, `markCutEnd`, `removeCut`, `saveTrimmed`, `deriveTrimmedName` methods; reset in `resetState()`.
- `frontend/src/app/pages/video-editor/video-editor.component.html` — trim panel block and cuts-lane overlay on the timeline.
- `frontend/src/app/pages/video-editor/video-editor.component.scss` — styles for the trim panel and cuts-lane overlay (mirroring existing segment marker styles).

Backend: none.
