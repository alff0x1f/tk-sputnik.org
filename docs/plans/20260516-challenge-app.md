# Challenge App

## Overview

New Django app `apps/challenge` that brings the winter sports challenge (Dec 2025 – Mar 2026) into the main site. Participants earn points for running, skiing, cycling, swimming, and hiking based on distance thresholds and a streak bonus.

Three deliverables:
1. **Public leaderboard** at `/challenge/` — rank table with expandable workout rows and links to source messages.
2. **Review page** at `/challenge/review/` — staff-only split-panel for verifying LLM-extracted workouts (Telegram photo + text on the left, editable workout form on the right).
3. **Photo view** at `/challenge/photo/<path>` — serves Telegram ChatExport photos from disk.

Integrates with the existing site (extends `demo/base.html`, matches site CSS variables).

## Context (from discovery)


- **Project**: Django 5.2 tourism club site, `apps/` pattern, uv-managed
- **Base template**: `apps/demo/templates/demo/base.html` — blocks `content`, `extra_css`, `topbar_action`; sidebar nav with forum + contributors links
- **CSS variables**: `--accent`, `--surface`, `--surface-2`, `--line`, `--ink`, `--muted`, `--radius`
- **Reference app**: `apps/forum` — shows model / view / urls / template / static layout to follow
- **Source data** (scratch/challenge/): `scores.json`, `messages_clean.json`, `ChatExport_2026-04-02/` (photos)
- **config/urls.py**: includes apps via `path("forum/", include("apps.forum.urls"))` pattern
- **config/settings.py**: `INSTALLED_APPS` uses `apps.<name>` strings

## Development Approach

- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- Every task that adds or changes Python code must include tests
- All tests must pass before starting the next task
- Run: `uv run pytest`

## Testing Strategy

- **Unit tests**: `pytest` with `django.test.TestCase` and `self.client`
- Test the scoring utility functions in isolation
- Test the management command with fixture data
- Test API endpoints (review save/delete) for auth and correctness
- No e2e tests needed (no Playwright/Cypress in project)

## Progress Tracking

- Mark completed items with `[x]` immediately when done
- Add newly discovered tasks with ➕ prefix
- Document issues/blockers with ⚠️ prefix

## Solution Overview

- Single app `apps/challenge` with three models: `Athlete`, `Workout`, `SourceMessage`
- Management command `import_challenge` populates DB from `scores.json` + `messages_clean.json`
- Scoring logic extracted into `apps/challenge/scoring.py` (pure functions, easy to test)
- Leaderboard view renders server-side HTML (no JS required for viewing)
- Review page embeds CARDS data as JSON in the page (like `review_server.py`) and uses `fetch()` for AJAX saves; server recomputes scores after each change
- `CHALLENGE_CHAT_EXPORT_DIR` setting points to the ChatExport directory; photos served via `FileResponse`

## Technical Details

### Scoring rules
| Activity | 2 pts | 3 pts |
|----------|-------|-------|
| running  | ≥5 km + pace < 10 min/km | ≥10 km + pace < 10 min/km |
| skiing   | ≥6 km | ≥12 km |
| cycling  | ≥20 km | ≥40 km |
| swimming | ≥1 km | ≥2 km |
| hiking   | 2 pts flat | — |

Streak bonus: +1 if gap to previous qualifying workout ≤ 4 days. Max 1 workout per athlete per day (highest base_points kept).

### Data models
```python
Athlete:   telegram_id (CharField PK), name (CharField)
Workout:   athlete (FK), date (DateField), activity (CharField),
           distance_km (FloatField null), pace_min_per_km (FloatField null),
           base_points (IntegerField), streak_bonus (IntegerField),
           total_points (IntegerField), msg_id (IntegerField null, db_index)
SourceMessage: msg_id (IntegerField PK), from_name (CharField),
               date (DateField), text (TextField), photos (JSONField)
```

### Review API endpoints (staff_member_required)
- `GET  /challenge/review/` — renders split-panel page with embedded CARDS JSON
- `GET  /challenge/review/api/cards/` — JSON list of cards (msg_id, from, date, photos, text, workouts)
- `POST /challenge/review/api/workout/` — create workout `{athlete_id, date, activity, distance_km, pace_min_per_km, msg_id}`
- `PUT  /challenge/review/api/workout/<id>/` — update workout fields
- `DELETE /challenge/review/api/workout/<id>/` — delete workout
- After any write: call `recompute_athlete_scores(athlete)` and return updated totals

### Photo serving
```python
# settings.py
CHALLENGE_CHAT_EXPORT_DIR = BASE_DIR / "scratch/challenge/ChatExport_2026-04-02"

# view
def challenge_photo(request, filename):
    return FileResponse(open(CHALLENGE_CHAT_EXPORT_DIR / filename, "rb"))
```

## Implementation Steps

