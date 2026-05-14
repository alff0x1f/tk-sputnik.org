# Import phpBB Users into ForumUser

## Overview

Add a `ForumUser` model to the forum archive and a management command `import_phpbb_users` that reads user records from the legacy phpBB MySQL database and stores them in PostgreSQL. The import is idempotent and one-time, matching the pattern of the existing `import_phpbb_forums` command.

## Context (from discovery)

- **Files involved:** `apps/forum/models.py`, `apps/forum/admin.py`, `apps/forum_import/management/commands/`, `apps/forum_import/tests.py`
- **Existing pattern:** `import_phpbb_forums` uses `connections["phpbb"].cursor()`, `update_or_create` by `phpbb_id`, HTML entity unescaping, unix-timestamp conversion — replicate exactly
- **Source table:** `vu2_users` in MySQL; relevant columns: `user_id`, `username`, `user_email`, `user_avatar`, `user_avatar_type`, `user_regdate`, `user_posts`, `user_type`
- **Filters:** skip `user_id=1` (phpBB anonymous) and `user_type=2` (bots/system accounts)
- **Avatar handling:** `user_avatar_type=2` → store URL as-is; type 1/3 → store filename as-is; empty → `""`

## Development Approach

- **Testing approach:** Regular (code first, then tests)
- Complete each task fully before moving to the next
- **Every task must include tests before moving on**
- Run `uv run pytest apps/forum_import/tests.py` after each task

## Testing Strategy

- **Unit tests** in `apps/forum_import/tests.py`, patching `connections` exactly like `ImportPhpbbForumsCommandTest`
- No UI / e2e tests needed — this is a management command with no frontend

## Progress Tracking

- Mark completed items with `[x]` immediately when done
- Add newly discovered tasks with ➕ prefix
- Document issues/blockers with ⚠️ prefix

## Solution Overview

1. Add `ForumUser` model to `apps/forum`
2. Generate and apply migration
3. Register in Django admin
4. Add `import_phpbb_users` management command in `apps/forum_import`
5. Write tests covering: normal import, filtering of anon/bots, avatar type handling, idempotency, timestamp conversion
6. Update `CLAUDE.md` import status checklist

## Technical Details

**Model fields:**

| Field | Type | Notes |
|---|---|---|
| `phpbb_id` | `IntegerField(unique=True)` | phpBB `user_id` |
| `username` | `CharField(max_length=255)` | display name |
| `email` | `EmailField(blank=True)` | may be empty |
| `avatar` | `CharField(max_length=500, blank=True)` | URL or filename |
| `registered_at` | `DateTimeField(null=True, blank=True)` | from unix `user_regdate` |
| `post_count` | `IntegerField(default=0)` | `user_posts` |

**Avatar logic:**
```python
def _avatar(val, avatar_type):
    if not val:
        return ""
    return val  # store path or URL as-is regardless of type
```

**SQL filter:**
```sql
WHERE user_id != 1 AND user_type != 2
```

## Implementation Steps

### Task 1: Add ForumUser model and migration

**Files:**
- Modify: `apps/forum/models.py`
- Create: `apps/forum/migrations/0002_forumuser.py` (generated)

- [x] add `ForumUser` model to `apps/forum/models.py` with all six fields and `verbose_name`
- [x] run `uv run python manage.py makemigrations forum` to generate migration
- [x] run `uv run python manage.py migrate` to apply it
- [x] write test in `apps/forum/tests.py` asserting `ForumUser` can be created and retrieved
- [x] run `uv run pytest apps/forum/tests.py` — must pass before Task 2

### Task 2: Register ForumUser in Django admin

**Files:**
- Modify: `apps/forum/admin.py`

- [x] add `admin.site.register(ForumUser)` to `apps/forum/admin.py`
- [x] (no separate test needed — admin registration is verified by existing app-config test pattern)
- [x] run `uv run pytest apps/forum/` — must pass before Task 3

### Task 3: Implement import_phpbb_users management command

**Files:**
- Create: `apps/forum_import/management/commands/import_phpbb_users.py`

- [x] create command class inheriting `BaseCommand`, `help` string set
- [x] execute SQL selecting all needed columns from `vu2_users` with `WHERE user_id != 1 AND user_type != 2`
- [x] map rows to `ForumUser` via `update_or_create(phpbb_id=..., defaults={...})`
- [x] apply avatar logic: store `user_avatar` string as-is (empty string when blank)
- [x] convert `user_regdate` unix timestamp with `_unix_to_dt` (import from `import_phpbb_forums` or duplicate the two-liner)
- [x] print `Imported N users` to stdout
- [x] run `uv run ruff check apps/forum_import/management/commands/import_phpbb_users.py` — must be clean

### Task 4: Write tests for import_phpbb_users

**Files:**
- Modify: `apps/forum_import/tests.py`

- [x] add `_make_user_row` helper and `_mock_user_cursor` following the existing pattern in the file
- [x] test: normal import creates `ForumUser` records and prints correct count
- [x] test: `user_id=1` (anonymous) is skipped
- [x] test: `user_type=2` (bot) is skipped
- [x] test: remote avatar (`user_avatar_type=2`) stored as-is
- [x] test: uploaded avatar (`user_avatar_type=1`) stored as filename string
- [x] test: empty avatar stored as `""`
- [x] test: `user_regdate` unix timestamp converted to aware datetime
- [x] test: idempotency — running command twice leaves one record
- [x] run `uv run pytest apps/forum_import/tests.py` — all must pass before Task 5

### Task 5: Verify acceptance criteria

- [x] run full test suite: `uv run pytest`
- [x] run linter: `uv run ruff check .`
- [x] confirm `ForumUser` model has all six fields with correct types
- [x] confirm command skips anon and bot users
- [x] confirm idempotency test passes

### Task 6: [Final] Update documentation

**Files:**
- Modify: `CLAUDE.md`
- Move: `docs/plans/20260514-import-phpbb-users.md` → `docs/plans/completed/`

- [x] update `CLAUDE.md` import status: mark `[ ] Topics, posts, users` note — add `[x] Users (ForumUser)` line
- [x] move this plan to `docs/plans/completed/20260514-import-phpbb-users.md`

## Post-Completion

**Manual verification:**
- Start MySQL phpBB container and run `uv run python manage.py import_phpbb_users` against real data
- Verify user count matches phpBB admin panel (minus anonymous + bots)
- Check Django admin `/admin/forum/forumuser/` shows imported records
