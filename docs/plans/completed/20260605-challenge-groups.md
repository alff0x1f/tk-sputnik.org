# Группы участников челленджа

## Overview
- Добавить понятие «группа» в приложение `apps/challenge`: участники («Первая группа», «Вторая группа», «42» и т.п.) распределяются администратором по группам.
- Решает задачу: админ может распределить людей по группам, а группы видны на публичной странице `/challenge/`.
- Интегрируется в существующий лидерборд (новая колонка), Django-админку (CRUD групп) и добавляет staff-only страницу распределения с автосохранением в стиле `/challenge/review/`.

## Context (from discovery)
- Файлы/компоненты:
  - `apps/challenge/models.py` — `Athlete` (PK `telegram_id` CharField, `name`), `Workout`, `SourceMessage`.
  - `apps/challenge/views.py` — `leaderboard()` рендерит `challenge/leaderboard.html`; staff-only `review()` + API `api_workout_create`/`api_workout_detail` (паттерн автосохранения); `member_detail()`.
  - `apps/challenge/urls.py` — `challenge-leaderboard` (`""`), `challenge-review`, `challenge-api-workout-*`, `challenge-photo`, `challenge-member`.
  - `apps/challenge/admin.py` — `AthleteAdmin`, `WorkoutAdmin`, `SourceMessageAdmin`.
  - `apps/challenge/templates/challenge/leaderboard.html` — таблица `.lb-table/.lb-header/.lb-row`, 4 колонки: `col-rank`, `col-name` (ссылка на `challenge-member`), `col-pts`, `col-cnt`. Наследует `demo/base.html`.
  - `apps/challenge/static/challenge/css/challenge.css` — стили лидерборда (`.lb-*`, `.col-*`).
  - `apps/challenge/templates/challenge/review.html` — образец автосохранения через `fetch`.
  - `apps/challenge/tests.py` — тесты на `django.test.TestCase` + `self.client`.
- Паттерны: staff-доступ через `@staff_member_required`; JSON API через `@require_http_methods`; автосохранение `fetch` + индикатор статуса.
- Зависимости: `select_related` для устранения N+1; CSRF в `fetch` (как в `review.html`).

## Development Approach
- **testing approach**: Regular (код → тесты в рамках той же задачи).
- Каждую задачу доводить до конца перед переходом к следующей.
- Маленькие сфокусированные изменения.
- **CRITICAL: каждая задача с изменением кода ОБЯЗАНА включать новые/обновлённые тесты** (success + error сценарии), отдельными пунктами чек-листа.
- **CRITICAL: все тесты должны проходить до начала следующей задачи.**
- **CRITICAL: при изменении объёма — обновлять этот файл плана.**
- Запускать тесты после каждого изменения: `uv run pytest apps/challenge/tests.py`.
- Сохранять обратную совместимость (поле `group` nullable, без потери данных).

## Testing Strategy
- **unit tests**: обязательны для каждой задачи (см. Development Approach).
- **e2e tests**: в проекте нет UI-e2e фреймворка (Playwright/Cypress) — покрываем поведение через Django `TestCase` + `self.client` (HTTP-уровень), включая рендер шаблонов и API.
- Команда тестов: `uv run pytest apps/challenge/tests.py` (полный набор: `uv run pytest`).

## Progress Tracking
- Отмечать выполненное `[x]` сразу.
- Новые задачи — с префиксом ➕.
- Блокеры — с префиксом ⚠️.
- Держать план в синхроне с реальной работой.

## Solution Overview
- Новая модель `Group` (имя + порядок); `Athlete.group` — `ForeignKey(SET_NULL, null=True)`, так что удаление группы не трогает участников.
- Лидерборд получает колонку «Группа» (между именем и очками); ранжирование остаётся общим по очкам (без секций, без фильтра — YAGNI).
- Создание/переименование/удаление групп — в Django-админке. Массовое распределение людей — на новой staff-only странице `/challenge/groups/` со списком `<select>` и автосохранением через PUT API.
- Ключевые решения: `SET_NULL` (безопасное удаление группы), nullable `group` (после импорта все нераспределены), `order` (управляемый порядок вывода), дублирование назначения группы (в админке и на странице) — намеренное, страница для массовой операции.

