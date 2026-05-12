# Rename Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users rename a video's display name (`original_name`) from the project detail page; the on-disk file is untouched.

**Architecture:** Extend the existing `PUT /api/videos/<id>` endpoint to accept `original_name` (single MongoDB field update). Add a pencil-icon button to each video card in the project detail page that opens a small dialog (mirrors the existing "Assign Tags" dialog pattern), POSTing the new name through `VideoService.updateVideo()`.

**Tech Stack:** Flask + PyMongo (backend), Angular 17 standalone components + Angular Material + RxJS (frontend).

**Spec:** `docs/superpowers/specs/2026-05-12-rename-video-design.md`

**No automated tests:** The project has no pytest setup for backend routes and no karma/jest setup for these Angular pages. Verification is by curl (backend) and browser smoke test (frontend), matching how features in this repo are currently shipped.

---

## File Structure

**Backend (modify):**
- `backend/routes/videos.py` — add an `original_name` branch inside `update_video()` (around line 911 with the other `if 'X' in data:` blocks). Single responsibility: one new allow-listed field with trim + empty-check.

**Frontend (modify):**
- `frontend/src/app/pages/project-detail/project-detail.component.ts` — three small additions co-located with the existing video-card dialog state (next to `editingVideo` / `annotatorVideo` near the top of the class): two new properties and three new methods.
- `frontend/src/app/pages/project-detail/project-detail.component.html` — one new icon button in the `video-actions-row` (near `:353`) and one new dialog block at the bottom of the file alongside the other dialogs (near `:846`).

No new files. No service changes — `VideoService.updateVideo()` already sends `Partial<VideoItem>`.

---

## Task 1: Backend — accept `original_name` in PUT /api/videos/:id

**Files:**
- Modify: `backend/routes/videos.py:910-931` (the body of `update_video`, inside the `if '...' in data:` chain)

- [ ] **Step 1: Skim the existing `update_video` function**

Read `backend/routes/videos.py:891-946` so you can place the new branch consistently. Notice that `content_changed = False` is set above the chain and individual branches set it to `True` for fields that should reset approval. `original_name` must NOT set `content_changed = True` — renaming is metadata-only and a rename of an approved video should remain approved.

- [ ] **Step 2: Add the `original_name` branch**

Insert this block in `backend/routes/videos.py` immediately after the `if 'duration' in data:` block (currently at line 910), keeping the file's existing 4-space indentation:

```python
    if 'original_name' in data:
        name = (data.get('original_name') or '').strip()
        if not name:
            return jsonify({'error': 'original_name must not be empty'}), 400
        update_fields['original_name'] = name
```

Notes:
- `data.get('original_name') or ''` defends against `None` being sent explicitly.
- `.strip()` matches how `secure_filename` collapses surrounding whitespace at upload time.
- 400 is returned before any DB write so a bad rename can't half-apply.
- Do NOT touch `content_changed` or `content_fields` — rename is not a content change.

- [ ] **Step 3: Start the backend**

```powershell
cd D:\Jupiter\video-labeling\backend; python app.py
```

Leave it running in a second terminal. (If `python app.py` isn't how this repo is normally started, use whatever command you find in `backend/Dockerfile` or `README` — the Dockerfile's CMD is the source of truth.)

- [ ] **Step 4: Pick a real video ID and auth token**

You need a JWT and a video id. Open the running web app in a browser, log in, open DevTools → Application → Local Storage, copy the `token` value. Pick any video from the project grid, open its editor, and copy the id from the URL.

Export them into the shell where you'll run curl:

```powershell
$TOKEN = "<paste token>"
$VID = "<paste video id>"
```

- [ ] **Step 5: Verify the happy path**

