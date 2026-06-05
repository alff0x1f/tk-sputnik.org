# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Django 5.2 website for a tourism club (турклуб). Python 3.14+, managed with `uv`.

**Python 3.14 syntax note:** `except A, B:` (no parentheses) is valid — per PEP 758, parentheses are optional in `except`/`except*` clauses when there's no `as` binding, so it means `except (A, B):` and catches both types. This is **not** the old Python 2 `except E, name:` (bind-to-name) syntax, and it is **not** a bug. `apps/challenge/views.py` uses this form (e.g. `except KeyError, ValueError:`). Do not "fix" it by adding parentheses unless an `as` binding is needed.

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
# copy attachment files, then import attachment metadata:
cp -r scratch/forum/files/ media/forum/attachments/
uv run python manage.py import_phpbb_attachments
# reset PostgreSQL sequences so ORM .create() works after explicit-ID imports:
uv run python manage.py reset_forum_sequences
```

**Django database connection:** `DATABASES['phpbb']` points to MySQL via PyMySQL (`pymysql.install_as_MySQLdb()` in `config/__init__.py`). MySQL env vars: `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT`. See `apps/forum_import/README.md` for details.

After import, MySQL is no longer needed at runtime — all data lives in PostgreSQL.

**Import status:**
- [x] Categories and subforums (`ForumCategory`, `SubForum`) — done
- [x] Users (`ForumUser`) — done
- [x] Topics (`Topic`), posts (`Post`) — done
- [x] Private subforum access control (is_private + allowed_group)
- [x] Attachments (`PostAttachment`) — done

## Challenge app

Winter sports challenge (Dec 2025 – Mar 2026) at `/challenge/`.

**Apps:**
- `apps/challenge` — models `Group`, `Athlete`, `Workout`, `SourceMessage`; leaderboard, review page, group assignment page, photo serving

**Models:**
- `Group` — `name` (unique CharField), `order` (IntegerField, default 0); `Meta.ordering = ["order", "name"]`
- `Athlete` — `telegram_id` (PK CharField), `name`, `group` (FK to `Group`, `on_delete=SET_NULL`, nullable — deleting a group leaves its athletes ungrouped)
- `Workout` — FK to `Athlete`, `date`, `activity`, `distance_km`, `pace_min_per_km`, `base_points`, `streak_bonus`, `streak_prev_date` (nullable DateField — date of previous qualifying workout in the streak chain), `total_points`, `msg_id`; `UniqueConstraint` on `(athlete, date, activity)` — CRUD API returns 400 on duplicate
- `SourceMessage` — `msg_id` (PK), `from_id` (Telegram sender ID, db_index), `from_name`, `date`, `datetime` (nullable), `text`, `photos` (JSONField)

**Scoring logic:** `apps/challenge/scoring.py` — `compute_base_points()` and `recompute_athlete_scores()`. Hiking (`activity == "hiking"`, «Пеший поход» — also covers тренировочный выезд с ГШ) scores a flat **2** base points and is excluded from the streak: it earns no `streak_bonus` and does not advance the streak chain, so neighbouring workouts measure their gap across it as if it were not there.

**Recompute command (refresh stored scores after a scoring rule change):**
```bash
uv run python manage.py recompute_scores
# expected output: Recomputed scores for N athletes
```
Re-runs `recompute_athlete_scores()` for every athlete in place. Needed because import and the review page only recompute on write — a scoring-logic change leaves stored `base_points`/`streak_bonus`/`total_points` stale until this runs.

**Import command (one-time or re-run to refresh):**
```bash
uv run python manage.py import_challenge \
    --scores scratch/challenge/scores.json \
    --telegram-export scratch/challenge/ChatExport_2026-04-02/result.json
# expected output: Imported N athletes, M workouts, K messages
```

**Photo serving:** `CHALLENGE_CHAT_EXPORT_DIR` in `config/settings.py` (and `.env`) points to the `ChatExport_*` directory. Photos served at `/challenge/photo/<filename>` with path-traversal protection.

**Review page:** `/challenge/review/` — staff-only split panel (photo + message text on the left, editable workout forms with auto-save on the right). CRUD API under `/challenge/review/api/workout/`.

**Leaderboard:** `/challenge/` — public ranking ordered by points. Includes a «Группа» column (`athlete.group.name`, «—» when ungrouped); the queryset uses `.select_related("group")`. Staff see a «Распределение по группам» link to the assignment page.

**Group assignment page:** `/challenge/groups/` — staff-only page listing all athletes, each with a `<select>` (current group or «— без группы —»). Changing a select auto-saves via `PUT /challenge/groups/api/athlete/<telegram_id>/` (route `challenge-api-athlete-group`), body `{"group_id": <id> | null}` → `200 {"ok": true}`; unknown group → `400`, unknown athlete → `404`, invalid JSON → `400`. Groups themselves (CRUD, ordering) are managed in Django admin (`GroupAdmin`); `AthleteAdmin` has a `group` column and `list_filter`.

**Member detail page:** `/challenge/member/<telegram_id>/` — public chat view of all messages from one athlete; messages linked to a workout show an embedded info card with inline edit/delete buttons (staff-only UI, PUT/DELETE to the same API as the review page). Messages sent by someone other than the athlete (e.g. when staff links a workout to a message from a group chat) display a `.msg-foreign-badge` label. The `_group_messages(messages, workouts_by_msg, athlete_telegram_id="")` helper in `views.py` computes `foreign_senders` (list of display names) per group using `from_id` for deduplication.

**Anonymous reports (жалобы):** `Report` model (FK to `SourceMessage` and `Athlete`, `text`, `created_at`, `resolved`) lets anyone flag a wrong or missing workout, tied to a message group's `primary_msg_id` rather than a specific workout. Every message bubble shows a «сообщить об ошибке» button + hidden form for all users. Anonymous create: `POST /challenge/member/<telegram_id>/api/report/` (route `challenge-api-report-create`, no `staff_member_required`), body `{"msg_id": <int>, "text": <str>}` → `201 {"ok": true}`; empty/too-long text (`MAX_REPORT_LEN = 2000`) → `400`, unknown/non-numeric `msg_id` → `400`, unknown athlete → `404`. `member_detail` carries `@ensure_csrf_cookie` so anonymous POSTs have a `csrftoken` cookie. Staff see a `.msg-report-badge` with the count of unresolved reports and a list with «Закрыть» buttons; resolve/delete via `PUT|DELETE /challenge/review/api/report/<pk>/` (route `challenge-api-report-detail`, `@staff_member_required`; PUT sets `resolved=True`, DELETE removes). For staff, `member_detail` loads unresolved reports into each group's `g["reports"]`. Reports are managed in Django admin (`ReportAdmin`, with `list_editable = ["resolved"]`).

## Branch naming

`feat/`, `fix/`, `chore/`, `refactor/`, `docs/`, `test/` — followed by issue number and slug, e.g. `feat/4-add-demo-app`.
