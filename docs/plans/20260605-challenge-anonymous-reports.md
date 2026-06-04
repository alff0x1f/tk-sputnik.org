# Анонимные жалобы (report) на странице участника челленджа

## Overview
- Добавить анонимным пользователям возможность пожаловаться на ошибочную или
  отсутствующую тренировку прямо на странице участника `/challenge/member/<telegram_id>/`.
- Жалоба привязывается к **сообщению** (группе сообщений по `primary_msg_id`), а не к
  конкретной тренировке — это покрывает и случай «тренировка есть, но неверная», и
  «тренировки нет, а должна быть».
- Текст жалобы обязателен. Кнопка «сообщить об ошибке» показывается на всех пузырях
  сообщений всем пользователям. Staff видит бейдж с количеством незакрытых жалоб и
  может их закрывать прямо на странице; всё хранится в БД и доступно в Django admin.

## Context (from discovery)
- Проект: Django 5.2, Python 3.14, `uv`, тесты через `pytest`.
- Затрагиваемые файлы:
  - `apps/challenge/models.py` — модели `Group`, `Athlete`, `Workout`, `SourceMessage`
  - `apps/challenge/views.py` — `member_detail`, существующие API-вьюхи (паттерн для новых)
  - `apps/challenge/urls.py` — маршруты
  - `apps/challenge/admin.py` — регистрация моделей в admin
  - `apps/challenge/templates/challenge/member.html` — шаблон страницы + JS (есть `getCsrfToken()`)
  - `apps/challenge/static/challenge/css/challenge.css` — стили
  - `apps/challenge/tests.py` — тесты
- Паттерны проекта:
  - API-вьюхи возвращают `JsonResponse`, парсят `json.loads(request.body)`, валидируют поля.
  - `except A, B:` без скобок (PEP 758) — **не «чинить»** добавлением скобок.
  - staff-вьюхи под `@staff_member_required`; анонимный POST под стандартной Django CSRF.
  - JS на странице использует `getCsrfToken()` (читает cookie `csrftoken`).
  - `member_detail` строит `groups` через `_group_messages`, у каждой группы есть `primary_msg_id`.
- `SourceMessage` PK = `msg_id` (IntegerField); `Athlete` PK = `telegram_id` (CharField).

## Development Approach
- **Testing approach**: Regular (код, затем тесты) — соответствует стилю проекта.
- Завершать каждую задачу полностью перед переходом к следующей.
- Небольшие сфокусированные изменения.
- **Каждая задача включает новые/обновлённые тесты** для изменённого кода (успех + ошибки).
- **Все тесты должны проходить перед началом следующей задачи.**
- Обновлять этот файл при изменении объёма работ.
- Запускать тесты после каждого изменения. Сохранять обратную совместимость.

## Testing Strategy
- **Unit/HTTP-тесты**: обязательны в каждой задаче (`django.test.TestCase`, `self.client`).
- **E2E**: в проекте нет UI e2e-фреймворка (Playwright/Cypress) — поведение JS проверяется
  через серверные тесты эндпоинтов и проверку наличия разметки в HTML.

## Progress Tracking
- Отмечать выполненное `[x]` сразу по завершении.
- Новые задачи помечать префиксом ➕, блокеры — ⚠️.
- Держать план в синхроне с фактической работой.

## Solution Overview
- Новая модель `Report` (FK на `SourceMessage` и `Athlete`) — вариант A из брейншторма.
- Два эндпоинта: анонимное создание (`POST .../member/<id>/api/report/`) и staff-резолв
  (`PUT|DELETE .../review/api/report/<pk>/`).
- `member_detail` для staff подгружает незакрытые жалобы и раскладывает по группам.
- Шаблон: кнопка + скрытая форма (всем), бейдж + список с кнопкой «Закрыть» (staff).
- Антиспам не делаем: только валидация длины текста (≤ 2000) и стандартная CSRF.

## Technical Details

### Модель `Report` (apps/challenge/models.py)
```python
class Report(models.Model):
    message = models.ForeignKey(
        SourceMessage, on_delete=models.CASCADE,
        related_name="reports", verbose_name="Сообщение",
    )
    athlete = models.ForeignKey(
        Athlete, on_delete=models.CASCADE,
        related_name="reports", verbose_name="Участник",
    )
    text = models.TextField("Текст жалобы")
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    resolved = models.BooleanField("Обработана", default=False)

    class Meta:
        verbose_name = "Жалоба"
        verbose_name_plural = "Жалобы"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Жалоба на #{self.message_id} ({self.created_at:%d.%m.%Y})"
```
Миграция через `makemigrations` (ожидается `0007_report.py`).

