# Fix unrendered BBCode tags [del] and [youtube]

## Overview

316 posts have `[del]...[/del]` leaking as raw text in `text_html`, and 654 posts have
`[youtube]...[/youtube]` unrendered. Root cause: `bbcode.Parser()` in
`import_phpbb_posts.py` has no formatters for these tags.

Fix: add formatters, store `bbcode_uid` on `Post`, add a `rerender_posts` command to
regenerate `text_html` from `text_bbcode` for all existing posts.

## Context (from discovery)

- `apps/forum/models.py` — `Post` model; `text_bbcode` and `text_html` stored separately
- `apps/forum_import/management/commands/import_phpbb_posts.py` — `_to_html()`,
  `_parser`, `Command.handle()`
- `apps/forum_import/management/commands/import_phpbb_attachments.py` — contains
  `_finalize_post_html()` which calls `_to_html()` and then resolves attachment
  placeholders; `rerender_posts` must use this function, not bare `_to_html()`, to
  preserve attachment HTML
- `apps/forum_import/tests.py` — existing tests for `_to_html` and all import commands
- `apps/forum/migrations/` — currently at `0003_postattachment.py`

Key constraint: `bbcode_uid` is currently NOT stored on `Post`. Existing posts in the DB
were imported without it. The `rerender_posts` command needs a fallback: auto-detect UID
from `text_bbcode` using a regex when the stored field is empty.

## Development Approach

- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- Every task includes new/updated tests
- All tests must pass before starting next task

## Testing Strategy

- Unit tests with `django.test.TestCase` via `pytest`
- Run: `uv run pytest apps/forum_import/tests.py`
- Full suite: `uv run pytest`

## Solution Overview

1. Add `Post.bbcode_uid` CharField + migration
2. Add `[del]` and `[youtube]` formatters to `_parser`; save `bbcode_uid` in import
3. Add `_detect_uid()` helper for existing posts that lack stored UID
4. New `rerender_posts` command: iterates all posts, calls `_finalize_post_html()` with
   stored attachments, saves updated `text_html`

YouTube renders as:
```html
<div class="yt-embed"><iframe width="560" height="315"
  src="https://www.youtube.com/embed/{VIDEO_ID}"
  allowfullscreen loading="lazy"></iframe></div>
```

## Technical Details

**YouTube URL patterns** to extract video ID from:
- `https://www.youtube.com/watch?v=VIDEO_ID`
- `http://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`

The BBCode parser auto-links URLs inside tags before calling the formatter, so
`_render_youtube` must strip the auto-linked `<a href="...">` wrapper to get the raw URL
(same pattern as existing `_render_img`).

**UID auto-detection** (fallback for existing posts):
```python
_UID_DETECT_RE = re.compile(r'\[[a-zA-Z][a-zA-Z0-9]*:([a-z0-9]{5,12})\]')

def _detect_uid(text: str) -> str:
    m = _UID_DETECT_RE.search(text)
    return m.group(1) if m else ""
```

Length filter `{5,12}` excludes phpBB list markers (`:u`, `:o`, `:m` are 1 char).

## Implementation Steps

### Task 1: Add `Post.bbcode_uid` field and migration

**Files:**
- Modify: `apps/forum/models.py`
- Create: `apps/forum/migrations/0004_post_bbcode_uid.py`

- [x] add `bbcode_uid = models.CharField("phpBB BBCode UID", max_length=20, blank=True)`
      to `Post` in `apps/forum/models.py`
- [x] run `uv run python manage.py makemigrations forum` to generate migration
- [x] verify migration file is generated as `0004_post_bbcode_uid.py`
- [x] run `uv run python manage.py migrate` — must succeed with no errors
- [x] write test: `Post` can be created with and without `bbcode_uid` field
- [x] run tests — must pass before Task 2

### Task 2: Add `[del]` and `[youtube]` formatters; save UID in import

**Files:**
- Modify: `apps/forum_import/management/commands/import_phpbb_posts.py`
- Modify: `apps/forum_import/tests.py`

- [x] add `_YT_URL_RE` regex constant for extracting YouTube video ID (supports
      `youtube.com/watch?v=` and `youtu.be/` in http and https)