## Technical Details
- `Group`: `name = CharField("Название", max_length=255, unique=True)`, `order = IntegerField("Порядок", default=0)`, `Meta.ordering = ["order", "name"]`, `verbose_name`/`verbose_name_plural` = «Группа»/«Группы», `__str__` → `name`.
- `Athlete.group = ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, related_name="athletes", verbose_name="Группа")`.
- API `PUT /challenge/groups/api/athlete/<str:telegram_id>/`, тело `{"group_id": <id> | null}` → `200 {"ok": true}`; неизвестная группа → `400`; неизвестный участник → `404`.
- Шаблон `groups.html`: на участника — имя + `<select>` (опция «— без группы —» с пустым value + все группы; выбранная = текущий `group_id`); `change` → `fetch` PUT с CSRF, индикатор «✓ сохранено»/«ошибка»; кнопка «назад к лидерборду».

## What Goes Where
- **Implementation Steps** (чекбоксы): модель + миграция, лидерборд, страница распределения + API, админка, верификация, документация.
- **Post-Completion** (без чекбоксов): ручная проверка UX в браузере, создание реальных групп в админке.

## Implementation Steps

### Task 1: Модель Group и FK Athlete.group + миграция

**Files:**
- Modify: `apps/challenge/models.py`
- Create: `apps/challenge/migrations/0002_*.py` (через `makemigrations`)
- Modify: `apps/challenge/tests.py`

- [x] добавить модель `Group` в `apps/challenge/models.py` (`name` unique, `order`, `Meta.ordering`, verbose_name, `__str__`)
- [x] добавить поле `group = ForeignKey(Group, on_delete=SET_NULL, null=True, blank=True, related_name="athletes", verbose_name="Группа")` в `Athlete`
- [x] сгенерировать миграцию: `uv run python manage.py makemigrations challenge` (новая модель + nullable FK, без data-сида) — `0005_group_athlete_group.py`
- [x] применить миграцию: `uv run python manage.py migrate`
- [x] написать тест: удаление `Group` → у участника `group` становится `NULL`, участник сохраняется (SET_NULL)
- [x] написать тест: участник создаётся без группы (`group` = None по умолчанию)
- [x] запустить тесты — должны пройти до следующей задачи

### Task 2: Колонка «Группа» на лидерборде

**Files:**
- Modify: `apps/challenge/views.py`
- Modify: `apps/challenge/templates/challenge/leaderboard.html`
- Modify: `apps/challenge/static/challenge/css/challenge.css`
- Modify: `apps/challenge/tests.py`

- [x] в `leaderboard()` добавить `.select_related("group")` к queryset `Athlete` (избежать N+1)
- [x] в `leaderboard.html` добавить 5-ю колонку «Группа» между именем и очками: заголовок `<span class="lb-col col-group">Группа</span>` и ячейку `{{ athlete.group.name|default:"—" }}`
- [x] в `leaderboard.html` добавить для staff ссылку «Распределение по группам» на `challenge-groups`, обёрнутую в `{% if request.user.is_staff %}` (URL + минимальная staff-only вьюха `groups` зарегистрированы, расширяются в Task 4)
- [x] в `challenge.css` добавить `.col-group` и пересчитать ширины колонок в `.lb-header`/`.lb-row` под 5 колонок
- [x] написать тест: участник с группой показывает её название; нераспределённый — «—»
- [x] написать тест: staff видит ссылку «Распределение по группам»; аноним/обычный юзер — нет
- [x] запустить тесты — должны пройти до следующей задачи

### Task 3: API назначения группы участнику

**Files:**
- Modify: `apps/challenge/views.py`
- Modify: `apps/challenge/urls.py`
- Modify: `apps/challenge/tests.py`

