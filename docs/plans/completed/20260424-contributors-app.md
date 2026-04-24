# Contributors App

## Overview

Страница `/contributors/` с таблицей взносов участников турклуба Спутник. Данные живут на kolco24.ru и синхронизируются в локальную БД через management command `sync_contributors`, запускаемый cron-ом.

Кнопка "Взнос" ведёт на `https://kolco24.ru/donate` (внешняя ссылка).

## Context (from discovery)

- Файлы-образцы: `apps/demo/views.py`, `apps/demo/urls.py`, `apps/demo/tests.py`, `apps/demo/templates/demo/members.html`
- Логика построения таблицы: `scratch/kolco24/donate/views.py` → `build_donor_table()`
- Оригинальные модели: `scratch/kolco24/donate/models.py`
- Регистрация приложений: `config/settings.py` INSTALLED_APPS, `config/urls.py`
- Тесты: `pytest` + `django.test.TestCase` + `self.client`

## Development Approach

- **Testing approach**: Regular (code first, then tests)
- Каждая задача завершается написанием тестов и `uv run pytest`
- Маленькие сфокусированные изменения

## Testing Strategy

- Unit-тесты для моделей и логики `build_donor_table()`
- HTTP-тесты через `self.client` (статус 200, правильный шаблон, контекст)
- Тест management command с mock HTTP-ответом

## Progress Tracking

- `[x]` — выполнено
- `➕` — обнаруженная задача
- `⚠️` — блокер

## Solution Overview

Новое приложение `apps/contributors` с локальными копиями трёх моделей kolco24 (`ClubMember`, `DonationPeriod`, `MemberDonation`). Management command `sync_contributors` делает GET к `KOLCO24_API_URL` и делает upsert всех данных в транзакции. View строит таблицу из локальной БД по той же логике, что `build_donor_table()` на kolco24. Шаблон — упрощённая версия `members.html` без stats-карточек, без тулбара фильтров, без бейджей школ.

## Technical Details

**API-формат (GET `KOLCO24_API_URL`):**
```json
{
  "periods": [{"id": 1, "name": "весна 2024", "date": "2024-03-01", "is_active": true}],
  "members": [{"id": 5, "name": "Алексей Костров", "label": "Горная школа"}],
  "donations": [{"member_id": 5, "period_id": 1, "is_paid": true,
                 "amount": "1500.00", "paid_date": "2024-04-10", "recipient": "sbp", "note": ""}]
}
```

**Метка участника:** поле `label` в API (соответствует `notes` на kolco24) — свободный текст ("Горная школа", "Вечный участник"). Пустое — ничего не показываем.

**Сортировка строк:** сначала оплатившие текущий период, затем остальные по имени.

**Текущий период:** последний активный период с `date <= today`.

## What Goes Where

**Implementation Steps** — всё ниже реализуется в этом репозитории.

**Post-Completion** — эндпоинт на kolco24.ru описан в `todo_kolco24.md`; cron на сервере настраивается отдельно.

## Implementation Steps

### Task 1: Модели `apps/contributors`

**Files:**
- Create: `apps/contributors/__init__.py`
- Create: `apps/contributors/apps.py`
- Create: `apps/contributors/models.py`
- Create: `apps/contributors/migrations/__init__.py`
- Modify: `config/settings.py`

- [x] создать `apps/contributors/__init__.py` (пустой)
- [x] создать `apps/contributors/apps.py` по образцу `apps/demo/apps.py`
- [x] создать `apps/contributors/models.py` с тремя моделями:
  - `ClubMember(external_id, name, label)`
  - `DonationPeriod(external_id, name, date, is_active)`
  - `MemberDonation(member FK, period FK, is_paid, amount, paid_date, recipient, note)` с `unique_together`
- [x] добавить `'apps.contributors'` в `INSTALLED_APPS`
- [x] выполнить `uv run python manage.py makemigrations contributors`
- [x] выполнить `uv run python manage.py migrate`
- [x] написать тесты: создание экземпляров всех трёх моделей, проверка `unique_together`
- [x] `uv run pytest` — должно пройти

### Task 2: Admin

**Files:**
- Create: `apps/contributors/admin.py`

- [x] зарегистрировать все три модели в admin с полезными `list_display`
- [x] `uv run pytest` — должно пройти

### Task 3: Management command `sync_contributors`

**Files:**
- Create: `apps/contributors/management/__init__.py`
- Create: `apps/contributors/management/commands/__init__.py`
- Create: `apps/contributors/management/commands/sync_contributors.py`
- Modify: `.env.example`

