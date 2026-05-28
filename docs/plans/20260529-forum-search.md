# Полнотекстовый поиск по форуму

## Overview
- Добавить поиск по архиву форума (phpBB, read-only, русский контент) на `/forum/search/`.
- Решает задачу: в архиве 2007–2016 нет способа найти тему/сообщение по словам. Поиск ищет по заголовкам тем и тексту сообщений, отдаёт список найденных **сообщений** (как в phpBB) с подсветкой и ссылкой на конкретный пост.
- Интеграция: новый view + URL в существующем `apps/forum`, строка поиска в общий топбар форума, индекс строится один раз после импорта (архив не меняется) — без триггеров на запись.

## Context (from discovery)
- **Стек:** Django 5.2, Python 3.14+, uv. БД: PostgreSQL и в проде, и в деве (SQLite-фолбэк НЕ нужен). `LANGUAGE_CODE="ru"`.
- **Модели** (`apps/forum/models.py`): `Topic` (поле `title`), `Post` (`text_bbcode`, `text_html`, `bbcode_uid`, `phpbb_id`, `created_at`, FK `topic`, `author`, `author_username`).
- **Вьюхи** (`apps/forum/views.py`):
  - `_can_access(request, subforum)` — контроль доступа к приватным подфорумам (`is_private` + `allowed_group`; staff видит всё).
  - `viewtopic_redirect(request)` — по `?p=<phpbb_id>` считает страницу поста (`POSTS_PER_PAGE=20`) и редиректит на `topic-posts` с якорем `#post-<pk>`. **Переиспользуем для ссылок результатов** — не дублируем вычисление страницы.
  - HTMX-паттерн: `is_htmx = request.headers.get("HX-Request") == "true"` → отдельный partial-шаблон + `patch_vary_headers(response, ["HX-Request"])`.
- **URLs** (`apps/forum/urls.py`): `forum-index`, `subforum-topics`, `topic-posts`, `forum-attachment`, `viewtopic-redirect`.
- **Шаблоны** (`apps/forum/templates/forum/`): все `extends "demo/base.html"`. База даёт блоки `topbar_action` (форум его сейчас обнуляет), `extra_css`, `content`. CSS: `apps/forum/static/forum/css/forum.css`.
- **templatetags:** `apps/forum/templatetags/forum_extras.py` (рендер BBCode).
- **`django.contrib.postgres` НЕТ в `INSTALLED_APPS`** (`config/settings.py`) — нужно добавить (требуется для `SearchVectorField`/`GinIndex`).
- **Тесты:** `pytest` (`uv run pytest`), `DJANGO_SETTINGS_MODULE` задан в `pyproject.toml`. Файл `apps/forum/tests.py`, `django.test.TestCase`, `self.client`. Тесты идут на PostgreSQL → FTS проверяется реально.

## Development Approach
- **testing approach**: Regular (код, затем тесты) — соответствует стилю репозитория (тесты рядом в `tests.py`).
- Каждую задачу доводить до конца перед переходом к следующей; небольшие сфокусированные изменения.
- **Каждая задача включает новые/обновлённые тесты** — это обязательная часть чеклиста, а не опция.
- **Все тесты должны проходить перед началом следующей задачи.**
- Запускать тесты после каждого изменения. Сохранять обратную совместимость.
- Линт/формат: `uv run ruff check .` и `uv run ruff format .`.

## Testing Strategy
- **unit-тесты**: обязательны в каждой задаче (см. Development Approach).
- **e2e**: в проекте нет браузерных e2e (Playwright/Cypress) — проверяем через `self.client` (HTTP-уровень). UI-логику (HTMX-партиал, экранирование сниппета) покрываем клиентскими тестами в той же задаче.
- Команда тестов: `uv run pytest apps/forum/tests.py` (отдельно), `uv run pytest` (полный прогон).

## Progress Tracking
- Отмечать выполненные пункты `[x]` сразу по завершении.
- Новые задачи — с префиксом ➕, блокеры — с префиксом ⚠️.
- Обновлять план, если реализация отклоняется от исходной задумки.

