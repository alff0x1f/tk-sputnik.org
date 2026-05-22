# Forum Topic: Infinite Scroll with Sticky Pagination

## Overview

Переработка страницы треда `/forum/t/<id>/`: пагинация переезжает наверх и прилипает при скролле, посты подгружаются автоматически через htmx когда пользователь доскролливает до конца текущей страницы. Активная страница в пагинации обновляется динамически через Intersection Observer.

Решаемая проблема: пагинация снизу неудобна для длинных тредов — нужно доскролить до конца, чтобы перейти на следующую страницу. Бесконечный скролл с верхней sticky-пагинацией решает это без потери классической навигации по страницам.

Интеграция: только `apps/forum`, никаких изменений в моделях или URL.

## Context (from discovery)

- **Файлы**: `apps/forum/views.py` (view), `apps/forum/templates/forum/topic.html` (шаблон), `apps/forum/static/forum/css/forum.css` (стили, пагинация на строках 222–240), `apps/demo/templates/demo/base.html` (базовый шаблон, нет `{% block extra_js %}`)
- **Паттерн пагинации**: Django `Paginator`, `?page=N`, 20 постов на страницу
- **Topbar**: `position: sticky; top: 0; height: 60px` — отсюда `top: 60px` для sticky-пагинации
- **htmx**: не используется в проекте, подключается через CDN в одном шаблоне
- **Тесты**: `uv run pytest`, Django `TestCase`, файл `apps/forum/tests.py`

## Design Decisions

1. **Backend**: `topic_posts()` определяет htmx-запрос по заголовку `HX-Request: true`. Отдаёт `topic_posts_partial.html` для htmx, `topic.html` для обычных запросов.
2. **Пагинация**: перемещается наверх, `id="pagination"`, `position: sticky; top: 60px`. Все номера страниц — `<a data-page="N">` (не `<span>`), чтобы JS мог переключать класс `current` без замены узлов.
3. **Сентинель**: `<div class="sentinel" hx-get="?page=N" hx-trigger="intersect once" hx-swap="outerHTML">` в конце каждого блока постов. При входе в viewport htmx заменяет сентинель на новый `page-block` + следующий сентинель.
4. **Трекинг страницы**: Intersection Observer в `topic.js` следит за `.page-block[data-page]`. Текущая страница = `Math.min(...visible)` — наименьший номер среди видимых блоков.
5. **URL**: не меняется при автоподгрузке. Меняется только при клике на пагинацию (полный переход + дальнейший infinite scroll со следующей страницы).

## Development Approach

- **testing approach**: Regular (код сначала, тесты следом в той же задаче)
- Каждую задачу завершаем полностью перед следующей
- Тесты — обязательная часть каждой задачи
- Все тесты должны проходить перед началом следующей задачи

## Testing Strategy

- **unit tests**: `apps/forum/tests.py` — проверяем view на partial/full ответ, наличие нужных элементов в шаблоне
- **manual**: запустить dev-сервер, проверить скролл в браузере

## Progress Tracking

- `[x]` — выполнено
- `➕` — новая задача, обнаруженная в процессе
- `⚠️` — блокер

## Implementation Steps

### Task 1: Добавить `{% block extra_js %}` в базовый шаблон

**Files:**
- Modify: `apps/demo/templates/demo/base.html`

- [x] добавить `{% block extra_js %}{% endblock %}` перед `</body>` в `base.html`
- [x] убедиться, что блок не ломает существующие страницы (рендер без изменений)

### Task 2: Доработать view для поддержки partial-ответа

**Files:**
- Modify: `apps/forum/views.py`
- Modify: `apps/forum/tests.py`

- [x] в `topic_posts()` добавить проверку `request.headers.get("HX-Request") == "true"`
- [x] при `is_htmx=True` рендерить `forum/topic_posts_partial.html`, иначе — `forum/topic.html`
- [x] написать тест: обычный GET `/forum/t/<pk>/` возвращает полный шаблон `topic.html`
- [x] написать тест: GET с заголовком `HTTP_HX_REQUEST=true` возвращает partial-шаблон
- [x] написать тест: partial-ответ содержит `.page-block`, не содержит `<html>`
- [x] написать тест: partial с последней страницей не содержит `.sentinel`
- [x] `uv run pytest apps/forum/tests.py` — все тесты проходят