- [x] добавить вьюху `api_athlete_group()` с `@staff_member_required` и `@require_http_methods(["PUT"])` в `views.py`
- [x] логика: распарсить JSON; найти `Athlete` (404 если нет); `group_id` null → снять группу; иначе `Group.objects.get(pk)` (400 если нет); сохранить; вернуть `200 {"ok": true}`; невалидный JSON → 400
- [x] добавить маршрут `path("groups/api/athlete/<str:telegram_id>/", views.api_athlete_group, name="challenge-api-athlete-group")` в `urls.py`
- [x] написать тест: staff назначает группу → 200 и записано в БД
- [x] написать тест: `group_id: null` → группа снята
- [x] написать тест (error): несуществующая группа → 400; несуществующий участник → 404; невалидный JSON → 400; неавторизованный → редирект/403; не-PUT методы (GET/POST) отклоняются
- [x] запустить тесты — должны пройти до следующей задачи

### Task 4: Страница распределения /challenge/groups/

**Files:**
- Modify: `apps/challenge/views.py`
- Modify: `apps/challenge/urls.py`
- Create: `apps/challenge/templates/challenge/groups.html`
- Modify: `apps/challenge/tests.py`

- [x] добавить вьюху `groups()` с `@staff_member_required`: `athletes = Athlete.objects.select_related("group").order_by("name")`, `groups = Group.objects.all()`, рендер `challenge/groups.html`
- [x] добавить маршрут `path("groups/", views.groups, name="challenge-groups")` в `urls.py`
- [x] создать `groups.html` (наследует `demo/base.html`): список участников, у каждого имя + `<select>` (опция «— без группы —» с пустым value + все группы, выбранная = текущий `group_id`); кнопка «назад к лидерборду»
- [x] добавить JS: на `change` `<select>` — `fetch` PUT на `challenge-api-athlete-group` с CSRF-токеном и `{"group_id": ...}` (пустое value → null), индикатор «✓ сохранено»/«ошибка» рядом со строкой (паттерн как в `review.html`)
- [x] написать тест: аноним → редирект на логин; обычный юзер → отказ; staff → 200, в контексте все участники и все группы
- [x] написать тест: в HTML страницы для staff присутствуют `<select>` и опции групп с правильным выбранным значением
- [x] запустить тесты — должны пройти до следующей задачи

### Task 5: Админка для групп

**Files:**
- Modify: `apps/challenge/admin.py`
- Modify: `apps/challenge/tests.py`

- [x] зарегистрировать `GroupAdmin`: `list_display = ["name", "order"]`, `list_editable = ["order"]`
- [x] в `AthleteAdmin`: добавить `group` в `list_display`, `list_filter = ["group"]`, `list_select_related = ["group"]`
- [x] написать тест: список `Group` в админке доступен staff (200) и показывает группы
- [x] написать тест: создание группы через админку проставляет её в `Athlete` (или фильтр по группе в `AthleteAdmin` работает)
- [x] запустить тесты — должны пройти до следующей задачи

### Task 6: Verify acceptance criteria
- [x] проверить все требования из Overview: модель, колонка на `/challenge/`, страница распределения с автосохранением, CRUD групп в админке
- [x] проверить edge-cases: нераспределённый участник, удаление группы (SET_NULL), снятие группы через API
- [x] запустить полный набор: `uv run pytest` — 348 passed
- [x] прогнать линт/формат: `uv run ruff check .` (All checks passed) и `uv run ruff format .` (79 files already formatted)

### Task 7: [Final] Документация
- [x] обновить раздел «Challenge app» в `CLAUDE.md`: модель `Group`, поле `Athlete.group`, страница `/challenge/groups/`, колонка «Группа» на лидерборде, API `challenge-api-athlete-group`
- [x] переместить этот план в `docs/plans/completed/`

## Post-Completion
*Items requiring manual intervention or external systems - no checkboxes, informational only*

**Manual verification:**
- Открыть `/challenge/groups/` под staff-аккаунтом, проверить автосохранение `<select>` и индикатор статуса в браузере.
- Проверить вёрстку колонки «Группа» на `/challenge/` (десктоп + мобильный).

**External system updates:**
- Создать реальные группы («Первая группа», «Вторая группа», «42») в Django-админке и распределить участников (одноразовая ручная операция, миграцией не сидим).