## Solution Overview
- **Движок:** PostgreSQL full-text search, конфиг `'russian'` (стемминг русских словоформ). Внешние движки и `pg_trgm` отклонены при brainstorm.
- **Индекс:** денормализованное поле `Post.search_text` (чистый плейнтекст) как источник для вектора и сниппетов; `Post.search_vector` (`SearchVectorField`) под GIN-индексом. Вес `B` — текст сообщения; вес `A` — заголовок темы, добавляется **только в первый пост темы** (первый по `created_at, id`). Значит матч по названию даёт одну строку (первый пост темы) и стоит выше body-матчей.
- **Запрос:** `SearchQuery(q, config="russian", search_type="websearch")` — устойчив к любому пользовательскому вводу, понимает кавычки/`OR`/`-слово`. Ранжирование `SearchRank`, сниппеты `SearchHeadline`.
- **Доступ:** фильтрация на уровне queryset через `topic__subforum` (та же логика, что в `_can_access`) — приватные разделы не утекают в выдачу.
- **UI:** строка поиска в топбаре всех страниц форума (инклуд), страница выдачи `forum/search.html` + HTMX-партиал для пагинации, в стиле существующего `subforum_topics`.

## Technical Details
- **Веса:** `SearchVector(..., weight="A")` (заголовок) и `weight="B"` (текст). `SearchRank` по умолчанию учитывает веса (A=1.0, B=0.4).
- **Снятие разметки для `search_text`:** убрать BBCode и HTML-теги из `text_bbcode`/`text_html` → плейнтекст. phpBB хранит BBCode с `bbcode_uid` (теги вида `[b:uid]`), и `text_html` уже отрендерен — берём `text_html` и снимаем теги (`django.utils.html.strip_tags` + `html.unescape`), это надёжнее, чем парсить BBCode.
- **Безопасность сниппета:** `SearchHeadline` НЕ экранирует исходный текст, а рендерить надо как HTML ради `<mark>`. Решение: задать нестандартные сентинел-маркеры (`start_sel`/`stop_sel`, напр. `"@@HLS@@"` / `"@@HLE@@"`), а в кастомном шаблонном фильтре сначала `escape()` всего сниппета, потом заменить экранированные сентинелы на `<mark>…</mark>` и вернуть `mark_safe`. Любой `<`, `>`, `&` из контента экранируется → защита от XSS.
- **Пагинация:** `Paginator(qs, 20)`, `get_page(request.GET.get("page"))`, в `hx-get` тащим и `q`, и `page`.
- **Пустой `q`:** ранний возврат страницы-подсказки без обращения к БД.

## What Goes Where
- **Implementation Steps** (`[ ]`): изменения в этом репозитории — settings, модель, миграция, функция индексации, команда, view, URL, фильтр, шаблоны, CSS, тесты, обновление CLAUDE.md.
- **Post-Completion** (без чекбоксов): однократный запуск индексации на проде/реальных данных и ручная визуальная проверка выдачи.

## Implementation Steps

### Task 1: Поля поиска в модели Post + регистрация contrib.postgres + миграция

**Files:**
- Modify: `config/settings.py`
- Modify: `apps/forum/models.py`
- Create: `apps/forum/migrations/000X_post_search.py` (через makemigrations)

- [ ] добавить `"django.contrib.postgres"` в `INSTALLED_APPS` (`config/settings.py`)
- [ ] в `Post` добавить `search_text = models.TextField("Текст для поиска", blank=True, default="")`
- [ ] в `Post` добавить `search_vector = SearchVectorField(null=True, editable=False)` (импорт из `django.contrib.postgres.search`)
- [ ] в `Post.Meta.indexes` добавить `GinIndex(fields=["search_vector"])` (импорт из `django.contrib.postgres.indexes`)
- [ ] `uv run python manage.py makemigrations forum` → проверить сгенерированную миграцию (поля + GIN-индекс)
- [ ] `uv run python manage.py migrate` — применяется без ошибок
- [ ] написать тест: после миграции у `Post` есть поля `search_text`/`search_vector`, объект создаётся и сохраняется
- [ ] `uv run pytest apps/forum/tests.py` — должно пройти перед Task 2

### Task 2: Функция rebuild_search_index + management-команда