### Эндпоинты (apps/challenge/views.py)
- Константа модульного уровня `MAX_REPORT_LEN = 2000`.
- `api_report_create(request, telegram_id)` — `@require_http_methods(["POST"])`, **без**
  `staff_member_required`:
  - `get_object_or_404(Athlete, pk=telegram_id)` → 404 при отсутствии атлета;
  - `json.loads(request.body)` с `except json.JSONDecodeError, UnicodeDecodeError` → 400;
  - `text = (data.get("text") or "").strip()`; пусто → 400 `text required`;
    `len(text) > MAX_REPORT_LEN` → 400 `text too long`;
  - **привести `msg_id` к int до lookup** (как в `api_workout_create`):
    `int(data["msg_id"])`, затем `SourceMessage.objects.get(pk=...)` с
    `except SourceMessage.DoesNotExist, KeyError, TypeError, ValueError` → 400 `message not found`
    (ловим `ValueError`, т.к. строковый `msg_id` на SQLite-PK даёт `ValueError`, иначе — 500);
  - `Report.objects.create(message=message, athlete=athlete, text=text)`;
  - `JsonResponse({"ok": True}, status=201)`.

### CSRF для анонимного POST (важно)
`config/settings.py` включает `CsrfViewMiddleware`. JS читает токен из cookie `csrftoken`
(`getCsrfToken()`), но у анонима, не получавшего ответ, устанавливающий cookie, его может не
быть → POST упадёт с 403. Чтобы гарантировать наличие cookie, навесить `@ensure_csrf_cookie`
(`from django.views.decorators.csrf import ensure_csrf_cookie`) на `member_detail`.
- `api_report_detail(request, pk)` — `@staff_member_required`,
  `@require_http_methods(["PUT", "DELETE"])`:
  - DELETE → `report.delete()`, `HttpResponse(status=204)`;
  - PUT → `report.resolved = True`, `save(update_fields=["resolved"])`,
    `JsonResponse({"ok": True})`.

### Маршруты (apps/challenge/urls.py)
```python
path("member/<str:telegram_id>/api/report/", views.api_report_create,
     name="challenge-api-report-create"),
path("review/api/report/<int:pk>/", views.api_report_detail,
     name="challenge-api-report-detail"),
```

### member_detail (apps/challenge/views.py)
После построения `groups`, **только** для `request.user.is_staff`:
```python
primary_ids = [g["primary_msg_id"] for g in groups]
reports_by_msg = {}
for r in Report.objects.filter(message_id__in=primary_ids, resolved=False).order_by("created_at"):
    reports_by_msg.setdefault(r.message_id, []).append(r)
for g in groups:
    g["reports"] = reports_by_msg.get(g["primary_msg_id"], [])
```
Для анонимов ключ `reports` отсутствует — шаблонная разметка бейджа под
`{% if request.user.is_staff %}`.

### Шаблон (apps/challenge/templates/challenge/member.html)
- В `.msg-meta` каждого пузыря — кнопка `.msg-report-btn` (SVG-флажок),
  `onclick="openReportForm('{{ group.primary_msg_id }}')"`. Показывается всем, на всех пузырях.
- Скрытая форма под пузырём: `.report-form[data-report-msg]` с
  `<textarea class="report-text" maxlength="2000">` + кнопки Отправить/Отмена
  (`submitReport`/`cancelReport`).
- Для staff при `group.reports`: бейдж `.msg-report-badge` «⚠ N жалоб» и список
  `.report-list` из `.report-item[data-report-id]` (текст + кнопка «Закрыть» → `resolveReport`).
- JS:
  - `openReportForm(msgId)` / `cancelReport(msgId)` — показать/скрыть форму;
  - `submitReport(msgId)` → POST `member/<ATHLETE_ID>/api/report/`, body `{msg_id, text}`,
    заголовок `X-CSRFToken` через `getCsrfToken()`; пустой текст блокируется на клиенте;
    при успехе форма прячется, кнопка `.msg-report-btn` для этого пузыря → «Отправлено ✓»
    и **дизейблится** (`disabled`), textarea очищается — чтобы исключить повторную отправку
    (без перезагрузки страницы);
  - `resolveReport(pk)` → PUT `review/api/report/<pk>/`; при успехе убрать `.report-item` из DOM.