### Task 3: Создать `topic_posts_partial.html`

**Files:**
- Create: `apps/forum/templates/forum/topic_posts_partial.html`

- [ ] создать шаблон без `extends` — только фрагмент HTML
- [ ] обернуть посты в `<div class="page-block" data-page="{{ page_obj.number }}">`
- [ ] скопировать разметку `.post-card` из `topic.html` без изменений
- [ ] добавить сентинель в конце если `page_obj.has_next`: `<div class="sentinel" hx-get="?page={{ page_obj.next_page_number }}" hx-trigger="intersect once" hx-swap="outerHTML"></div>`
- [ ] `uv run pytest apps/forum/tests.py` — тесты из Task 2 проходят с новым шаблоном

### Task 4: Переписать `topic.html`

**Files:**
- Modify: `apps/forum/templates/forum/topic.html`

- [ ] убрать пагинацию снизу
- [ ] добавить пагинацию сверху (после `.feed-sub`, до `.post-feed`) с `id="pagination"` и классом `pagination-sticky`
- [ ] все номера страниц — `<a href="?page={{ num }}" data-page="{{ num }}" {% if num == page_obj.number %}class="current"{% endif %}>{{ num }}</a>` (не `<span>`)
- [ ] обернуть посты в `<div class="page-block" data-page="{{ page_obj.number }}">`
- [ ] добавить сентинель после блока постов если `page_obj.has_next`
- [ ] в `{% block extra_js %}` подключить htmx CDN и `{% static 'forum/js/topic.js' %}`
- [ ] `uv run pytest apps/forum/tests.py` — все тесты проходят

### Task 5: CSS — sticky-пагинация и сентинель

**Files:**
- Modify: `apps/forum/static/forum/css/forum.css`

- [ ] добавить `.pagination-sticky`: `position: sticky; top: 60px; z-index: 10; background: var(--bg); border-bottom: 1px solid var(--line); margin: 0 0 20px; padding: 8px 0;`
- [ ] добавить `.sentinel`: `height: 1px;`
- [ ] убедиться, что `.pagination` базовые стили не конфликтуют с `.pagination-sticky` (margin-top переопределяется)

### Task 6: JavaScript — Intersection Observer для трекинга страницы

**Files:**
- Create: `apps/forum/static/forum/js/topic.js`

- [ ] создать `topic.js` с IIFE
- [ ] если нет `#pagination` — выходим (защита для других страниц)
- [ ] создать `IntersectionObserver` с `rootMargin: '-60px 0px 0px 0px'`
- [ ] вести `Set visible` — добавлять/удалять `data-page` при пересечении
- [ ] `setActivePage(Math.min(...visible))` — переключает класс `current` на `[data-page]`
- [ ] `observeBlocks()` — подписывает все `.page-block[data-page]` на observer
- [ ] `document.body.addEventListener('htmx:afterSwap', observeBlocks)` — переподписка после htmx-загрузки
- [ ] убедиться что `observeBlocks()` не дублирует подписки при повторном вызове (использовать WeakSet или проверять `data-observed`)

### Task 7: Проверка требований

- [ ] запустить `uv run pytest` — полный прогон
- [ ] запустить dev-сервер, открыть тред с >1 страницей
- [ ] проверить: пагинация отображается сверху и прилипает при скролле
- [ ] проверить: при скролле к концу страницы подгружается следующая
- [ ] проверить: активный номер в пагинации обновляется при скролле
- [ ] проверить: клик на страницу 2 → полный переход, далее автоподгрузка страницы 3
- [ ] проверить: последняя страница не создаёт сентинель (загрузка останавливается)
- [ ] проверить на мобильном экране (≤720px)

### Task 8: [Final] Завершение

- [ ] переместить план в `docs/plans/completed/`

## Post-Completion

**Ручная проверка:**
- тред с 1 страницей (пагинация не должна отображаться) — поведение не изменилось
- тред с частным подфорумом — доступ всё ещё работает корректно
- проверить Network tab в DevTools: partial-запросы идут с заголовком `HX-Request: true`, ответ — только HTML-фрагмент без `<html>`