**Files:**
- Create: `apps/forum/search.py` (функция `rebuild_search_index`)
- Create: `apps/forum/management/__init__.py` (если нет)
- Create: `apps/forum/management/commands/__init__.py` (если нет)
- Create: `apps/forum/management/commands/build_forum_search_index.py`
- Modify: `apps/forum/tests.py`

- [ ] создать `apps/forum/search.py` с `rebuild_search_index(queryset=None)`:
  - [ ] для постов в `queryset` (по умолчанию все) снять разметку с `text_html` (`strip_tags` + `html.unescape`) → записать в `search_text` пачками через `bulk_update` (батчи, `iterator()`)
  - [ ] определить первый пост каждой темы (по `created_at, id`) — множество их id
  - [ ] обновить `search_vector`: для обычных постов `SearchVector("search_text", weight="B", config="russian")`; для первого поста темы дополнительно `|| SearchVector(Value(topic.title), weight="A", config="russian")`
- [ ] создать команду `build_forum_search_index` — тонкая обёртка: вызывает `rebuild_search_index()` и печатает число обновлённых постов
- [ ] написать тест: после `rebuild_search_index()` `search_text` очищен от BBCode/HTML-тегов
- [ ] написать тест: `search_vector` заполнен; первый пост темы получает вес заголовка (заголовочное слово находится по первому посту), последующие посты — нет
- [ ] написать тест (edge): пустой/без текста пост не падает
- [ ] `uv run pytest apps/forum/tests.py` — должно пройти перед Task 3

### Task 3: Шаблонный фильтр подсветки сниппета (XSS-safe)

**Files:**
- Modify: `apps/forum/templatetags/forum_extras.py`
- Modify: `apps/forum/tests.py`

- [ ] добавить фильтр `highlight_snippet` (или подобный) в `forum_extras.py`: на вход строка от `SearchHeadline` с сентинелами `@@HLS@@`/`@@HLE@@`
  - [ ] `escape()` всю строку
  - [ ] заменить экранированные сентинелы на `<mark>`/`</mark>`
  - [ ] вернуть `mark_safe(...)`
- [ ] определить константы сентинелов в одном месте (переиспользуются и во view, и в фильтре) — например в `apps/forum/search.py` или рядом
- [ ] написать тест: обычный текст с сентинелами → `<mark>` вокруг совпадения
- [ ] написать тест (XSS): текст с `<script>` и сентинелами → `&lt;script&gt;` в выводе, сырого тега нет, `<mark>` на месте
- [ ] `uv run pytest apps/forum/tests.py` — должно пройти перед Task 4

### Task 4: View поиска + контроль доступа + URL + шаблоны + строка поиска + CSS

**Files:**
- Modify: `apps/forum/views.py`
- Modify: `apps/forum/urls.py`
- Create: `apps/forum/templates/forum/search.html`
- Create: `apps/forum/templates/forum/search_results_partial.html`
- Create: `apps/forum/templates/forum/_search_box.html`
- Modify: `apps/forum/templates/forum/forum.html`
- Modify: `apps/forum/templates/forum/subforum.html`
- Modify: `apps/forum/templates/forum/topic.html`
- Modify: `apps/forum/static/forum/css/forum.css`
- Modify: `apps/forum/tests.py`

- [ ] добавить хелпер `_accessible_posts(request)` в `views.py`: queryset `Post` с фильтром по `topic__subforum` — аноним → `is_private=False`; staff → без фильтра; обычный юзер → `Q(is_private=False) | Q(allowed_group__in=группы юзера)` (через `topic__subforum__...`)
- [ ] добавить view `forum_search(request)`:
  - [ ] прочитать `q = request.GET.get("q", "").strip()`; пустой `q` → ранний `render` страницы-подсказки без запроса к БД
  - [ ] `query = SearchQuery(q, config="russian", search_type="websearch")`
  - [ ] queryset: `_accessible_posts(request).select_related("topic", "topic__subforum", "author").annotate(rank=SearchRank(F("search_vector"), query), snippet=SearchHeadline("search_text", query, config="russian", start_sel=<сентинел>, stop_sel=<сентинел>)).filter(search_vector=query).order_by("-rank", "-created_at")`
  - [ ] `Paginator(qs, 20)`, `get_page`, эледированные страницы — как в `subforum_topics`
  - [ ] HTMX: `is_htmx` → `search_results_partial.html`, иначе `search.html`; `patch_vary_headers(response, ["HX-Request"])`