### CSS (apps/challenge/static/challenge/css/challenge.css)
Добавить `.msg-report-btn`, `.report-form`, `.report-text`, `.report-actions`,
`.msg-report-badge`, `.report-list`, `.report-item` в стиле существующих классов
(`.msg-add-btn`, `.wic-create-form` и т.п.).

## What Goes Where
- **Implementation Steps**: модель, миграция, admin, эндпоинты, маршруты, изменение
  `member_detail`, шаблон, JS, CSS, тесты, документация.
- **Post-Completion**: ручная проверка UX в браузере, применение миграции на проде.

## Implementation Steps

### Task 1: Модель Report и миграция

**Files:**
- Modify: `apps/challenge/models.py`
- Create: `apps/challenge/migrations/0007_report.py`
- Modify: `apps/challenge/tests.py`

- [ ] добавить модель `Report` в `apps/challenge/models.py` (поля, `Meta`, `__str__` как в Technical Details)
- [ ] сгенерировать миграцию: `uv run python manage.py makemigrations challenge` (ожидается `0007_report.py`)
- [ ] написать тест: создание `Report` через ORM, проверка дефолтов (`resolved is False`, `created_at` заполнен)
- [ ] написать тест: `__str__` возвращает строку с `#<msg_id>`
- [ ] запустить тесты: `uv run pytest apps/challenge/tests.py` — должны пройти перед Task 2

### Task 2: Регистрация Report в admin

**Files:**
- Modify: `apps/challenge/admin.py`

- [ ] зарегистрировать `ReportAdmin` с `list_display = ["message", "athlete", "short_text", "created_at", "resolved"]`
- [ ] добавить `list_filter = ["resolved", "created_at"]`, `list_editable = ["resolved"]`, `list_select_related = ["message", "athlete"]`
- [ ] реализовать метод `short_text` (обрезка `text` до ~60 символов, с `@admin.display(description=...)`)
- [ ] написать тест: admin-страница списка `Report` открывается staff-пользователем (200)
- [ ] запустить тесты — должны пройти перед Task 3

### Task 3: Эндпоинт создания жалобы (анонимный)

**Files:**
- Modify: `apps/challenge/views.py`
- Modify: `apps/challenge/urls.py`
- Modify: `apps/challenge/tests.py`

- [ ] добавить константу `MAX_REPORT_LEN = 2000` и импорт `Report` в `views.py`
- [ ] реализовать `api_report_create(request, telegram_id)` (валидация атлета, JSON, текста; `int(msg_id)` до lookup с ловлей `ValueError`; создание)
- [ ] добавить маршрут `challenge-api-report-create` в `urls.py`
- [ ] написать тест `test_report_create_anonymous` → 201, запись создана, `resolved=False`
- [ ] написать тесты ошибок: `test_report_create_empty_text` → 400, `test_report_create_too_long` → 400, `test_report_create_unknown_msg` → 400, `test_report_create_bad_msg_id` (нечисловой `msg_id`) → 400, `test_report_create_unknown_athlete` → 404
- [ ] написать тест `test_report_create_csrf_enforced` — `Client(enforce_csrf_checks=True)`: с валидным токеном → 201
- [ ] запустить тесты — должны пройти перед Task 4

### Task 4: Эндпоинт резолва жалобы (staff)

**Files:**
- Modify: `apps/challenge/views.py`
- Modify: `apps/challenge/urls.py`
- Modify: `apps/challenge/tests.py`

- [ ] реализовать `api_report_detail(request, pk)` (`@staff_member_required`, PUT → resolved, DELETE → удаление)
- [ ] добавить маршрут `challenge-api-report-detail` в `urls.py`
- [ ] написать тест `test_report_resolve_requires_staff` → аноним PUT редиректит на логин
- [ ] написать тест `test_report_resolve_sets_resolved` → staff PUT → `resolved=True`
- [ ] написать тест `test_report_delete` → staff DELETE → 204, запись удалена
- [ ] запустить тесты — должны пройти перед Task 5

### Task 5: Подгрузка жалоб в member_detail

**Files:**
- Modify: `apps/challenge/views.py`
- Modify: `apps/challenge/tests.py`

