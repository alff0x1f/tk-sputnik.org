# Refactor: Unify id and phpbb_id in forum models

## Overview

Eliminated the duality between Django's auto-increment `id` and `phpbb_id` in all five
forum models. For imported phpBB data `id == phpbb_id` — the Django primary key is now
set explicitly to the phpBB value during import. `phpbb_id` remains as a nullable field
to document the origin and allow future native posts (which will have `phpbb_id = NULL`).

## What changed

### `apps/forum/models.py`

All five models (`ForumCategory`, `SubForum`, `ForumUser`, `Topic`, `Post`):

```python
# before
phpbb_id = models.IntegerField("ID в phpBB", unique=True)

# after
phpbb_id = models.IntegerField("ID в phpBB", unique=True, null=True, blank=True)
```

### Import commands

All four commands (`import_phpbb_forums`, `import_phpbb_users`, `import_phpbb_topics`,
`import_phpbb_posts`) now:

- Use `id=<phpbb_value>` as the `update_or_create` lookup key
- Pass `phpbb_id=<phpbb_value>` in `defaults` so both fields are set identically
- Look up related objects via `id=` instead of `phpbb_id=`

Example:
```python
# before
Topic.objects.update_or_create(phpbb_id=row["topic_id"], defaults={...})

# after
Topic.objects.update_or_create(id=row["topic_id"], defaults={"phpbb_id": row["topic_id"], ...})
```

### Migrations

Old `0002_forumuser.py` and `0003_topic_post.py` removed. `0001_initial.py` regenerated
as a single clean migration covering all five models with the new nullable `phpbb_id`.

### New management command: `reset_forum_sequences`

`apps/forum_import/management/commands/reset_forum_sequences.py` — resets PostgreSQL
sequences for all forum tables after import with explicit IDs, so subsequent inserts
get correct auto-increment values.

```bash
uv run python manage.py reset_forum_sequences
```

No-op on SQLite (skips silently).

### Tests

`apps/forum_import/tests.py` — setUp fixtures for `ImportPhpbbTopicsCommandTest` and
`ImportPhpbbPostsCommandTest` now set `id=X` explicitly alongside `phpbb_id=X` so they
match what the import commands expect.

## Re-import instructions

Run once after deploying this branch:

```bash
# 1. Drop existing forum tables and clear migration history
uv run python manage.py dbshell
```
In psql:
```sql
DROP TABLE IF EXISTS forum_post, forum_topic, forum_forumuser, forum_subforum, forum_forumcategory CASCADE;
DELETE FROM django_migrations WHERE app = 'forum';
\q
```

```bash
# 2. Apply fresh migration
uv run python manage.py migrate

# 3. Re-run all imports (requires phpbb Docker service)
docker compose --profile phpbb up -d phpbb_db
uv run python manage.py import_phpbb_forums
uv run python manage.py import_phpbb_users
uv run python manage.py import_phpbb_topics
uv run python manage.py import_phpbb_posts

# 4. Reset PostgreSQL sequences
uv run python manage.py reset_forum_sequences
```

## Branch / commit

Branch: `refactor/forum-unify-id-phpbb-id`  
Commit: `6028846`