```powershell
curl -s -X PUT "http://localhost:5000/api/videos/$VID" `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"original_name":"renamed-by-curl.mp4"}'
```

Expected response body:

```json
{"message": "Video updated successfully"}
```

Then fetch the video back and confirm the field updated:

```powershell
curl -s "http://localhost:5000/api/videos/$VID" -H "Authorization: Bearer $TOKEN" | ConvertFrom-Json | Select-Object original_name, filename
```

Expected: `original_name` is `renamed-by-curl.mp4`, and `filename` is unchanged (still the original UUID + extension).

Also confirm the underlying disk file still exists at its UUID name:

```powershell
Test-Path "D:\Jupiter\video-labeling\backend\uploads\videos\$(curl -s "http://localhost:5000/api/videos/$VID" -H "Authorization: Bearer $TOKEN" | ConvertFrom-Json | Select-Object -ExpandProperty filename)"
```

Expected: `True`.

- [ ] **Step 6: Verify empty-name rejection**

```powershell
curl -s -o response.json -w "%{http_code}" -X PUT "http://localhost:5000/api/videos/$VID" `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"original_name":"   "}'
```

Expected output: `400`. Open `response.json` — body should be `{"error": "original_name must not be empty"}`.

- [ ] **Step 7: Verify rename does not reset approval**

Pick an approved video (or first approve one through the UI). Grab its `review_status` before rename:

```powershell
curl -s "http://localhost:5000/api/videos/$VID" -H "Authorization: Bearer $TOKEN" | ConvertFrom-Json | Select-Object review_status
```

Rename it:

```powershell
curl -s -X PUT "http://localhost:5000/api/videos/$VID" `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"original_name":"approved-then-renamed.mp4"}'
```

Re-fetch and confirm `review_status` is still `approved`:

```powershell
curl -s "http://localhost:5000/api/videos/$VID" -H "Authorization: Bearer $TOKEN" | ConvertFrom-Json | Select-Object review_status
```

Expected: still `approved`. If it's `not_submitted`, you accidentally added `original_name` to `content_fields` or set `content_changed = True` — go back to Step 2.

- [ ] **Step 8: Restore the test video's original name**

```powershell
curl -s -X PUT "http://localhost:5000/api/videos/$VID" `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"original_name":"<the original name you saw in Step 4>"}'
```

- [ ] **Step 9: Commit**

```powershell
cd D:\Jupiter\video-labeling; git add backend/routes/videos.py; git commit -m "feat(videos): allow renaming original_name via PUT /api/videos/<id>"
```

---

## Task 2: Frontend — rename dialog state and methods

**Files:**
- Modify: `frontend/src/app/pages/project-detail/project-detail.component.ts` (add two properties and three methods)

- [ ] **Step 1: Locate the existing dialog state**

