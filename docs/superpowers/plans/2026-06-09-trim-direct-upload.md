# Trim Direct Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `dam_server /trim → blob → frontend → backend upload` chain with `dam_server /trim → direct upload via forwarded JWT → return video record`. Frontend exchanges only KB-scale JSON.

**Architecture:** dam_server validates the user's forwarded JWT, encodes the trimmed video using the existing NVENC segment pipeline, generates a thumbnail with ffmpeg, then POSTs the result to backend `/api/videos/upload` carrying the same JWT. Backend's existing `@token_required` handles auth — zero backend changes.

**Tech Stack:** FastAPI (dam_server), PyJWT, ffmpeg/NVENC, httpx/requests for outbound multipart, Angular (frontend HttpClient already attaches JWT via existing global interceptor).

**Key design decisions resolved from spec open questions:**
- JWT algorithm: **HS256** with shared `SECRET_KEY` (matches `backend/utils/auth_middleware.py:21`)
- Frontend interceptor: existing `authInterceptor` at `frontend/src/app/core/interceptors/auth.interceptor.ts` already attaches `Authorization: Bearer <jwt>` globally — no interceptor change needed
- Thumbnail timestamp: match current frontend behavior (`min(1.0, duration * 0.25)`, 320px wide, JPEG quality ~80) — see `frontend/src/app/core/utils/video-thumbnail.ts`
- Semaphore size: default `2`, env-configurable via `TRIM_CONCURRENCY`
- NVENC params: keep current `-preset p4 -cq 20` (already in place from commit 7f8f6c8)
- Rate limit: deferred to future work; semaphore is the only concurrency control in this iteration

**Execution note (2026-06-09):** Implementation was committed in `f26074d` and pushed to `origin/main`. Automated checks passed (`npx tsc --noEmit`, dam_server import smoke with `JWT_SECRET=test`, JWT helper smoke, and syntax compile). Manual browser/E2E checks with the real backend secret remain open.

---

## File Structure

**Modify:**
- `describe-anything/dam_server.py` — JWT verify helper, semaphore, extended `TrimRequest`, rewritten `/trim` flow, thumbnail/probe/upload helpers
- `describe-anything/requirements.txt` — add `PyJWT`
- `frontend/src/app/core/services/dam.service.ts` — change `trimVideo` signature/response
- `frontend/src/app/core/services/video.service.ts` — pass-through update
- `frontend/src/app/pages/video-editor/video-editor.component.ts` — simplify `saveTrimmed`, remove client-side thumbnail

**No changes:**
- `backend/routes/videos.py` — `/api/videos/upload` reused as-is
- `frontend/src/app/core/interceptors/auth.interceptor.ts` — already global, attaches JWT to dam_server requests too

---

## Phase 1: dam_server side

### Task 1: Add PyJWT dependency

**Files:**
- Modify: `describe-anything/requirements.txt`

- [x] **Step 1: Add PyJWT to requirements**

Edit `describe-anything/requirements.txt`. Add this line under the existing FastAPI section (after `pydantic>=2.0.0`):

```
PyJWT>=2.8.0
```

- [x] **Step 2: Install in the dam_server environment**

Run on the WSL/server host where dam_server runs:

```bash
pip install PyJWT>=2.8.0
```

Expected: package installs without errors. Verify:

```bash
python -c "import jwt; print(jwt.__version__)"
```

- [ ] **Step 3: Commit**

```bash
git add describe-anything/requirements.txt
git commit -m "build(dam-server): add PyJWT dependency for forwarded JWT verification"
```

---

### Task 2: Add JWT verification helper

**Files:**
- Modify: `describe-anything/dam_server.py` — add near the existing helpers around line 367 (`_fmt_size`)

- [x] **Step 1: Add config + helper function**

Open `describe-anything/dam_server.py`. After the imports block (around line 55, after the `scenedetect` import), add:

```python
import jwt as _jwt  # PyJWT
```

Then near the other small helpers (after `_fmt_size`, around line 367), add:

```python
# JWT config — must match the backend's signing key/algorithm.
# Reads at startup; fail-fast if missing.
JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET env var is required. It must match the backend's Config.SECRET_KEY."
    )


def _verify_jwt(authorization_header: Optional[str]) -> dict:
    """Extract and verify a bearer JWT. Returns decoded payload (e.g. {'user_id': ..., 'exp': ...}).
    Raises ValueError with a short message on any failure."""
    if not authorization_header:
        raise ValueError("missing Authorization header")
    parts = authorization_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise ValueError("Authorization header must be 'Bearer <token>'")
    token = parts[1]
    try:
        return _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except _jwt.ExpiredSignatureError:
        raise ValueError("token expired")
    except _jwt.InvalidTokenError as e:
        raise ValueError(f"invalid token: {e}")
```

- [ ] **Step 2: Write a smoke test script**

Create `describe-anything/_smoke_jwt.py`:

```python
"""Standalone smoke test for _verify_jwt. Run: JWT_SECRET=test python _smoke_jwt.py"""
import os
os.environ.setdefault("JWT_SECRET", "test-secret")

import jwt
import time
from dam_server import _verify_jwt

SECRET = os.environ["JWT_SECRET"]

# Valid token
good_token = jwt.encode({"user_id": "abc", "exp": int(time.time()) + 60}, SECRET, algorithm="HS256")
payload = _verify_jwt(f"Bearer {good_token}")
assert payload["user_id"] == "abc", f"expected user_id=abc, got {payload}"
print("OK: valid token decoded")

# Missing header
try:
    _verify_jwt(None)
    raise AssertionError("expected ValueError on missing header")
except ValueError as e:
    assert "missing" in str(e).lower()
    print(f"OK: missing header rejected ({e})")

# Wrong scheme
try:
    _verify_jwt("Basic abc")
    raise AssertionError("expected ValueError on wrong scheme")
except ValueError as e:
    assert "bearer" in str(e).lower()
    print(f"OK: wrong scheme rejected ({e})")

# Expired token
expired = jwt.encode({"user_id": "abc", "exp": int(time.time()) - 1}, SECRET, algorithm="HS256")
try:
    _verify_jwt(f"Bearer {expired}")
    raise AssertionError("expected ValueError on expired token")
except ValueError as e:
    assert "expired" in str(e).lower()
    print(f"OK: expired token rejected ({e})")

# Wrong signature
wrong = jwt.encode({"user_id": "abc", "exp": int(time.time()) + 60}, "other-secret", algorithm="HS256")
try:
    _verify_jwt(f"Bearer {wrong}")
    raise AssertionError("expected ValueError on bad signature")
except ValueError as e:
    print(f"OK: bad signature rejected ({e})")

print("\nAll JWT smoke tests passed.")
```

- [ ] **Step 3: Run smoke test**

```bash
cd describe-anything
JWT_SECRET=test-secret python _smoke_jwt.py
```

Expected output: 5 "OK:" lines, ending with "All JWT smoke tests passed."

The import will be slow (~5-10s) because `dam_server` pulls in torch/transformers, but model weights are loaded in the FastAPI lifespan handler — not at module import — so the smoke test works without GPU.

- [ ] **Step 4: Delete the smoke script**

```bash
rm describe-anything/_smoke_jwt.py
```

The script is a one-shot verification, not part of the production code.

- [ ] **Step 5: Commit**

```bash
git add describe-anything/dam_server.py
git commit -m "feat(dam-server): add JWT verification helper with fail-fast config"
```

---

### Task 3: Extend `TrimRequest` model

**Files:**
- Modify: `describe-anything/dam_server.py:133-135`

- [x] **Step 1: Replace `TrimRequest` definition**

Find lines 133-135:

```python
class TrimRequest(BaseModel):
    video_url: str
    cut_ranges: List[CutRange]
```

Replace with:

```python
class TrimRequest(BaseModel):
    video_url: str
    cut_ranges: List[CutRange]
    # Direct-upload params
    upload_url: str           # backend base URL, e.g. "https://annotator.stecom.vn"
    project_id: str
    target_name: str          # original_name for the new VideoItem
    subpart_id: Optional[str] = None
    duration_hint: Optional[float] = None
```

- [x] **Step 2: Verify by importing the module**

```bash
cd describe-anything
JWT_SECRET=test python -c "from dam_server import TrimRequest; print(TrimRequest.model_fields.keys())"
```

Expected: `dict_keys(['video_url', 'cut_ranges', 'upload_url', 'project_id', 'target_name', 'subpart_id', 'duration_hint'])`

