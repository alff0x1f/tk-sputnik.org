# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Django 5.2 website for a tourism club (турклуб). Python 3.14+, managed with `uv`.

## Setup

```bash
cp .env.example .env          # fill in DJANGO_SECRET_KEY and ALLOWED_HOSTS at minimum
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

The app loads `.env` automatically via `python-dotenv`. `DEBUG` defaults to `False` unless set to `1`, `true`, `yes`, or `on`.

## Common commands

```bash
uv run python manage.py runserver       # dev server at http://127.0.0.1:8000/
uv run python manage.py migrate
uv run python manage.py makemigrations
uv run pytest                           # run all tests
uv run pytest apps/demo/tests.py       # run a single test file
uv run ruff check .                     # lint
uv run ruff format .                    # format
```

## Testing

Use `pytest` (not `manage.py test`). `DJANGO_SETTINGS_MODULE` is set in `pyproject.toml` under `[tool.pytest.ini_options]`, so no extra env setup is needed. Write tests with `django.test.TestCase` and use `self.client` for HTTP assertions. Test files can be named `tests.py` or `test_*.py` — both are discovered.

## Architecture

- `config/` — Django project config (settings, urls, wsgi, asgi)
- `apps/` — all Django apps live here
- New apps go in `apps/` and are registered in `INSTALLED_APPS` as `apps.<name>`
- Database: SQLite in development (`db.sqlite3`), PostgreSQL via `psycopg[binary]` in production
- Static files: standard Django `STATIC_URL`
- No custom authentication — uses Django's built-in auth

## phpBB forum archive

The site includes a read-only archive of the old phpBB forum (2007–2014), accessible at `/forum/`.

**Apps:**
- `apps/forum` — models `ForumCategory` and `SubForum` stored in PostgreSQL; view at `/forum/`
- `apps/forum_import` — import infrastructure; management command `import_phpbb_forums`

**Data source:** phpBB 3.x MySQL database, table prefix `vu2_`. The MySQL instance runs as a separate Docker Compose service with `profiles: [phpbb]` — it is not started by default.

**Import workflow (one-time manual step):**
```bash
docker compose --profile phpbb up -d phpbb_db
# wait for healthy, then load the dump:
docker compose exec phpbb_db mysql -u phpbb -p phpbb < /path/to/forum_dump.sql
# run the import command:
uv run python manage.py import_phpbb_forums
# expected output: Imported 5 categories, N subforums
```

**Django database connection:** `DATABASES['phpbb']` points to MySQL via PyMySQL (`pymysql.install_as_MySQLdb()` in `config/__init__.py`). MySQL env vars: `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT`. See `apps/forum_import/README.md` for details.

After import, MySQL is no longer needed at runtime — all data lives in PostgreSQL.

**Import status:**
- [x] Categories and subforums (`ForumCategory`, `SubForum`) — done
- [x] Users (`ForumUser`) — done
- [x] Topics (`Topic`), posts (`Post`) — done

## Challenge app

Winter sports challenge (Dec 2025 – Mar 2026) at `/challenge/`.

**Apps:**
- `apps/challenge` — models `Athlete`, `Workout`, `SourceMessage`; leaderboard, review page, photo serving

**Models:**
- `Athlete` — `telegram_id` (PK CharField), `name`
- `Workout` — FK to `Athlete`, `date`, `activity`, `distance_km`, `pace_min_per_km`, `base_points`, `streak_bonus`, `total_points`, `msg_id`
- `SourceMessage` — `msg_id` (PK), `from_name`, `date`, `text`, `photos` (JSONField)

**Scoring logic:** `apps/challenge/scoring.py` — `compute_base_points()` and `recompute_athlete_scores()`

**Import command (one-time or re-run to refresh):**
```bash
uv run python manage.py import_challenge \
    --scores scratch/challenge/scores.json \
    --messages scratch/challenge/messages_clean.json
# expected output: Imported N athletes, M workouts, K messages
```

**Photo serving:** `CHALLENGE_CHAT_EXPORT_DIR` in `config/settings.py` (and `.env`) points to the `ChatExport_*` directory. Photos served at `/challenge/photo/<filename>` with path-traversal protection.

**Review page:** `/challenge/review/` — staff-only split panel (photo + message text on the left, editable workout forms with auto-save on the right). CRUD API under `/challenge/review/api/workout/`.

**Member detail page:** `/challenge/member/<telegram_id>/` — staff-only read-only chat view of all messages from one athlete; messages linked to a workout show an embedded info card.

## Branch naming

`feat/`, `fix/`, `chore/`, `refactor/`, `docs/`, `test/` — followed by issue number and slug, e.g. `feat/4-add-demo-app`.