- [ ] навесить `@ensure_csrf_cookie` на `member_detail` (гарантирует cookie `csrftoken` для анонима)
- [ ] в `member_detail` после построения `groups` для staff собрать незакрытые `Report` по `primary_msg_id` и положить в `g["reports"]`
- [ ] убедиться, что для анонимов запрос не выполняется и ключ `reports` отсутствует
- [ ] написать тест: ответ member-страницы анониму ставит cookie `csrftoken`
- [ ] написать тест: для staff в контексте/HTML присутствуют жалобы соответствующего сообщения
- [ ] написать тест: закрытые (`resolved=True`) жалобы не попадают в выдачу
- [ ] запустить тесты — должны пройти перед Task 6

### Task 6: Шаблон — кнопка и форма жалобы (для всех)

**Files:**
- Modify: `apps/challenge/templates/challenge/member.html`
- Modify: `apps/challenge/tests.py`

- [ ] добавить кнопку `.msg-report-btn` в `.msg-meta` каждого пузыря (SVG-флажок, `openReportForm`)
- [ ] добавить скрытую форму `.report-form[data-report-msg]` с `<textarea.report-text maxlength="2000">` и кнопками Отправить/Отмена
- [ ] добавить JS `openReportForm`, `cancelReport`, `submitReport` (POST с `getCsrfToken()`, пустой текст блокируется; при успехе кнопка → «Отправлено ✓» + `disabled`, textarea очищается — без повторной отправки)
- [ ] написать тест: на странице участника (аноним) присутствует разметка кнопки/формы жалобы на всех пузырях
- [ ] запустить тесты — должны пройти перед Task 7

### Task 7: Шаблон — бейдж и резолв (для staff)

**Files:**
- Modify: `apps/challenge/templates/challenge/member.html`
- Modify: `apps/challenge/tests.py`

- [ ] добавить под `{% if request.user.is_staff and group.reports %}` бейдж `.msg-report-badge` и список `.report-list`/`.report-item`
- [ ] добавить JS `resolveReport(pk)` (PUT, удаление `.report-item` из DOM)
- [ ] написать тест `test_member_page_shows_badge_for_staff` → staff видит «жалоб» в HTML, аноним не видит
- [ ] запустить тесты — должны пройти перед Task 8

### Task 8: Стили CSS

**Files:**
- Modify: `apps/challenge/static/challenge/css/challenge.css`

- [ ] добавить стили `.msg-report-btn`, `.report-form`, `.report-text`, `.report-actions`, `.msg-report-badge`, `.report-list`, `.report-item` в стиле существующих классов
- [ ] проверить визуально, что элементы не ломают раскладку пузырей (ручная проверка в Post-Completion)
- [ ] (нет нового кода с логикой — отдельных тестов не требуется; функциональность покрыта Task 6–7)

### Task 9: Verify acceptance criteria
- [ ] проверить, что все требования из Overview реализованы (анонимная жалоба, привязка к сообщению, обязательный текст, кнопка на всех пузырях, бейдж/резолв для staff, admin)
- [ ] проверить обработку ошибок (пустой/длинный текст, неизвестное сообщение/атлет, доступ не-staff)
- [ ] прогнать линтер и формат: `uv run ruff check .` и `uv run ruff format .`
- [ ] прогнать весь набор тестов: `uv run pytest`
- [ ] убедиться, что миграции применяются: `uv run python manage.py migrate`

### Task 10: [Final] Документация
- [ ] добавить в `CLAUDE.md` в раздел «Challenge app» заметку про модель `Report` и эндпоинты жалоб (создание анонимом, резолв staff, бейдж на member-странице)
- [ ] переместить этот план в `docs/plans/completed/`

## Post-Completion
*Items requiring manual intervention or external systems — informational only*

**Manual verification:**
- Открыть `/challenge/member/<id>/` анонимом: отправить жалобу, проверить, что кнопка
  меняется на «Отправлено ✓» без перезагрузки и запись появляется в admin.
- Открыть ту же страницу staff-пользователем: проверить бейдж «⚠ N жалоб», раскрытие
  текста и кнопку «Закрыть» (жалоба исчезает из списка, `resolved=True` в admin).
- Проверить вёрстку формы/бейджа на мобильной ширине.

**External system updates:**
- Применить миграцию `0007_report` на проде (PostgreSQL) при деплое.
