# phpBB Import: Topics and Posts

## Overview

Add `Topic` and `Post` models to `apps/forum` and two management commands
(`import_phpbb_topics`, `import_phpbb_posts`) that transfer the phpBB archive
(7 043 topics, 115 954 posts) into the Django database.

BBCode is converted to HTML during import and stored alongside the raw source
so the site can render posts without a runtime BBCode dependency.

## Context (from discovery)

- **Existing models**: `ForumCategory`, `SubForum`, `ForumUser` in `apps/forum/models.py`
- **Migrations**: `0001_initial.py`, `0002_forumuser.py`
- **Import pattern**: `apps/forum_import/management/commands/import_phpbb_forums.py`
  (`connections["phpbb"]`, `update_or_create`, `html.unescape`, `_unix_to_dt`)
- **Test pattern**: `apps/forum_import/tests.py` — mock `connections` with `MagicMock`,
  build fake rows + `cursor.description`, call via `call_command`
- **phpBB quirk**: BBCode tags carry a per-post UID suffix (`[b:12hsql24]text[/b:12hsql24]`);
  must be stripped with regex before parsing
- **Volumes**: `vu2_topics` — 7 043 rows; `vu2_posts` — 115 954 rows

## Development Approach

- **Testing approach**: Regular (implement, then write tests)
- Complete each task fully before moving to the next
- **Every task must include new/updated tests**
- All tests must pass before starting the next task
- Run `uv run pytest` after each task

## Testing Strategy

- Unit tests only (no e2e / UI yet — forum display not in scope here)
- Mock `connections["phpbb"]` as in existing tests
- Cover: happy path, idempotency, missing FK (orphan topic/post), BBCode conversion,
  HTML-entity decoding, Unix-timestamp conversion, null author fallback

## Solution Overview

1. Add `Topic` and `Post` models → generate migration
2. Add `bbcode` to dependencies
3. `import_phpbb_topics` — reads `vu2_topics`, resolves `SubForum` by `phpbb_id`,
   `update_or_create` per row
4. `import_phpbb_posts` — reads `vu2_posts`, strips UID, decodes entities, converts
   BBCode→HTML, resolves `Topic` and `ForumUser` (both nullable-safe), `update_or_create`
5. Register new models in admin
6. Update CLAUDE.md import status

## Technical Details

### Models

```python
class Topic(Model):
    phpbb_id    IntegerField(unique=True)
    subforum    FK → SubForum(CASCADE, related_name="topics")
    title       CharField(255)
    created_at  DateTimeField(null=True, blank=True)   # vu2_topics.topic_time (Unix)
    views       IntegerField(default=0)                 # topic_views
    post_count  IntegerField(default=0)                 # topic_replies + 1
    ordering    ["-created_at"]

class Post(Model):
    phpbb_id        IntegerField(unique=True)
    topic           FK → Topic(CASCADE, related_name="posts")
    author          FK → ForumUser(SET_NULL, null=True, blank=True, related_name="posts")
    author_username CharField(255, blank=True)          # post_username fallback
    text_bbcode     TextField()
    text_html       TextField()
    created_at      DateTimeField(null=True, blank=True) # post_time (Unix)
    ordering        ["created_at"]
```

### BBCode processing pipeline (per post)

```python
import re, html, bbcode

_parser = bbcode.Parser()

def _to_html(raw: str, uid: str) -> str:
    text = html.unescape(raw or "")
    if uid:
        # strip phpBB UID: [b:uid] → [b],  [/b:uid] → [/b]
        text = re.sub(rf"\[([^\[\]:]+):{re.escape(uid)}\]", r"[\1]", text)
        text = re.sub(rf"\[/([^\[\]:]+):{re.escape(uid)}\]", r"[/\1]", text)
    return _parser.format(text)
```

### Key phpBB columns used

**vu2_topics**: `topic_id`, `forum_id`, `topic_title`, `topic_time`, `topic_views`,
`topic_replies`, `topic_replies_real`

**vu2_posts**: `post_id`, `topic_id`, `poster_id`, `post_username`, `post_text`,
`bbcode_uid`, `post_time`

## What Goes Where

**Implementation Steps** — all code changes tracked below with checkboxes.

**Post-Completion** — manual steps after implementation:
- Load phpBB dump, run `import_phpbb_topics` then `import_phpbb_posts`
- Spot-check a few posts in Django admin for correct BBCode rendering

---

## Implementation Steps

### Task 1: Add Topic and Post models + migration

**Files:**
- Modify: `apps/forum/models.py`
- Create: `apps/forum/migrations/0003_topic_post.py` (via makemigrations)