### Task 1: App scaffold + models

**Files:**
- Create: `apps/challenge/__init__.py`
- Create: `apps/challenge/apps.py`
- Create: `apps/challenge/models.py`
- Create: `apps/challenge/admin.py`
- Create: `apps/challenge/migrations/0001_initial.py` (via makemigrations)
- Modify: `config/settings.py`

- [x] Create `apps/challenge/__init__.py`, `apps/challenge/apps.py` (name = `apps.challenge`)
- [x] Define `Athlete`, `Workout`, `SourceMessage` models in `apps/challenge/models.py`
- [x] Register models in `apps/challenge/admin.py` with basic `list_display`
- [x] Add `apps.challenge` to `INSTALLED_APPS` in `config/settings.py`
- [x] Add `CHALLENGE_CHAT_EXPORT_DIR = BASE_DIR / "scratch/challenge/ChatExport_2026-04-02"` to `config/settings.py`
- [x] Run `uv run python manage.py makemigrations challenge` and verify migration file
- [x] Run `uv run python manage.py migrate` — must succeed
- [x] Write model tests: create Athlete + Workout instances, check str(), check FK cascade
- [x] Run tests — must pass before Task 2

### Task 2: Scoring utility

**Files:**
- Create: `apps/challenge/scoring.py`
- Create: `apps/challenge/tests.py`

- [x] Implement `compute_base_points(activity, distance_km, pace_min_per_km) -> int` in `apps/challenge/scoring.py`
- [x] Implement `recompute_athlete_scores(athlete)` — queries all Workouts for athlete ordered by date, recomputes base_points + streak_bonus + total_points, bulk-updates DB
- [x] Write unit tests for `compute_base_points`: all five activities, boundary values (exactly at threshold, just below, just above), None distance, pace too slow
- [x] Write unit tests for `recompute_athlete_scores`: streak chain, gap > 4 days resets bonus, same-day deduplication is handled at import time (not here — note in test)
- [x] Run tests — must pass before Task 3

### Task 3: Import management command

**Files:**
- Create: `apps/challenge/management/__init__.py`
- Create: `apps/challenge/management/commands/__init__.py`
- Create: `apps/challenge/management/commands/import_challenge.py`

- [x] Read `scores.json` → upsert `Athlete` (telegram_id, name) and `Workout` records; use `update_or_create` keyed on (athlete + date + activity) or clear + reimport strategy
- [x] Read `messages_clean.json` → upsert `SourceMessage` (msg_id, from_name, date, text, photos list)
- [x] Print summary: `Imported N athletes, M workouts, K messages`
- [x] Handle missing files gracefully (print warning, continue)
- [x] Write tests using `call_command('import_challenge', ...)` with small in-memory fixture JSON (patch file paths via `--scores` and `--messages` CLI args, or monkeypatching settings)
- [x] Test idempotency: run twice, counts stay the same
- [x] Run tests — must pass before Task 4

### Task 4: Leaderboard view + template

**Files:**
- Create: `apps/challenge/views.py`
- Create: `apps/challenge/urls.py`
- Create: `apps/challenge/templates/challenge/leaderboard.html`
- Create: `apps/challenge/static/challenge/css/challenge.css`
- Modify: `config/urls.py`
- Modify: `apps/demo/templates/demo/base.html`

- [x] Create `leaderboard` view: query all Athletes ordered by total `Workout.total_points` sum descending, pass ranked list + per-athlete workout list to template
- [x] Create `apps/challenge/urls.py` with `path("", views.leaderboard, name="challenge-leaderboard")` and photo view stub
- [x] Include in `config/urls.py`: `path("challenge/", include("apps.challenge.urls"))`
- [x] Create `leaderboard.html` extending `demo/base.html`:
  - Title row with challenge name + date range
  - Rank table: place / name / points / workout count
  - Each row expandable (JS toggle): workout chip per entry with date, activity icon, distance, pace, base pts + streak bonus; last column is link to `/challenge/review/?msg=<msg_id>` (shown only if msg_id exists)
- [x] Add CSS in `challenge.css` using site variables (no new colours except from palette)
- [x] Add "Челлендж" nav-item to sidebar in `apps/demo/templates/demo/base.html`
- [x] Write view tests: response 200, correct number of athletes in context, correct ranking order
- [x] Run tests — must pass before Task 5

### Task 5: Photo serving view

**Files:**
- Modify: `apps/challenge/views.py`
- Modify: `apps/challenge/urls.py`

- [ ] Implement `challenge_photo(request, filename)` view: resolve path within `CHALLENGE_CHAT_EXPORT_DIR`, validate no path traversal (`Path.resolve()` check), return `FileResponse`; return 404 if file not found
- [ ] Add URL: `path("photo/<path:filename>", views.challenge_photo, name="challenge-photo")`
- [ ] Write tests: valid file path returns 200, path traversal (`../../etc/passwd`) returns 404
- [ ] Run tests — must pass before Task 6

