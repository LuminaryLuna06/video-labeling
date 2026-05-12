# Rename Video Design

Date: 2026-05-12
Status: Approved

## Goal

Let users rename the display name of an uploaded video — the label shown across the project grid, editor, and dialogs — without touching the underlying file on disk.

## Scope

In scope:
- Editing `videos.original_name` in MongoDB via an existing PUT endpoint.
- A rename action surfaced on each video card in the project detail page.

Out of scope:
- Renaming the on-disk `.mp4` (the storage filename is a UUID and is never user-facing).
- Renaming via the video editor page.
- Bulk rename.
- Audit / history of name changes.

## Why display-name-only

`videos` documents store two names:
- `filename` — UUID + extension, used as the disk filename and URL slug (`/uploads/videos/<filename>`).
- `original_name` — the friendly label rendered in the UI (`project-detail.component.html:298`, `:829`, `:852`, `:872`, and in delete/submit confirms).

The disk file is opaque to users. Renaming it would invalidate cached URLs and require a coordinated FS + DB write with rollback on partial failure. Keeping the rename to `original_name` is reversible, atomic (single document update), and matches how `original_name` is already used everywhere in the UI.

## Backend

### Endpoint

Reuse `PUT /api/videos/<video_id>` (`backend/routes/videos.py:891`, `update_video`). Add `original_name` to the accepted fields:

```python
if 'original_name' in data:
    name = (data['original_name'] or '').strip()
    if not name:
        return jsonify({'error': 'original_name must not be empty'}), 400
    update_fields['original_name'] = name
```

### Behavior

- Trim leading/trailing whitespace.
- Reject empty strings with HTTP 400.
- No extension enforcement — `original_name` is a label, not a path.
- Rename is **not** a content change: it must not be added to `content_fields` and must not trigger the auto-reset of `review_status` to `not_submitted`.
- Auth: rely on the existing `@token_required` decorator. No role gate, matching how tags / annotators / review_comment are already updatable through this same endpoint.

### Why not a separate PATCH `/<id>/name` endpoint

A separate endpoint would duplicate the lookup, ObjectId-coerce, and `updated_at` write that `update_video` already performs. The existing PUT is the canonical update path for the videos collection; adding one more allow-listed field is the cheapest correct change.

## Frontend

### Service

No changes. `VideoService.updateVideo(videoId, data)` (`frontend/src/app/core/services/video.service.ts:39`) already sends `Partial<VideoItem>` to `PUT /api/videos/<id>`.

### Card action button

In `project-detail.component.html` inside `video-actions-row` (currently at `:353`), insert a new icon button between **Edit Tags** and **Delete**:

```html
<button mat-icon-button (click)="openRenameDialog(video); $event.stopPropagation()"
        matTooltip="Rename video">
  <mat-icon>edit</mat-icon>
</button>
```

`$event.stopPropagation()` is required because the card's outer `(click)` opens the editor.

### Rename dialog

Add a dialog block at the bottom of `project-detail.component.html`, modeled on the existing "Assign Tags" dialog (`:827`):

```html
<div class="dialog-overlay" *ngIf="renamingVideo" (click)="closeRenameDialog()">
  <div class="dialog-card" (click)="$event.stopPropagation()">
    <h2>Rename Video</h2>
    <p class="dialog-subtitle">Current: {{ renamingVideo.original_name }}</p>
    <mat-form-field appearance="outline">
      <mat-label>New name</mat-label>
      <input matInput [(ngModel)]="renameValue" (keyup.enter)="saveRename()" cdkFocusInitial>
    </mat-form-field>
    <div class="dialog-actions">
      <button mat-button (click)="closeRenameDialog()">Cancel</button>
      <button mat-raised-button class="primary-btn"
              [disabled]="!renameValue.trim() || renameValue.trim() === renamingVideo.original_name"
              (click)="saveRename()">
        Save
      </button>
    </div>
  </div>
</div>
```

The Save button stays disabled when the input is empty or unchanged so the user can't no-op the dialog.

### Component logic

In `project-detail.component.ts`:

- New state:
  ```ts
  renamingVideo: VideoItem | null = null;
  renameValue = '';
  ```
- New methods:
  ```ts
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
        video.original_name = name; // optimistic local update so title flips before refetch returns
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

The local mutation of `video.original_name` is a small UX nicety so the title updates even before the list refetch completes; the refetch is still issued for consistency with how `deleteVideo` and `assignTags` patterns refresh.

## Data model

No schema migration. `original_name` already exists on every video document (set at upload time, `routes/videos.py:649`).

## Error handling

- Empty / whitespace-only input → client-side disables Save; server-side returns 400.
- Network / 5xx → snackbar with the server message if present, else a generic "Failed to rename video".
- 404 (video deleted by someone else mid-rename) → surface the server message via snackbar; the next list refresh will drop the stale entry.

## Permissions

Matches the rest of the PUT endpoint: any authenticated user. If finer control is needed later, the gate belongs on the whole endpoint, not on the rename branch.

## Test plan

Backend:
- `PUT /api/videos/<id>` with `{"original_name": "New name.mp4"}` updates the field; disk file at `uploads/videos/<filename>` is untouched.
- `PUT` with `{"original_name": "   "}` returns 400.
- `PUT` with `{"original_name": "..."}` on an approved video does not reset `review_status`.

Frontend (manual):
- Pencil icon appears in the card action row; clicking it does not navigate to the editor.
- Dialog opens prefilled with the current name; Save is disabled when empty or unchanged.
- After Save, the card title updates and a success snackbar appears.
- Cancel / overlay-click closes the dialog without sending a request.
- After rename, opening the editor shows the new name; deleting via the existing delete button still works.

## Files touched

Backend:
- `backend/routes/videos.py` — extend `update_video` (`:891`).

Frontend:
- `frontend/src/app/pages/project-detail/project-detail.component.html` — new icon button in `video-actions-row` + new rename dialog block.
- `frontend/src/app/pages/project-detail/project-detail.component.ts` — `renamingVideo`, `renameValue` state and three new methods.
