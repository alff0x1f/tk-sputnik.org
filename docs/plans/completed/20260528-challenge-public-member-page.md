# Challenge: открыть страницу участника и убрать список тренировок из лидерборда

## Overview

- Страница `/challenge/member/<telegram_id>/` была доступна только staff — открыть для всех
- На странице `/challenge/` (лидерборд) убрать раскрывающийся список тренировок каждого участника
- Ссылка на страницу участника в лидерборде — показывать всем, а не только staff

## Context (from discovery)

- Файлы: `apps/challenge/views.py`, `apps/challenge/templates/challenge/leaderboard.html`, `apps/challenge/tests.py`
- `member_detail` был защищён `@staff_member_required`
- `leaderboard` view собирал `workout_list` для каждого участника через отдельные запросы
- Шаблон лидерборда содержал expandable-секцию с workout-чипами и JS `toggleWorkouts()`

## Development Approach

- **testing approach**: Regular (код сначала, потом тесты)
- Изменения минимальные и локализованные

## Solution Overview

1. Убрать декоратор `@staff_member_required` с `member_detail`
2. Убрать цикл `workout_list` из `leaderboard()` — лишние N+1 запросы
3. Упростить шаблон: убрать expandable-логику, показать ссылку на участника всем
4. Обновить тесты под новое поведение

## Implementation Steps

### Task 1: Открыть member_detail для всех

**Files:**
- Modify: `apps/challenge/views.py`

- [x] убрать `@staff_member_required` с `member_detail` (строка 206)

### Task 2: Убрать workout_list из leaderboard view

**Files:**
- Modify: `apps/challenge/views.py`

- [x] убрать цикл `athlete.workout_list = list(Workout.objects.filter(...))` из `leaderboard()`

### Task 3: Упростить шаблон лидерборда

**Files:**
- Modify: `apps/challenge/templates/challenge/leaderboard.html`

- [x] убрать блок `lb-workouts` (workout-чипы)
- [x] убрать колонку `col-toggle` и SVG-стрелку
- [x] убрать атрибуты `onclick`, `role`, `aria-expanded` с `.lb-athlete`
- [x] убрать JS-функцию `toggleWorkouts`
- [x] показывать ссылку на участника всем (убрать условие `{% if request.user.is_staff %}`)

### Task 4: Обновить тесты

**Files:**
- Modify: `apps/challenge/tests.py`

- [x] `test_anonymous_redirected` → `test_anonymous_gets_200` (ожидать 200, не редирект)
- [x] `test_non_staff_redirected` → `test_non_staff_gets_200` (ожидать 200, не редирект)
- [x] `test_leaderboard_athlete_has_workout_list` → `test_leaderboard_athlete_workout_count` (проверять `workout_count`, не `workout_list`)

### Task 5: Проверка

- [x] запустить `uv run pytest apps/challenge/ -q` — 95 passed, 0 failed