### Task 6: Review page — read-only rendering

**Files:**
- Modify: `apps/challenge/views.py`
- Modify: `apps/challenge/urls.py`
- Create: `apps/challenge/templates/challenge/review.html`

- [ ] Create `review` view (staff_member_required): load all SourceMessages ordered by date; for each, fetch linked Workouts (by msg_id); serialize to CARDS JSON; embed in template
- [ ] Add URL: `path("review/", views.review, name="challenge-review")`
- [ ] Create `review.html` extending `demo/base.html`:
  - Topbar (inside `{% block content %}`): prev/next nav, card counter, user filter dropdown, status filter (all / has_workout / no_workout)
  - Left panel: photo gallery + message text (sender, date)
  - Right panel: read-only workout list (date, activity, distance, pace, points)
  - `?msg=<id>` URL param: jump to that card on load
  - Style uses site CSS variables; light-mode to match site (not dark-mode of scratch version)
- [ ] Write view tests: non-staff → redirect to login; staff → 200, CARDS JSON present in response
- [ ] Run tests — must pass before Task 7

### Task 7: Review API — CRUD endpoints

**Files:**
- Modify: `apps/challenge/views.py`
- Modify: `apps/challenge/urls.py`

- [ ] Implement `api_workout_create(request)` — POST JSON `{athlete_id, date, activity, distance_km, pace_min_per_km, msg_id}`, creates Workout, calls `recompute_athlete_scores`, returns updated athlete totals
- [ ] Implement `api_workout_update(request, pk)` — PUT JSON with partial fields, updates Workout, recomputes, returns updated totals
- [ ] Implement `api_workout_delete(request, pk)` — DELETE, removes Workout, recomputes, returns 204
- [ ] All three: `@require_http_methods`, `@staff_member_required`, parse JSON body, return JSON response with `JsonResponse`
- [ ] Add URLs under `review/api/workout/` prefix
- [ ] Write tests: unauthenticated → 302; non-staff → 302; staff POST/PUT/DELETE → correct DB changes + correct recompute triggered; invalid JSON → 400
- [ ] Run tests — must pass before Task 8

### Task 8: Review page — interactive editing (JS)

**Files:**
- Modify: `apps/challenge/templates/challenge/review.html`
- Modify: `apps/challenge/static/challenge/css/challenge.css`

- [ ] Wire up prev/next navigation + counter in JS (client-side card switching)
- [ ] User filter dropdown: re-filters card list client-side
- [ ] Status filter buttons: all / has_workout / no_workout (client-side)
- [ ] Right panel: render editable workout forms (activity select, distance, pace, date, athlete name inputs)
- [ ] "Delete workout" button → `fetch DELETE /challenge/review/api/workout/<id>/`, remove card from DOM
- [ ] "Add workout" button → `fetch POST /challenge/review/api/workout/`, append form
- [ ] Auto-save on field change (debounced, 500ms) → `fetch PUT /challenge/review/api/workout/<id>/`
- [ ] Save status indicator (saving… / saved ✓ / error ✗)
- [ ] `?msg=<id>` URL param: find card index and set as initial card on load
- [ ] No new tests needed for pure JS (covered by API tests in Task 7); verify manually that save/delete round-trip works
- [ ] Run full test suite — must pass before Task 9

### Task 9: Verify acceptance criteria

**Files:** none (verification only)

- [ ] Leaderboard: athletes ranked by total points, rows expand to show workouts, msg links work
- [ ] Review: photo + text visible, workout form editable, save persists to DB, recomputed scores correct
- [ ] Photo serving: `.jpg` files from ChatExport accessible; path traversal rejected
- [ ] Nav "Челлендж" link appears in sidebar and marks active on `/challenge/` routes
- [ ] Non-staff cannot access `/challenge/review/` or review API
- [ ] Run full test suite: `uv run pytest`
- [ ] Run linter: `uv run ruff check .`

### Task 10: [Final] Documentation + cleanup

**Files:**
- Modify: `CLAUDE.md`

- [ ] Add `apps/challenge` section to `CLAUDE.md` (models, import command, photo setting)
- [ ] Move this plan to `docs/plans/completed/`

## Post-Completion

**Manual verification:**
- Load the real `scores.json` + `messages_clean.json` via `import_challenge` command
- Open leaderboard, verify athlete ordering matches scratch/challenge `leaderboard.html`
- Open review page, verify photos load from ChatExport dir (update `CHALLENGE_CHAT_EXPORT_DIR` in `.env` if needed)
- Test add/delete workout as staff user and confirm leaderboard updates

**Deployment:**
- Set `CHALLENGE_CHAT_EXPORT_DIR` in production `.env` pointing to uploaded ChatExport directory
- Run `import_challenge` management command on production after deploy