- [ ] **Step 3: Commit**

```bash
git add describe-anything/dam_server.py
git commit -m "feat(dam-server): extend TrimRequest with upload params"
```

---

### Task 4: Add concurrency semaphore

**Files:**
- Modify: `describe-anything/dam_server.py` — near the JWT config block from Task 2

- [x] **Step 1: Add semaphore + env config**

Below the JWT config block, add:

```python
TRIM_CONCURRENCY = int(os.environ.get("TRIM_CONCURRENCY", "2"))
_trim_semaphore = asyncio.Semaphore(TRIM_CONCURRENCY)
```

- [x] **Step 2: Verify**

```bash
cd describe-anything
JWT_SECRET=test python -c "from dam_server import TRIM_CONCURRENCY, _trim_semaphore; print(TRIM_CONCURRENCY, _trim_semaphore)"
```

Expected: `2 <asyncio.locks.Semaphore object at ...>`

Also verify env override:

```bash
JWT_SECRET=test TRIM_CONCURRENCY=4 python -c "from dam_server import TRIM_CONCURRENCY; print(TRIM_CONCURRENCY)"
```

Expected: `4`

- [ ] **Step 3: Commit**

```bash
git add describe-anything/dam_server.py
git commit -m "feat(dam-server): add concurrency semaphore for /trim"
```

---

### Task 5: Add output metadata probe helper

**Files:**
- Modify: `describe-anything/dam_server.py` — near `_probe_duration` and `_has_audio` (around lines 829-844)

- [x] **Step 1: Add helper**

After `_has_audio` (line 844), add:

```python
def _probe_video_meta(path: str) -> dict:
    """Return {'width': int, 'height': int, 'duration': float} for the given file."""
    out = subprocess.run(
        ["ffprobe", "-v", "quiet",
         "-select_streams", "v:0",
         "-show_entries", "stream=width,height:format=duration",
         "-of", "json", path],
        capture_output=True, text=True, check=True
    )
    data = json.loads(out.stdout)
    stream = data["streams"][0] if data.get("streams") else {}
    fmt = data.get("format", {})
    return {
        "width": int(stream.get("width", 0) or 0),
        "height": int(stream.get("height", 0) or 0),
        "duration": float(fmt.get("duration", 0.0) or 0.0),
    }
```

- [ ] **Step 2: Verify with a sample file**

Find any `.mp4` on the system (use an existing one):

```bash
cd describe-anything
JWT_SECRET=test python -c "
from dam_server import _probe_video_meta
import sys
print(_probe_video_meta(sys.argv[1]))
" /path/to/sample.mp4
```

Expected: `{'width': 1920, 'height': 1080, 'duration': 12.34}` (numbers will vary).

- [ ] **Step 3: Commit**

```bash
git add describe-anything/dam_server.py
git commit -m "feat(dam-server): add _probe_video_meta helper for upload metadata"
```

---

### Task 6: Add thumbnail generation helper

**Files:**
- Modify: `describe-anything/dam_server.py` — after `_probe_video_meta`

- [x] **Step 1: Add helper**

```python
def _make_thumbnail(src_path: str, duration: float) -> str:
    """Generate a JPEG thumbnail matching the frontend's behavior
    (seek to min(1.0, duration*0.25), width 320). Returns the temp file path."""
    seek = min(1.0, max(0.0, duration * 0.25))
    fd, thumb_path = tempfile.mkstemp(suffix=".jpg", prefix="trim_thumb_")
    os.close(fd)
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{seek}",
        "-i", src_path,
        "-frames:v", "1",
        "-vf", "scale=320:-2",
        "-q:v", "4",
        thumb_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        # Cleanup and re-raise — caller will treat as fatal
        try:
            os.remove(thumb_path)
        except OSError:
            pass
        raise RuntimeError(f"thumbnail generation failed: {(proc.stderr or '')[-300:]}")
    return thumb_path
```

- [ ] **Step 2: Verify with a sample file**

```bash
cd describe-anything
JWT_SECRET=test python -c "
from dam_server import _make_thumbnail, _probe_video_meta
import sys, os
meta = _probe_video_meta(sys.argv[1])
thumb = _make_thumbnail(sys.argv[1], meta['duration'])
print(f'thumb: {thumb}, size: {os.path.getsize(thumb)} bytes')
os.remove(thumb)
" /path/to/sample.mp4
```