- [x] Add `Topic` model to `apps/forum/models.py` (fields per Technical Details above)
- [x] Add `Post` model to `apps/forum/models.py` (fields per Technical Details above)
- [x] Run `uv run python manage.py makemigrations forum` and verify generated file
- [x] Write model-level tests in `apps/forum/tests.py`:
  - `test_topic_str` — `str(topic)` returns title
  - `test_post_str` — `str(post)` returns something sensible
  - `test_post_author_nullable` — post can be saved without author
- [x] Run `uv run pytest apps/forum/tests.py` — must pass before Task 2

### Task 2: Add bbcode dependency

**Files:**
- Modify: `pyproject.toml`

- [x] Run `uv add bbcode` to add the library and update `pyproject.toml` + `uv.lock`
- [x] Smoke-test: `uv run python -c "import bbcode; print(bbcode.render_html('[b]ok[/b]'))"`
- [x] No separate test needed — covered by Task 4 tests

### Task 3: import_phpbb_topics command

**Files:**
- Create: `apps/forum_import/management/commands/import_phpbb_topics.py`

- [x] Create command reading all rows from `vu2_topics`
- [x] For each row: resolve `SubForum` by `phpbb_id == forum_id`; skip with stderr message if not found
- [x] `update_or_create(phpbb_id=topic_id, defaults={subforum, title, created_at, views, post_count})`
  - `post_count = topic_replies + 1` (phpBB stores reply count, not total)
- [x] Print `Imported N topics (M skipped)` to stdout
- [x] Write tests in `apps/forum_import/tests.py` (`ImportPhpbbTopicsCommandTest`):
  - `test_imports_topics` — happy path, count matches
  - `test_skips_unknown_subforum` — subforum not in DB → skipped, stderr message
  - `test_idempotency` — running twice doesn't duplicate
  - `test_unix_timestamp_converted` — `created_at` is timezone-aware
  - `test_post_count_includes_first_post` — `post_count = topic_replies + 1`
- [x] Run `uv run pytest apps/forum_import/tests.py` — must pass before Task 4

### Task 4: import_phpbb_posts command

**Files:**
- Create: `apps/forum_import/management/commands/import_phpbb_posts.py`

- [x] Create command reading all rows from `vu2_posts` ordered by `post_id`
- [x] Implement `_to_html(raw, uid)` helper (regex UID strip + html.unescape + bbcode.Parser)
- [x] For each row:
  - resolve `Topic` by `phpbb_id == topic_id`; skip with stderr if not found
  - resolve `ForumUser` by `phpbb_id == poster_id`; set `None` if not found
  - `author_username` = `post_username` (raw, may be empty)
  - `update_or_create(phpbb_id=post_id, defaults={...})`
- [x] Print `Imported N posts (M skipped)` to stdout
- [x] Write tests (`ImportPhpbbPostsCommandTest`):
  - `test_imports_posts` — happy path
  - `test_skips_unknown_topic` — topic not in DB → skipped
  - `test_null_author_for_missing_user` — user not in DB → author=None
  - `test_idempotency` — running twice doesn't duplicate
  - `test_bbcode_uid_stripped` — `[b:uid]text[/b:uid]` → `<strong>text</strong>` (or `<b>`)
  - `test_html_entities_unescaped` — `&#1087;&#1088;&#1099;&#1074;&#1077;&#1090;` decoded
  - `test_unix_timestamp_converted`
- [x] Run `uv run pytest apps/forum_import/tests.py` — must pass before Task 5

### Task 5: Register models in admin

**Files:**
- Modify: `apps/forum/admin.py`

- [x] Register `Topic` with `list_display = ["title", "subforum", "post_count", "created_at"]`
- [x] Register `Post` with `list_display = ["phpbb_id", "topic", "author_username", "created_at"]`
- [x] Run `uv run pytest` (full suite) — must pass before Task 6

### Task 6: Verify and clean up

- [ ] Run full test suite: `uv run pytest`
- [ ] Run linter: `uv run ruff check . && uv run ruff format --check .`
- [ ] Update `CLAUDE.md` import status checklist (Topics/Posts → `[x] done`)
- [ ] Move this plan to `docs/plans/completed/`

## Post-Completion

**Manual verification:**
1. Start phpBB MySQL service and load dump
2. Run `uv run python manage.py import_phpbb_topics`
3. Run `uv run python manage.py import_phpbb_posts`
4. Open Django admin → spot-check 2–3 posts for correct HTML rendering
5. Stop MySQL service
