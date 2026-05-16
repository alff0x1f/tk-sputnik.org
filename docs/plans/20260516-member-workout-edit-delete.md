# Inline Edit/Delete for Workouts on Member Detail Page

## Overview

Add Edit and Delete buttons to each workout info card on `/challenge/member/<telegram_id>/` so staff can correct or remove workout records directly from the chat-style view — without navigating to the review page.

- Clicking **Ред.** toggles the card into an inline form (activity, date, distance, pace)
- Saving PUTs to the existing API and updates the card DOM in place
- Clicking **Дел.** confirms and DELETEs via the existing API, then reloads the page
- No new API endpoints or Django views — purely a template + CSS change

## Context (from discovery)

- Files involved: `apps/challenge/templates/challenge/member.html`, `apps/challenge/static/challenge/css/challenge.css`
- Existing API: `PUT /challenge/review/api/workout/<pk>/` and `DELETE /challenge/review/api/workout/<pk>/` in `views.py:119`
- Workout model fields relevant for the form: `activity`, `date`, `distance_km`, `pace_min_per_km`
- Existing tests live in `MemberDetailViewTests` (tests.py:850) — setUp already creates `self.workout` and `self.staff`
- Pattern source: `review.html` uses `getCsrfToken()` cookie, `fetch()`, vanilla JS, `data-workout-id` attribute

## Development Approach

- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- Every task with code changes includes new/updated tests
- All tests must pass before starting the next task

## Testing Strategy

- **Unit tests**: HTTP assertions via `self.client` in `MemberDetailViewTests`
- No e2e tests in this project
- Run: `uv run pytest apps/challenge/tests.py`

## Progress Tracking

- Mark completed items with `[x]` immediately when done
- Add newly discovered tasks with ➕ prefix
- Document blockers with ⚠️ prefix

## Solution Overview

Server-renders the page as before. Each `.workout-info-card` gains two small action buttons in its header. A hidden `<div class="wic-edit-form">` lives inside the same card. JS functions `editWorkout(id)` / `cancelEdit(id)` / `saveWorkout(id)` / `deleteWorkout(id)` toggle visibility and call the existing API. After save, the displayed text is updated in the DOM. After delete, `location.reload()` refreshes stats in the page header.

## Technical Details

- `data-workout-id="{{ workout.pk }}"` added to `.workout-info-card`
- `data-workout-date`, `data-workout-activity`, `data-workout-distance`, `data-workout-pace` on the card for pre-filling the form
- ACT_NAMES constant in JS maps activity keys to display labels (matches `review.html`)
- Save response `{workout: {base_points, streak_bonus, total_points}}` used to update `.wic-pts` text

## What Goes Where

**Implementation Steps** below = all changes are in this repo.

**Post-Completion** (manual):
- Smoke-test in browser: open a member page, edit a workout, verify points update; delete a workout, verify page reloads with updated stats

## Implementation Steps

### Task 1: Add edit/delete buttons and inline form to member.html

**Files:**
- Modify: `apps/challenge/templates/challenge/member.html`

- [x] Add `data-workout-id`, `data-workout-date`, `data-workout-activity`, `data-workout-distance`, `data-workout-pace` attributes to `.workout-info-card`
- [x] Add **Ред.** and **Дел.** buttons to `.wic-header` (only rendered when `workout` exists, so no guard needed)
- [x] Add hidden `.wic-edit-form` div inside the card with `<select>` for activity, `<input type="date">`, two `<input type="number">` for distance and pace, plus Save/Cancel buttons
- [x] Add `<script>` block at bottom of `{% block content %}` with:
  - `getCsrfToken()` (cookie extraction — same as review.html)
  - `ACT_NAMES` dict
  - `editWorkout(id)` — hide `.wic-view`, show `.wic-edit-form`, pre-fill fields from data attributes
  - `cancelEdit(id)` — reverse of above
  - `saveWorkout(id)` — collect form values, `fetch PUT`, on success update `.wic-activity`, `.wic-date`, `.wic-dist`, `.wic-pace`, `.wic-pts`, update `data-*` attributes, call `cancelEdit`
  - `deleteWorkout(id)` — `confirm()`, `fetch DELETE`, on success `location.reload()`

### Task 2: Add CSS for edit buttons and inline form

**Files:**
- Modify: `apps/challenge/static/challenge/css/challenge.css`

- [ ] Add `.wic-actions` flex container (positioned top-right in `.wic-header`)
- [ ] Style `.wic-btn-edit` and `.wic-btn-delete` (small, muted, hover state)
- [ ] Style `.wic-edit-form` (padding, gap, label+input layout matching the `.workout-form` style from review page)
- [ ] Ensure `.wic-view` and `.wic-edit-form` are toggled via `display:none` (no additional CSS transition needed)

### Task 3: Add tests for edit/delete button presence

**Files:**
- Modify: `apps/challenge/tests.py`

- [ ] Add `test_workout_card_has_edit_button` — staff GET returns HTML containing `editWorkout` and `deleteWorkout` JS calls for the workout's pk
- [ ] Add `test_workout_card_buttons_absent_without_workout` — message bubble without a workout has no edit/delete buttons
- [ ] Run tests: `uv run pytest apps/challenge/tests.py::MemberDetailViewTests` — must all pass

### Task 4: Verify acceptance criteria

- [ ] Verify edit button toggles card to form and back with Cancel
- [ ] Verify save sends PUT and updates points in the card without page reload
- [ ] Verify delete sends DELETE and page reloads with updated athlete stats
- [ ] Run full test suite: `uv run pytest`
- [ ] Run linter: `uv run ruff check .`

### Task 5: Update documentation

- [ ] Update CLAUDE.md if new patterns were introduced (likely not needed — no new API/view)
- [ ] Move this plan to `docs/plans/completed/`

## Post-Completion

**Manual verification:**
- Open `/challenge/member/<id>/` as staff, edit a workout, confirm card updates without reload
- Delete a workout, confirm page reloads and header counts update
- Verify non-staff users still cannot reach `/challenge/review/api/workout/<pk>/` (existing auth unchanged)