Expected: prints thumb path and size > 0 bytes; no exceptions.

- [ ] **Step 3: Commit**

```bash
git add describe-anything/dam_server.py
git commit -m "feat(dam-server): add _make_thumbnail helper matching frontend timing"
```

---

### Task 7: Add upload-to-backend helper

**Files:**
- Modify: `describe-anything/dam_server.py` — after `_make_thumbnail`

- [x] **Step 1: Add helper**

```python
def _upload_to_backend(
    upload_url: str,
    bearer_token: str,
    video_path: str,
    thumb_path: str,
    project_id: str,
    subpart_id: Optional[str],
    width: int,
    height: int,
    duration: float,
) -> tuple[int, dict | str]:
    """POST the trimmed video + thumbnail to {upload_url}/api/videos/upload.
    Returns (status_code, parsed_json_or_raw_text)."""
    endpoint = upload_url.rstrip("/") + "/api/videos/upload"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    data = {
        "project_id": project_id,
        "duration": str(duration),
        "width": str(width),
        "height": str(height),
    }
    if subpart_id:
        data["subpart_id"] = subpart_id
    with open(video_path, "rb") as vf, open(thumb_path, "rb") as tf:
        files = {
            "video": ("trimmed.mp4", vf, "video/mp4"),
            "thumbnail": ("thumb.jpg", tf, "image/jpeg"),
        }
        # Long read timeout for slow backend uploads
        resp = requests.post(endpoint, headers=headers, data=data, files=files, timeout=(30, 600))
    try:
        return resp.status_code, resp.json()
    except ValueError:
        return resp.status_code, resp.text
```

**Note on `original_name`**: backend derives `original_name` from `file.filename` (the multipart filename, set above to `"trimmed.mp4"`). To preserve the user's chosen `target_name`, change `"trimmed.mp4"` to the actual target name passed from the request. We thread `target_name` in via the endpoint — see Task 8.

Update the helper signature to accept `target_name` and use it as the multipart filename:

```python
def _upload_to_backend(
    upload_url: str,
    bearer_token: str,
    video_path: str,
    thumb_path: str,
    project_id: str,
    subpart_id: Optional[str],
    target_name: str,           # <-- new
    width: int,
    height: int,
    duration: float,
) -> tuple[int, dict | str]:
    endpoint = upload_url.rstrip("/") + "/api/videos/upload"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    data = {
        "project_id": project_id,
        "duration": str(duration),
        "width": str(width),
        "height": str(height),
    }
    if subpart_id:
        data["subpart_id"] = subpart_id
    with open(video_path, "rb") as vf, open(thumb_path, "rb") as tf:
        files = {
            "video": (target_name, vf, "video/mp4"),
            "thumbnail": ("thumb.jpg", tf, "image/jpeg"),
        }
        resp = requests.post(endpoint, headers=headers, data=data, files=files, timeout=(30, 600))
    try:
        return resp.status_code, resp.json()
    except ValueError:
        return resp.status_code, resp.text
```

- [x] **Step 2: Verify the helper imports without errors**

```bash
cd describe-anything
JWT_SECRET=test python -c "from dam_server import _upload_to_backend; print(_upload_to_backend.__name__)"
```

Expected: `_upload_to_backend`

- [ ] **Step 3: Commit**

```bash
git add describe-anything/dam_server.py
git commit -m "feat(dam-server): add _upload_to_backend helper for direct multipart POST"
```

---

### Task 8: Rewrite `/trim` endpoint

**Files:**
- Modify: `describe-anything/dam_server.py:871-960` (the current `/trim` endpoint)

- [x] **Step 1: Replace the endpoint**

Replace the entire `@app.post("/trim")` block (starting around line 871) with:

```python
@app.post("/trim")
async def trim_video(req: TrimRequest, request: Request):
    # 0. Verify forwarded JWT before doing any work.
    try:
        jwt_payload = _verify_jwt(request.headers.get("Authorization"))
    except ValueError as e:
        return JSONResponse(status_code=401, content={"error": str(e)})

    if not req.cut_ranges:
        return JSONResponse(status_code=400, content={"error": "cut_ranges is required"})

    bearer_token = request.headers["Authorization"].split()[1]
    src_path = None
    out_path = None
    thumb_path = None
    seg_paths: List[str] = []
    list_path = None

    # Wait for a free slot in the GPU queue.
    async with _trim_semaphore:
        try:
            # 1. Download source
            try:
                print(f"[trim] user={jwt_payload.get('user_id')} downloading {req.video_url}")
                r = requests.get(req.video_url, stream=True, timeout=(5, 60))
                r.raise_for_status()
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                    for chunk in r.iter_content(chunk_size=8192):
                        tmp.write(chunk)
                    src_path = tmp.name
            except Exception as e:
                return JSONResponse(status_code=502, content={"error": f"failed to fetch source video: {e}"})

            # 2. Probe source
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

            # 4. NVENC segment encodes
            for i, (s, e) in enumerate(keeps):
                seg_fd, seg_path = tempfile.mkstemp(suffix=".mp4", prefix=f"trim_seg_{i}_")
                os.close(seg_fd)
                seg_paths.append(seg_path)
                cmd = [
                    "ffmpeg", "-y",
                    "-hwaccel", "cuda",
                    "-hwaccel_output_format", "cuda",
                    "-i", src_path,
                    "-ss", f"{s}", "-to", f"{e}",
                    "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "20",
                ]
                if with_audio:
                    cmd += ["-c:a", "aac"]
                cmd.append(seg_path)
                print(f"[trim] segment {i+1}/{len(keeps)} [{s:.3f}-{e:.3f}]")
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.returncode != 0:
                    tail = (proc.stderr or "")[-500:]
                    return JSONResponse(status_code=500, content={"error": f"ffmpeg segment {i} failed: {tail}"})

            # 5. Concat (stream-copy)
            list_fd, list_path = tempfile.mkstemp(suffix=".txt", prefix="trim_list_")
            with os.fdopen(list_fd, "w") as f:
                for p in seg_paths:
                    f.write(f"file '{p}'\n")
            out_fd, out_path = tempfile.mkstemp(suffix=".mp4", prefix="trim_out_")
            os.close(out_fd)
            concat_cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", list_path, "-c", "copy", out_path,
            ]
            print(f"[trim] concat {len(seg_paths)} segments")
            proc = subprocess.run(concat_cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                tail = (proc.stderr or "")[-500:]
                return JSONResponse(status_code=500, content={"error": f"ffmpeg concat failed: {tail}"})

            # 6. Probe output + thumbnail
            try:
                meta = _probe_video_meta(out_path)
            except subprocess.CalledProcessError as e:
                return JSONResponse(status_code=500, content={"error": f"ffprobe (output) failed: {e.stderr or e}"})

            try:
                thumb_path = _make_thumbnail(out_path, meta["duration"])
            except RuntimeError as e:
                return JSONResponse(status_code=500, content={"error": str(e)})

            # 7. Upload to backend with forwarded JWT
            print(f"[trim] uploading to {req.upload_url}/api/videos/upload")
            try:
                status, body = _upload_to_backend(
                    upload_url=req.upload_url,
                    bearer_token=bearer_token,
                    video_path=out_path,
                    thumb_path=thumb_path,
                    project_id=req.project_id,
                    subpart_id=req.subpart_id,
                    target_name=req.target_name,
                    width=meta["width"],
                    height=meta["height"],
                    duration=meta["duration"],
                )
            except requests.RequestException as e:
                return JSONResponse(status_code=502, content={"error": f"backend upload network error: {e}"})

            if status < 200 or status >= 300:
                body_str = body if isinstance(body, str) else json.dumps(body)
                return JSONResponse(
                    status_code=502,
                    content={"error": f"backend upload failed (HTTP {status}): {body_str[:500]}"},
                )

            return JSONResponse(status_code=200, content=body if isinstance(body, dict) else {"raw": body})

        except Exception as e:
            traceback.print_exc()
            return JSONResponse(status_code=500, content={"error": str(e)})

        finally:
            # Cleanup all temp files (src + segments + list + out + thumb)
            for path in [src_path, out_path, thumb_path, list_path, *seg_paths]:
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception as ex:
                        print(f"[trim] warning: failed to delete {path}: {ex}")
```