- [x] add `_render_youtube(tag_name, value, options, parent, context)` function:
      extract URL (strip auto-link wrapper with `_HREF_RE`), parse video ID, return
      `<div class="yt-embed"><iframe ...></iframe></div>`; return bare value if no ID found
- [x] register `[del]` with `_parser.add_simple_formatter("del", "<del>%(value)s</del>")`
- [x] register `[youtube]` with
      `_parser.add_formatter("youtube", _render_youtube, render_embedded=False)`
- [x] in `Command.handle()`, add `"bbcode_uid": uid` to the `update_or_create` defaults
- [x] write test `test_del_tag_renders_to_del_element`: `_to_html("[del]text[/del]", "")` →
      `<del>text</del>`
- [x] write test `test_del_tag_with_uid_stripped_and_rendered`: uid suffix stripped before
      rendering
- [x] write test `test_youtube_tag_renders_iframe`: `_to_html` with
      `[youtube:uid]https://www.youtube.com/watch?v=ABC123[/youtube:uid]` →
      `<iframe ... src=".../embed/ABC123" ...>`
- [x] write test `test_youtube_youtu_be_url`: short URL `https://youtu.be/ABC123` → same
      iframe
- [x] write test `test_youtube_invalid_url_falls_back`: no video ID → no iframe, no crash
- [x] write test `test_bbcode_uid_saved_on_import`: after import command, `post.bbcode_uid`
      equals the UID from the row
- [x] run `uv run pytest apps/forum_import/tests.py` — must pass before Task 3

### Task 3: Create `rerender_posts` management command

**Files:**
- Create: `apps/forum_import/management/commands/rerender_posts.py`
- Modify: `apps/forum_import/tests.py`

- [x] create `rerender_posts.py` with `Command` class
- [x] add `_detect_uid(text: str) -> str` helper (with `_UID_DETECT_RE`) in the new file
- [x] command iterates `Post.objects.all()` in `phpbb_id` order
- [x] for each post: `uid = post.bbcode_uid or _detect_uid(post.text_bbcode)`
- [x] call `_finalize_post_html(post.text_bbcode, uid, list(post.attachments.order_by("phpbb_id")))`
      imported from `import_phpbb_attachments`
- [x] save with `post.save(update_fields=["text_html"])`
- [x] print progress every 100 posts and final count
- [x] write test `test_rerender_updates_del_tag`: create `Post` with `text_bbcode`
      containing `[del:uid]text[/del:uid]` and wrong `text_html`; run command; assert
      `text_html` contains `<del>text</del>`
- [x] write test `test_rerender_updates_youtube_tag`: similar for `[youtube:uid]`
- [x] write test `test_rerender_preserves_attachments`: post with attachment in DB;
      assert attachment HTML present after rerender
- [x] write test `test_rerender_uid_autodetect`: post with empty `bbcode_uid` but UID
      embedded in `text_bbcode`; assert UID stripped correctly after rerender
- [x] run `uv run pytest apps/forum_import/tests.py` — must pass before Task 4

### Task 4: Verify acceptance criteria

- [ ] run full test suite: `uv run pytest`
- [ ] run `uv run ruff check .` — no lint errors
- [ ] verify `[del]` rendering: `Post.objects.filter(text_html__icontains="[del]").count()` == 0
      after rerender
- [ ] verify `[youtube]` rendering: `Post.objects.filter(text_html__icontains="[youtube]").count()` == 0
      after rerender

### Task 5: [Final] Cleanup

- [ ] move this plan to `docs/plans/completed/`

## Post-Completion

**Run `rerender_posts` on production data:**
```bash
uv run python manage.py rerender_posts
```
Expected: all 316 `[del]` and 654 `[youtube]` posts re-rendered.

**Spot-check:**
- Post `phpbb_id=56194` — should show `<del>...</del>` in `text_html`
- Post `phpbb_id=34474` — should show `<iframe>` for youtube embed

**CSS for `.yt-embed`:** consider adding responsive wrapper styles to
`apps/forum/static/forum/css/forum.css` if iframe overflow is an issue on mobile.