- [ ] добавить URL `path("search/", views.forum_search, name="forum-search")` в `apps/forum/urls.py`
- [ ] создать `_search_box.html` (`<form method="get" action="{% url 'forum-search' %}">` с `<input name="q" value="{{ q|default:'' }}">`)
- [ ] подключить `_search_box.html` в блок `topbar_action` в `forum.html`, `subforum.html`, `topic.html`
- [ ] создать `search.html` (extends `demo/base.html`): крошки «Форум / Поиск», строка поиска (предзаполненная), счётчик найденного, состояния пустого `q` и нуля результатов («Ничего не найдено»), `{% include "forum/search_results_partial.html" %}`
- [ ] создать `search_results_partial.html`: список результатов (заголовок темы — ссылка на `{% url 'viewtopic-redirect' %}?p={{ post.phpbb_id }}`; мелким — подфорум · автор · дата; сниппет через фильтр `highlight_snippet`) + HTMX-подгрузка следующей страницы (тащит `q` и `page`)
- [ ] добавить классы в `forum.css` под строку поиска и строки результатов (в духе существующих токенов, без новых зависимостей)
- [ ] написать тест: морфология — запрос «поход» находит пост с «походы»
- [ ] написать тест: ранжирование — title-матч (первый пост темы) выше body-матча
- [ ] написать тест доступа: аноним не видит результаты из приватного подфорума
- [ ] написать тест доступа: юзер из `allowed_group` видит приватное; юзер не из группы — нет; staff видит всё
- [ ] написать тест: ссылка результата ведёт на `viewtopic-redirect?p=<phpbb_id>`
- [ ] написать тест: сниппет в отрендеренной странице содержит `<mark>`; пост с `<script>` экранирован (XSS)
- [ ] написать тест (edge): пустой `q` → 200 + подсказка, без падения; ноль результатов → «Ничего не найдено»
- [ ] написать тест HTMX: `HX-Request: true` → партиал `search_results_partial.html`; обычный запрос → `search.html`
- [ ] `uv run ruff check . && uv run ruff format .`
- [ ] `uv run pytest apps/forum/tests.py` — должно пройти перед Task 5

### Task 5: Обновить воркфлоу импорта в CLAUDE.md
**Files:**
- Modify: `CLAUDE.md`

- [ ] дописать шаг `uv run python manage.py build_forum_search_index` в блок «Import workflow» (после импорта постов/вложений)
- [ ] добавить отметку в «Import status» про поиск (search index)
- [ ] тесты не требуются (только документация)

### Task 6: Verify acceptance criteria
- [ ] проверить, что реализованы все пункты Overview (поиск по темам+сообщениям, список сообщений, подсветка, ссылка на пост)
- [ ] проверить edge-кейсы (пустой запрос, ноль результатов, XSS, доступ к приватному)
- [ ] полный прогон: `uv run pytest`
- [ ] линт: `uv run ruff check .`
- [ ] браузерных e2e в проекте нет — пропускаем

### Task 7: [Final] Документация и закрытие плана
- [ ] обновить README.md при необходимости
- [ ] обновить CLAUDE.md, если по ходу появились новые паттерны
- [ ] переместить план в `docs/plans/completed/`

## Post-Completion
*Требуют ручного вмешательства / внешних систем — без чекбоксов, информационно.*

**Однократный запуск на реальных данных:**
- после деплоя выполнить `uv run python manage.py build_forum_search_index` на проде (PostgreSQL), чтобы заполнить `search_text`/`search_vector` для всего архива. Команда идемпотентна — можно перезапускать.

**Ручная проверка:**
- визуально проверить выдачу на проде: подсветка `<mark>`, корректность ссылок на конкретный пост (`#post-<pk>` и номер страницы), отсутствие приватного контента в выдаче для анонима.
- проверить производительность поиска на полном объёме архива (GIN-индекс должен использоваться — при сомнениях `EXPLAIN ANALYZE`).