**Note on changes from the previous version:**
- Endpoint now takes `request: Request` (FastAPI inject) to read `Authorization` header
- Removed `StreamingResponse` and `file_iter` — output never returned to client
- Output file is now always cleaned up in `finally` (no ownership transfer to streaming response)
- Adds semaphore wrap

- [x] **Step 2: Verify imports still work**

```bash
cd describe-anything
JWT_SECRET=test python -c "from dam_server import app, trim_video; print('OK')"
```

Expected: `OK` (no import errors).

- [ ] **Step 3: Start the server**

```bash
cd describe-anything
JWT_SECRET=<the actual backend SECRET_KEY> python dam_server.py
```

Use the SAME `SECRET_KEY` value the backend uses (`backend/config.py` or `.env`). The server should start and bind to its usual port.

- [ ] **Step 4: Smoke test with curl (no upload params → expect 401 or 422)**

In a separate terminal:

```bash
curl -i -X POST http://localhost:8000/trim \
  -H "Content-Type: application/json" \
  -d '{"video_url":"http://example.com/x.mp4","cut_ranges":[{"start_sec":0,"end_sec":1}]}'
```

Expected: `422 Unprocessable Entity` (missing required fields `upload_url`, `project_id`, `target_name`).

Then test missing auth:

```bash
curl -i -X POST http://localhost:8000/trim \
  -H "Content-Type: application/json" \
  -d '{"video_url":"http://example.com/x.mp4","cut_ranges":[{"start_sec":0,"end_sec":1}],"upload_url":"http://localhost:5000","project_id":"abc","target_name":"x.mp4"}'
```

Expected: `401` with `{"error": "missing Authorization header"}`.

- [ ] **Step 5: Stop the server**

`Ctrl-C` in the server terminal.

- [ ] **Step 6: Commit**

```bash
git add describe-anything/dam_server.py
git commit -m "feat(dam-server): /trim uploads directly to backend with forwarded JWT"
```

---

## Phase 2: Frontend side

### Task 9: Update `DamService.trimVideo` signature

**Files:**
- Modify: `frontend/src/app/core/services/dam.service.ts:83-115` (the existing `trimVideo` method)

- [x] **Step 1: Add response type interface near the top of the file**

Open `dam.service.ts`. After the existing imports, add (if not already present):

```typescript
export interface TrimUploadResponse {
  id: string;
  filename: string;
  original_name: string;
  file_size: number;
  url: string;
  thumbnail_url: string;
  status: string;
  message?: string;
}

export interface TrimVideoOptions {
  videoUrl: string;
  cutRanges: { start_sec: number; end_sec: number }[];
  uploadUrl: string;
  projectId: string;
  targetName: string;
  subpartId?: string;
  durationHint?: number;
}
```

- [x] **Step 2: Replace the `trimVideo` method**

Replace the existing `trimVideo(videoUrl, cutRanges)` method (and its body) with:

```typescript
/**
 * Trim a source video via DAM. DAM encodes and uploads the result directly
 * to the backend using the user's forwarded JWT (attached by authInterceptor).
 * Returns the resulting backend video record.
 */
trimVideo(opts: TrimVideoOptions): Observable<TrimUploadResponse> {
  const url = `${this.getDamUrl()}/trim`;
  let absoluteVideoUrl = opts.videoUrl;
  if (!absoluteVideoUrl.startsWith('http')) {
    absoluteVideoUrl = window.location.origin + absoluteVideoUrl;
  }
  const body: any = {
    video_url: absoluteVideoUrl,
    cut_ranges: opts.cutRanges,
    upload_url: opts.uploadUrl,
    project_id: opts.projectId,
    target_name: opts.targetName,
  };
  if (opts.subpartId) body.subpart_id = opts.subpartId;
  if (opts.durationHint !== undefined) body.duration_hint = opts.durationHint;

  return this.http.post<TrimUploadResponse>(url, body).pipe(
    catchError((err) => {
      let msg = '';
      try {
        msg = typeof err?.error === 'string'
          ? err.error
          : (err?.error?.error || err?.message || '');
      } catch {
        msg = err?.message || '';
      }
      return throwError(() => new Error(msg || `DAM /trim failed (HTTP ${err?.status ?? '?'})`));
    })
  );
}
```

