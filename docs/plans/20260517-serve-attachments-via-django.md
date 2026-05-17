# Serve Forum Attachments via Django View

## Overview

Replace direct media file serving of phpBB attachments with a dedicated Django view.

**Problem:** `PostAttachment.url` currently returns `/media/forum/attachments/{physical_filename}`.
phpBB stores attachment files without extensions (e.g. `16_96cbd839fd247f8d15e00f60e10d86ea`).
Django's media serving passes the file through without `Content-Disposition` or `Content-Type` headers,
so browsers download files without the original extension — `poloz-kol-2009.doc` arrives as a nameless blob.

**Fix:** A Django view at `/forum/a/<pk>/` that returns a `FileResponse` with
`as_attachment=True, filename=real_filename, content_type=mimetype`.
As a bonus, the view can enforce subforum access control on attachments
(important for future private-message attachment support).

## Context

- `apps/forum/models.py:153` — `PostAttachment` model; `.url` property at line 168
- `apps/forum/views.py` — existing `_can_access()` helper; `topic_posts`, `subforum_topics` views
- `apps/forum/urls.py` — forum URL patterns
- `apps/forum_import/management/commands/import_phpbb_attachments.py` — `_render_attachment_html()` generates the HTML stored in `post.text_html`; uses `att.url` to build `href`/`src`
- `apps/forum/tests.py` — existing forum tests

After `PostAttachment.url` changes, every `post.text_html` row in PostgreSQL will contain stale
`/media/forum/attachments/...` URLs. A management command re-renders them without MySQL.

## Development Approach

- **Testing approach:** Regular (code first, then tests)
- Complete each task fully before moving to the next
- All tests must pass before starting the next task

## Solution Overview

1. Change `PostAttachment.url` to return `/forum/a/{pk}/`
2. Add URL pattern and `serve_attachment` view with access control + `FileResponse`
3. Add management command `render_forum_attachments` to patch stale URLs in `post.text_html`
4. Update `CLAUDE.md` import workflow

No migrations needed — only model property and view changes.

## Technical Details

**`serve_attachment` view:**
```python
att = get_object_or_404(
    PostAttachment.objects.select_related("post__topic__subforum"), pk=pk
)
if not _can_access(request, att.post.topic.subforum):
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    return HttpResponseForbidden()
path = settings.MEDIA_ROOT / "forum" / "attachments" / os.path.basename(att.physical_filename)
return FileResponse(open(path, "rb"), as_attachment=True,
                    filename=att.real_filename,
                    content_type=att.mimetype or "application/octet-stream")
```

**`render_forum_attachments` command logic:**
- Iterate all `PostAttachment` objects grouped by `post`
- For each: `old_url = f"{settings.MEDIA_URL}forum/attachments/{basename(att.physical_filename)}"`
- Replace `old_url` with `att.url` (new property value) in `post.text_html`
- Save only changed posts via `update_fields=["text_html"]`
- Print: `Updated N posts`

## Implementation Steps

### Task 1: Change `PostAttachment.url` to Django view URL

**Files:**
- Modify: `apps/forum/models.py`

- [x] Change `PostAttachment.url` property to return `f"/forum/a/{self.pk}/"` instead of the `/media/...` path
- [x] Verify no other code depends on the old URL format (grep for `MEDIA_URL.*attachment` and `media/forum/attach`)
- [x] Write unit tests for the updated property: `PostAttachment.url` returns `/forum/a/{pk}/`
- [x] Run tests — must pass before Task 2

### Task 2: Add `serve_attachment` view and URL

**Files:**
- Modify: `apps/forum/views.py`
- Modify: `apps/forum/urls.py`

- [x] Add `serve_attachment(request, pk)` view to `apps/forum/views.py`:
  - `get_object_or_404` with `select_related("post__topic__subforum")`
  - Call `_can_access(request, att.post.topic.subforum)` — anon → `redirect_to_login`, forbidden → `HttpResponseForbidden`
  - Build file path: `settings.MEDIA_ROOT / "forum" / "attachments" / os.path.basename(att.physical_filename)`
  - Return `FileResponse(open(path, "rb"), as_attachment=True, filename=att.real_filename, content_type=att.mimetype or "application/octet-stream")`
- [x] Add URL pattern `path("a/<int:pk>/", views.serve_attachment, name="forum-attachment")` to `apps/forum/urls.py`
- [x] Write tests for `serve_attachment` in `apps/forum/tests.py`:
  - Public subforum: anonymous user gets file with correct `Content-Disposition` filename and `Content-Type`
  - Private subforum + anonymous: redirect to login
  - Private subforum + authenticated non-member: 403
  - Private subforum + member: 200 with file
  - Private subforum + staff: 200 with file
  - Non-existent pk: 404
- [x] Run tests — must pass before Task 3

### Task 3: Add `render_forum_attachments` management command

**Files:**
- Create: `apps/forum_import/management/commands/render_forum_attachments.py`

- [x] Create command that iterates all `PostAttachment` grouped by `post_id`
- [x] For each post, compute `old_url` from `settings.MEDIA_URL + "forum/attachments/" + basename(att.physical_filename)`, replace with `att.url`; handle multiple attachments per post in a single pass
- [x] Save only posts where `text_html` actually changed (`update_fields=["text_html"]`)
- [x] Print summary: `Updated N posts (M attachments)`
- [x] Write tests for the command in `apps/forum_import/tests.py`:
  - Post with one attachment: old URL replaced with new URL in `text_html`
  - Post with multiple attachments: all URLs replaced
  - Post with no attachment references (inline attachment already replaced in BBCode): no change
  - Post not in any changed set: `text_html` unchanged
- [x] Run tests — must pass before Task 4

### Task 4: Verify acceptance criteria

- [ ] Run full test suite: `uv run pytest`
- [ ] Manually confirm: `PostAttachment.url` returns `/forum/a/{pk}/`
- [ ] Manually confirm: `GET /forum/a/{pk}/` returns file with `Content-Disposition: attachment; filename="real_filename.ext"`
- [ ] Manually confirm: `render_forum_attachments` updates `post.text_html` rows

### Task 5: Update documentation

**Files:**
- Modify: `CLAUDE.md`
- Move: `docs/plans/20260517-serve-attachments-via-django.md` → `docs/plans/completed/`

- [ ] Add `render_forum_attachments` step to the import workflow in `CLAUDE.md`
- [ ] Move this plan file to `docs/plans/completed/`

## Post-Completion

**Manual verification:**
- Download a `.doc`, `.pdf`, and image attachment from a real post and confirm filenames and extensions are preserved
- Verify a private-subforum attachment is blocked for anonymous users and accessible for members

**Deployment note:**
- Run `uv run python manage.py render_forum_attachments` once on production after deploy to patch stored HTML