- [x] создать `sync_contributors` с методом `handle()`
- [x] читать `KOLCO24_API_URL` из `os.environ`; завершаться с ошибкой если не задан
- [x] GET-запрос к API через `urllib.request` (без новых зависимостей)
- [x] upsert `DonationPeriod` через `update_or_create(external_id=...)`
- [x] upsert `ClubMember` через `update_or_create(external_id=...)`
- [x] upsert `MemberDonation` через `update_or_create(member=..., period=...)` с маппингом `member_id`/`period_id` → локальные FK через `external_id`
- [x] всё в одной `transaction.atomic()`
- [x] добавить `KOLCO24_API_URL=` в `.env.example`
- [x] написать тест: mock HTTP-ответ (минимальный JSON) → проверить что объекты созданы в БД
- [x] написать тест: повторный запуск не создаёт дубликаты (idempotent)
- [x] `uv run pytest` — должно пройти

### Task 4: View и URL

**Files:**
- Create: `apps/contributors/views.py`
- Create: `apps/contributors/urls.py`
- Modify: `config/urls.py`

- [x] создать `contributors_view` в `views.py`, вызывающую `build_donor_table()` и передающую результат в шаблон
- [x] реализовать `build_donor_table()` по образцу `scratch/kolco24/donate/views.py`:
  - периоды: только `is_active=True`, порядок по `date` (старый → новый)
  - текущий период: последний с `date <= today`
  - строки: `{member, cells: [True/False/None, ...], paid_current}`
  - сортировка: `(0 if paid_current else 1, member.name)`
- [x] создать `urls.py` с `path("", views.contributors_view, name="contributors")`
- [x] добавить `path("contributors/", include("apps.contributors.urls"))` в `config/urls.py`
- [x] написать тест: `GET /contributors/` → 200, правильный шаблон
- [x] написать тест: пустая БД → страница отображается без ошибок (пустая таблица)
- [x] написать тест: данные в БД → контекст содержит `donor_table` с правильной структурой
- [x] `uv run pytest` — должно пройти

### Task 5: Шаблон `contributors.html`

**Files:**
- Create: `apps/contributors/templates/contributors/contributors.html`

- [x] создать шаблон на основе `apps/demo/templates/demo/members.html`:
  - `{% extends "demo/base.html" %}`
  - убрать блок `.stats` (карточки со статистикой)
  - убрать блок `.toolbar` (фильтры по школам)
  - убрать `.school`-бейджи: вместо них — просто `{{ member.label }}` текстом в `.role`
  - кнопка "Взнос" в `topbar_action` → `<a href="https://kolco24.ru/donate" target="_blank" ...>`
  - колонки периодов рендерить из `donor_table.periods`; добавлять класс `now` для `current_period_index`
  - ячейки: `paid` / `inactive` / пусто (None) по значению `cell`
  - если `donor_table` пустой — показать заглушку "Нет данных"
- [x] `uv run pytest` — должно пройти (HTTP-тест из Task 4 теперь проверяет реальный шаблон)

### Task 6: ТЗ для kolco24

**Files:**
- Create: `todo_kolco24.md`

- [x] описать эндпоинт: метод GET, URL `/api/contributors/`, формат JSON
- [x] описать поля: `periods`, `members` (с `label` = текущее поле `notes`), `donations`
- [x] указать требования: без аутентификации (или с API-ключом — уточнить), Content-Type application/json
- [x] описать как `label` маппится на `notes` поле модели `ClubMember` на kolco24
- [x] `uv run pytest` — должно пройти

### Task 7: Финальная проверка

- [x] убедиться что все требования из Overview реализованы
- [x] `uv run pytest` — все тесты проходят
- [x] `uv run ruff check .` — нет замечаний
- [x] `uv run ruff format .` — нет изменений
- [x] `uv run python manage.py check` — нет ошибок
- [x] переместить план в `docs/plans/completed/`

## Post-Completion

**Cron на сервере:**
```cron
0 * * * * cd /path/to/project && uv run python manage.py sync_contributors
```

**kolco24.ru:**
- реализовать API-эндпоинт согласно `todo_kolco24.md`
- задать `KOLCO24_API_URL` в `.env` на продакшне

**Ручная проверка:**
- открыть `/contributors/` в браузере после первого `sync_contributors`
- убедиться что кнопка "Взнос" ведёт на `kolco24.ru/donate`
- убедиться что `label` отображается под именем участника без бейджей