- [x] **Step 3: Verify compile**

```bash
cd frontend
npx tsc --noEmit
```

Expected: no errors. If there are unrelated pre-existing errors, ignore them; focus only on errors in `dam.service.ts` and its callers.

Expect compile errors in `video.service.ts` and `video-editor.component.ts` because we haven't updated the callers yet — that's the next tasks.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/core/services/dam.service.ts
git commit -m "feat(frontend): change DamService.trimVideo to return upload response"
```

---

### Task 10: Update `VideoService.trimVideo` pass-through

**Files:**
- Modify: `frontend/src/app/core/services/video.service.ts:27-33`

- [x] **Step 1: Replace the `trimVideo` method**

Find lines 27-33:

```typescript
  /**
   * Trim a source video via DAM and return the trimmed bytes.
   * Caller is responsible for wrapping the Blob in a File and calling uploadVideo().
   */
  trimVideo(videoUrl: string, cutRanges: { start_sec: number; end_sec: number }[]): Observable<Blob> {
    return this.dam.trimVideo(videoUrl, cutRanges);
  }
```

Replace with:

```typescript
  /**
   * Trim a source video via DAM. DAM uploads the result to the backend directly
   * using the user's forwarded JWT and returns the new video record.
   */
  trimVideo(opts: import('./dam.service').TrimVideoOptions): Observable<import('./dam.service').TrimUploadResponse> {
    return this.dam.trimVideo(opts);
  }
```

- [x] **Step 2: Verify compile**

```bash
cd frontend
npx tsc --noEmit
```

Expected: errors now only in `video-editor.component.ts` (the last consumer to fix).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/core/services/video.service.ts
git commit -m "feat(frontend): adapt VideoService.trimVideo to new options/response shape"
```

---

### Task 11: Simplify `video-editor.component.ts` `saveTrimmed`

**Files:**
- Modify: `frontend/src/app/pages/video-editor/video-editor.component.ts:615-664`

- [x] **Step 1: Replace the `saveTrimmed` method**

Find the `saveTrimmed()` method (starts around line 615). Replace the entire method body with:

```typescript
saveTrimmed(): void {
  if (!this.video || this.trimming || this.cutRanges.length === 0) return;
  if (this.pendingCutStart !== null) return;

  const keeps = keepRanges(this.cutRanges, this.duration);
  if (keeps.length === 0) {
    this.snackBar.open('Nothing left after cuts', '', { duration: 3000, panelClass: 'snack-error' });
    return;
  }

  const sourceVideo = this.video;
  if (!sourceVideo.project_id) {
    this.snackBar.open('Cannot save: source video has no project', '', { duration: 3000, panelClass: 'snack-error' });
    return;
  }

  this.trimming = true;
  const ranges = this.cutRanges.map(c => ({ start_sec: c.start, end_sec: c.end }));
  const trimmedDuration = keeps.reduce((sum, k) => sum + (k.end - k.start), 0);
  const targetName = this.deriveTrimmedName(sourceVideo.original_name);

  this.videoService.trimVideo({
    videoUrl: sourceVideo.url,
    cutRanges: ranges,
    uploadUrl: window.location.origin,
    projectId: sourceVideo.project_id!,
    targetName,
    subpartId: sourceVideo.subpart_id,
    durationHint: trimmedDuration,
  }).subscribe({
    next: (res) => {
      this.trimming = false;
      this.snackBar
        .open(`Saved as '${res.original_name}'`, 'Open', { duration: 5000, panelClass: 'snack-success' })
        .onAction().subscribe(() => this.router.navigate(['/editor', res.id]));
    },
    error: (err) => {
      this.trimming = false;
      this.snackBar.open(`Trim failed: ${err?.message || 'unknown error'}`, '', { duration: 4000, panelClass: 'snack-error' });
    }
  });
}
```

This removes the `generateThumbnail → wrap blob → uploadVideo` chain. dam_server now handles thumbnail + upload.

- [x] **Step 2: Remove the now-unused import (if no other usage)**

Check whether `generateThumbnail` is still referenced elsewhere in the file:

```bash
grep -n "generateThumbnail" frontend/src/app/pages/video-editor/video-editor.component.ts
```

If the only remaining match is the `import` line, remove the import:

```typescript
import { generateThumbnail } from '../../core/utils/video-thumbnail';
```

If there are other usages (e.g., other features still call it), leave the import alone.

- [x] **Step 3: Verify compile**

```bash
cd frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Run the dev server**

```bash
cd frontend
npm run start
```

Wait for "Application bundle generation complete" and the dev server URL.

- [ ] **Step 5: Manual browser test**

Open the dev server URL, log in, navigate to a project, open a video in the editor, set 1-2 cut ranges, click "Save trimmed".

Expected:
- Spinner shows briefly
- Snackbar: "Saved as 'X_trimmed.mp4'"
- Clicking "Open" navigates to the new video

In DevTools Network tab:
- The `POST /trim` request should return JSON (NOT a Blob) with shape `{id, url, ...}`
- No subsequent `POST /api/videos/upload` request from the browser
- Browser memory should not balloon during the operation

- [ ] **Step 6: Stop the dev server**

`Ctrl-C` in the dev server terminal.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/pages/video-editor/video-editor.component.ts
git commit -m "feat(frontend): saveTrimmed uses direct upload, removes client-side thumbnail"
```

---

## Phase 3: Final verification

### Task 12: End-to-end integration test

**Files:** none

- [ ] **Step 1: Start dam_server with the real backend secret**

```bash
cd describe-anything
JWT_SECRET=<actual SECRET_KEY> python dam_server.py
```

- [ ] **Step 2: Start frontend**

```bash
cd frontend
npm run start
```

- [ ] **Step 3: Full user flow**

In a browser, with both servers running:

1. Log in as a real user
2. Open a project with a video
3. Open the video in the editor
4. Mark 2-3 cut ranges
5. Click "Save trimmed"
6. Wait for the snackbar
7. Click "Open" → navigates to new video
8. Confirm:
   - New video plays correctly (frame-accurate cuts)
   - Thumbnail is visible in the project grid
   - `uploaded_by` in MongoDB matches the logged-in user (check via DB or a project listing API)

- [ ] **Step 4: Failure-mode tests**

- **Expired JWT**: simulate by editing browser localStorage to use a manually-crafted expired token. Click "Save trimmed" → expect snackbar "token expired".
- **Wrong project_id**: temporarily edit `sourceVideo.project_id` in DevTools → expect snackbar from backend's "Project not found".

- [ ] **Step 5: Capture metrics**

For a real 5-minute trim job, note:
- Wall clock duration of `/trim` request (Network tab)
- Browser memory during the request (DevTools → Performance / Memory)
- VRAM during the request (`nvidia-smi` on the dam_server host)

Record these in the commit message of the final commit so future you knows the baseline.

- [ ] **Step 6: Commit (final wrap-up if any tweaks)**

If any tweaks were needed during integration testing:

```bash
git add <files>
git commit -m "fix(dam-server): <specific fix>"
```

Otherwise, skip this step.

---

### Task 13: Push

- [ ] **Step 1: Confirm clean state**

```bash
git status
```

Expected: `nothing to commit, working tree clean`.

- [ ] **Step 2: Push all commits**

```bash
git push origin main
```

Expected: commits from this plan land on `origin/main`.

---

## Operational notes for deployment

The implementation depends on two environment variables on the dam_server host. They must be set before starting `python dam_server.py`:

```
JWT_SECRET=<same value as backend Config.SECRET_KEY>
JWT_ALGORITHM=HS256              # optional, defaults to HS256
TRIM_CONCURRENCY=2               # optional, defaults to 2
```

If you use a process manager (systemd, supervisor, pm2), add these to the unit/config file. If you run inside Docker, add to the container env.

The existing CORS allowlist in `dam_server.py:360` already includes the frontend domains — no change needed there.

## What's NOT included (deliberately deferred)

- **Async subprocess**: `subprocess.run` still blocks the FastAPI event loop. Per-request blocking is bounded by the semaphore (max 2), but a true async refactor (`asyncio.create_subprocess_exec`) is a separate concern — file a follow-up.
- **Rate limit per user**: only the semaphore caps concurrency. No quota or token-bucket.
- **Progress streaming**: client sees a single spinner, no SSE/WebSocket progress.
- **Retry on transient upload failure**: a 502 surfaces as an error to the user, who must re-trigger.