Open `frontend/src/app/pages/project-detail/project-detail.component.ts` and find the cluster of properties named `editingVideo`, `videoTagIds`, `annotatorVideo`, `annotatorVideoIds`, `rejectingVideo`, `rejectComment` (they're together around the upper part of the class body — grep for `annotatorVideo` to find them quickly). You will add the rename state right after that group so all per-video dialog state stays co-located.

- [ ] **Step 2: Add the two new properties**

Insert these two lines immediately after the existing reject-dialog state (after the line declaring `rejectComment`):

```typescript
  // Rename Dialog
  renamingVideo: VideoItem | null = null;
  renameValue = '';
```

- [ ] **Step 3: Add the three methods**

Find an existing video-action method (for example `deleteVideo` or `openAnnotatorDialog`) and add these three methods nearby so related logic stays grouped. The exact insertion point doesn't matter as long as they're inside the class body:

```typescript
  openRenameDialog(video: VideoItem): void {
    this.renamingVideo = video;
    this.renameValue = video.original_name;
  }

  closeRenameDialog(): void {
    this.renamingVideo = null;
    this.renameValue = '';
  }

  saveRename(): void {
    if (!this.renamingVideo) return;
    const name = this.renameValue.trim();
    if (!name || name === this.renamingVideo.original_name) return;
    const video = this.renamingVideo;
    this.videoService.updateVideo(video.id, { original_name: name }).subscribe({
      next: () => {
        video.original_name = name;
        this.snackBar.open('Video renamed', 'Close', { duration: 2000, panelClass: 'snack-success' });
        this.closeRenameDialog();
        if (this.selectedSubpart) {
          this.loadSubpartVideos(this.selectedSubpart.id);
        }
      },
      error: (err) => {
        const msg = err?.error?.error || 'Failed to rename video';
        this.snackBar.open(msg, 'Close', { duration: 3000, panelClass: 'snack-error' });
      }
    });
  }
```

Notes:
- `video.original_name = name` is an optimistic local mutation so the card title flips before the refetch round-trip completes. Existing methods in this component already mutate `VideoItem` properties this way.
- `this.loadSubpartVideos(...)` is the same refresh call used by `deleteVideo` (`project-detail.component.ts:693`); it keeps tag chips, annotator chips, and pagination in sync.
- No new imports needed — `VideoItem`, `MatSnackBar`, and `VideoService` are already imported at the top of the file.

- [ ] **Step 4: Type-check by running the build (or `ng serve`)**

```powershell
cd D:\Jupiter\video-labeling\frontend; pnpm exec ng build --configuration development
```

Expected: build completes without TypeScript errors. (If `pnpm` is not installed, use `npm run build` or `npx ng build` — the project ships with both lockfiles.) If you see "Property 'renamingVideo' does not exist", you put the properties outside the class body — go back to Step 2.

- [ ] **Step 5: Commit**

```powershell
cd D:\Jupiter\video-labeling; git add frontend/src/app/pages/project-detail/project-detail.component.ts; git commit -m "feat(project-detail): add rename-video dialog state and saveRename handler"
```

---

## Task 3: Frontend — pencil-icon button and rename dialog markup

**Files:**
- Modify: `frontend/src/app/pages/project-detail/project-detail.component.html` (one new button inside `video-actions-row` around `:353`; one new dialog block near `:846`)

- [ ] **Step 1: Add the pencil-icon button to the video card**

Open `frontend/src/app/pages/project-detail/project-detail.component.html` and find the `video-actions-row` div (currently at line 353). It contains three buttons in this order: Assign Annotators (person_add), Edit Tags (label), Delete (delete).

Insert a new button between "Edit Tags" and "Delete". The block to insert is:

```html
              <button mat-icon-button (click)="openRenameDialog(video); $event.stopPropagation()"
                      matTooltip="Rename video">
                <mat-icon>edit</mat-icon>
              </button>
```

`$event.stopPropagation()` is required because the outer `.video-card` div has `(click)="openEditor(video)"` (line 288) — without it, clicking the pencil would also navigate into the editor.

After your edit, the `video-actions-row` should look like:

```html
            <div class="video-actions-row">
              <button mat-icon-button (click)="openAnnotatorDialog(video); $event.stopPropagation()"
                      matTooltip="Assign Annotators">
                <mat-icon>person_add</mat-icon>
              </button>
              <button mat-icon-button (click)="openVideoTagDialog(video); $event.stopPropagation()"
                      matTooltip="Edit Tags">
                <mat-icon>label</mat-icon>
              </button>
              <button mat-icon-button (click)="openRenameDialog(video); $event.stopPropagation()"
                      matTooltip="Rename video">
                <mat-icon>edit</mat-icon>
              </button>
              <button mat-icon-button (click)="deleteVideo(video); $event.stopPropagation()"
                      matTooltip="Delete video">
                <mat-icon>delete</mat-icon>
              </button>
            </div>
```

- [ ] **Step 2: Add the rename dialog block**

Find the "Video Tag Assignment Dialog" block (currently at line 825-846). It is the template for what the rename dialog should look like. Insert the following block immediately after the closing `</div>` of the Video Tag Assignment Dialog (so the rename dialog appears adjacent to the other per-video dialogs):

```html
<!-- Video Rename Dialog -->
<div class="dialog-overlay" *ngIf="renamingVideo" (click)="closeRenameDialog()">
  <div class="dialog-card" (click)="$event.stopPropagation()">
    <h2>Rename Video</h2>
    <p class="dialog-subtitle">Current: {{ renamingVideo?.original_name }}</p>
    <mat-form-field appearance="outline">
      <mat-label>New name</mat-label>
      <input matInput [(ngModel)]="renameValue" (keyup.enter)="saveRename()" cdkFocusInitial>
    </mat-form-field>
    <div class="dialog-actions">
      <button mat-button (click)="closeRenameDialog()">Cancel</button>
      <button mat-raised-button class="primary-btn"
              [disabled]="!renameValue.trim() || renameValue.trim() === renamingVideo?.original_name"
              (click)="saveRename()">
        Save
      </button>
    </div>
  </div>
</div>
```

Notes:
- `(click)="closeRenameDialog()"` on the overlay + `$event.stopPropagation()` on the inner card is the same overlay-dismiss pattern as the Tag and Annotator dialogs.
- `cdkFocusInitial` autofocuses the input when the dialog opens. The `MatDialogModule` import (already present in the component's `imports` array) brings in the CDK A11y directive; if the linter complains it's unknown, swap it for the slightly more verbose `#renameInput (ngModelChange)` + `@ViewChild` pattern, but try `cdkFocusInitial` first — it usually works in this codebase because Material is already wired up.
- `(keyup.enter)="saveRename()"` lets the user submit without reaching for the mouse. `saveRename()` already early-returns if the name is empty or unchanged, so Enter on an invalid value is a safe no-op.

- [ ] **Step 3: Build the frontend**

```powershell
cd D:\Jupiter\video-labeling\frontend; pnpm exec ng build --configuration development
```

Expected: build succeeds with no template errors. If you see `Can't bind to 'matTooltip'` or `'mat-icon-button' is not a known element`, the imports are fine (they're used elsewhere on this page) — re-check that your edits are inside `project-detail.component.html` and not accidentally in another file.

- [ ] **Step 4: Manual smoke test in the browser**

Start the dev server if it isn't already:

```powershell
cd D:\Jupiter\video-labeling\frontend; pnpm exec ng serve
```

Open the app in a browser, navigate to a project that has at least one uploaded video.

Verify, in order:

1. The pencil icon appears in the action row of every video card, between the tag icon and the trash icon.
2. Hovering shows the "Rename video" tooltip.
3. Clicking the pencil opens the rename dialog and does NOT navigate into the video editor. (If it does navigate, you forgot `$event.stopPropagation()` — go back to Step 1.)
4. The input is pre-filled with the current name and is autofocused.
5. With the input unchanged or whitespace-only, the Save button is disabled.
6. Type a new name and press Enter — the dialog closes, a green "Video renamed" snackbar appears, and the card title updates to the new name.
7. Click the pencil again, type a new name, click Cancel — the name does not change.
8. Click the pencil, type a new name, click the overlay (outside the card) — the name does not change.
9. After rename, click the card body — the editor opens and shows the new name in its header.
10. Refresh the page — the rename persists.
11. Click the trash icon — the existing delete confirm shows the new name and still works.

- [ ] **Step 5: Commit**

```powershell
cd D:\Jupiter\video-labeling; git add frontend/src/app/pages/project-detail/project-detail.component.html; git commit -m "feat(project-detail): rename button and dialog on video cards"
```

---

## Self-Review

**Spec coverage:**
- Backend: PUT accepts `original_name` with trim + empty check + no review reset → Task 1, Steps 2 & 7.
- Frontend service: no change needed → confirmed in spec; no task required.
- Frontend card action: pencil icon between Edit Tags and Delete → Task 3, Step 1.
- Frontend dialog: prefilled input, Save disabled when empty/unchanged, Enter to submit, overlay dismiss, snackbar feedback → Task 2 (logic) + Task 3 Step 2 (markup).
- Spec test plan items (3 backend, 6 frontend) are each covered by a verification step.

**Placeholder scan:** No TBDs, no "handle errors appropriately", no "similar to Task N". Every code step shows the actual code. Every command shows expected output.

**Type consistency:** `renamingVideo: VideoItem | null`, `renameValue: string`, `openRenameDialog(video: VideoItem)`, `closeRenameDialog()`, `saveRename()` are used identically in Task 2 (where they're defined) and Task 3 (where they're consumed in the template). `videoService.updateVideo` signature matches the existing method at `video.service.ts:39`.
