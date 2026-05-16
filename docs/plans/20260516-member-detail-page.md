# Member Detail Page — Challenge App

## Overview

Staff-only page at `/challenge/member/<telegram_id>/` showing all messages from a specific athlete in read-only chat format. Messages linked to workouts (via `msg_id`) display an embedded workout info card. Purpose: quickly audit whether workouts are correctly attributed and none are missed.

Integrates with the existing challenge app — reuses `challenge.css`, `challenge-photo` URL, and `@staff_member_required`.

## Context (from discovery)

- **Models**: `Athlete` (telegram_id PK, name), `Workout` (FK athlete, msg_id nullable, base/streak/total_points), `SourceMessage` (msg_id PK, from_name, date, text, photos JSONField)
- **Key invariant**: `SourceMessage.from_name` always exactly matches `Athlete.name` (guaranteed by import)
- **Existing patterns**: `review` view passes data as server-side context; `leaderboard` view renders athlete list; `challenge_photo` serves files; `@staff_member_required` used on review/API views
- **Base template**: `demo/base.html` with `extra_css` block; `challenge.css` loaded via `{% static %}`
- **Test style**: `django.test.TestCase` with `self.client`, tests in `apps/challenge/tests.py`

## Development Approach

- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- Make small, focused changes
- Every task must include new/updated tests
- All tests must pass before starting next task

## Testing Strategy

- **Unit tests**: view returns 200 for staff, 302 redirect for anonymous/non-staff; correct messages shown; workout card data present; date separators; 404 for unknown telegram_id
- **No e2e tests**: project has no Playwright/Cypress setup

## Progress Tracking

- Mark completed items with `[x]` immediately when done
- Add newly discovered tasks with ➕ prefix
- Document issues/blockers with ⚠️ prefix

## Solution Overview

Server-rendered Django template, no JavaScript. View fetches messages by `from_name`, builds a workout lookup dict by `msg_id`, zips them together and passes to template. Template renders chat-style bubbles with date separators; messages with a workout get an embedded info card. Leaderboard shows athlete name as a link (only for staff users).

## Technical Details

**View data flow:**
1. `athlete = get_object_or_404(Athlete, pk=telegram_id)`
2. `messages = SourceMessage.objects.filter(from_name=athlete.name).order_by("date", "msg_id")`
3. `workouts_by_msg = {w.msg_id: w for w in Workout.objects.filter(athlete=athlete, msg_id__isnull=False)}`
4. Build `cards = [(msg, workouts_by_msg.get(msg.msg_id)) for msg in messages]` — list of `(SourceMessage, Workout|None)`
5. Compute `total_points = athlete.workouts.aggregate(Sum("total_points"))["total_points__sum"] or 0`
6. Compute `workout_count = athlete.workouts.count()`

**Template context:** `athlete`, `cards` (list of tuples), `total_points`, `workout_count`

**Date separator logic:** in template, use `{% ifchanged msg.date %}` to emit a date heading when the date changes.

**Leaderboard change:** wrap athlete name with `{% if request.user.is_staff %}<a href="...">{% endif %}`.

## What Goes Where

**Implementation Steps** — code changes with checkboxes below.

**Post-Completion** — manual staff browser test to verify page looks correct with real data.

## Implementation Steps

### Task 1: Add `member_detail` view

**Files:**
- Modify: `apps/challenge/views.py`

- [ ] import `Sum` from `django.db.models` (already imported — verify)
- [ ] add `member_detail(request, telegram_id)` view with `@staff_member_required`
- [ ] fetch athlete via `get_object_or_404(Athlete, pk=telegram_id)`
- [ ] query messages filtered by `from_name=athlete.name`, ordered by `("date", "msg_id")`
- [ ] build `workouts_by_msg` dict from athlete's workouts with non-null `msg_id`
- [ ] build `cards` list of `(msg, workout_or_none)` tuples
- [ ] compute `total_points` and `workout_count` aggregates
- [ ] render `challenge/member.html` with context

### Task 2: Register URL

**Files:**
- Modify: `apps/challenge/urls.py`

- [ ] add `path("member/<str:telegram_id>/", views.member_detail, name="challenge-member")` to `urlpatterns`

### Task 3: Create `member.html` template

**Files:**
- Create: `apps/challenge/templates/challenge/member.html`

- [ ] extend `demo/base.html`, load `{% static %}`, link `challenge.css`
- [ ] header section: athlete name, back link to leaderboard, total points, workout count
- [ ] loop over `cards` with `{% ifchanged msg.date %}` for date separator headings
- [ ] message bubble: show `msg.text` (if non-empty) and photos via `{% url 'challenge-photo' filename %}`
- [ ] workout card (inside bubble when `workout` is not None): activity display, date, distance + pace (if set), points breakdown (`base + streak = total`)
- [ ] visually distinguish messages with workout (e.g. highlighted border/background) from plain messages

### Task 4: Update leaderboard template

**Files:**
- Modify: `apps/challenge/templates/challenge/leaderboard.html`

- [ ] wrap athlete name `<span>` with `{% if request.user.is_staff %}<a href="{% url 'challenge-member' athlete.telegram_id %}">...</a>{% else %}...{% endif %}`
- [ ] verify leaderboard still renders correctly for non-staff (name shown without link)

### Task 5: Write tests

**Files:**
- Modify: `apps/challenge/tests.py`

- [ ] add `MemberDetailViewTests(TestCase)` with `setUp`: create staff user, athlete, 2 SourceMessages (one with workout, one plain), one message from different athlete
- [ ] test: anonymous user GET → 302 redirect to login
- [ ] test: non-staff authenticated user GET → 302 redirect to login
- [ ] test: staff user GET `/challenge/member/<id>/` → 200 OK
- [ ] test: 404 for unknown telegram_id
- [ ] test: only messages matching `from_name` appear in response (other athlete's message absent)
- [ ] test: message with linked workout contains workout info (activity, points) in response content
- [ ] test: message without workout does not contain workout card class/marker
- [ ] run `uv run pytest apps/challenge/tests.py` — all pass

### Task 6: Verify acceptance criteria

- [ ] run full test suite: `uv run pytest`
- [ ] run linter: `uv run ruff check .`
- [ ] manually open `/challenge/member/<real_id>/` as staff — check layout, date separators, workout cards, photos
- [ ] check leaderboard: athlete names link for staff, plain text for anonymous

### Task 7: Update documentation and archive plan

**Files:**
- Modify: `CLAUDE.md`
- Move: this plan to `docs/plans/completed/`

- [ ] add `member_detail` to the challenge app section in `CLAUDE.md` under "Review page" bullet (one line)
- [ ] move plan: `mkdir -p docs/plans/completed && mv docs/plans/20260516-member-detail-page.md docs/plans/completed/`

## Post-Completion

**Manual verification:**
- Open `/challenge/member/<real_telegram_id>/` in browser as staff, confirm correct messages load, workout cards show correct data, photos render
- Open leaderboard as anonymous user, confirm names are plain text (no links)
