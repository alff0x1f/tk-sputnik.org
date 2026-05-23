# Subforum Topics: Infinite Scroll with Sticky Pagination

## Overview

Переработка страницы списка тем `/forum/f/<id>/`: пагинация переезжает наверх и прилипает при скролле, темы подгружаются автоматически через htmx когда пользователь доскролливает до конца текущей страницы. Активная страница в пагинации обновляется динамически через Intersection Observer.

Паттерн идентичен реализации для постов треда (`20260523-forum-infinite-scroll.md`).

Интеграция: только `apps/forum`, никаких изменений в моделях или URL.

## Context (from discovery)

- **Файлы**: `apps/forum/views.py` (subforum_topics(), строки 57–75), `apps/forum/templates/forum/subforum.html` (шаблон), `apps/forum/static/forum/js/topic.js` (переименовать), `apps/forum/static/forum/css/forum.css` (`.pagination-sticky` и `.sentinel` уже есть)
- **Паттерн пагинации**: Django `Paginator`, `?page=N`, 25 тем на страницу
- **Ссылочная реализация**: `topic_posts()` view + `topic.html` + `topic_posts_partial.html` + `topic.js`
- **htmx**: уже подключён через `forum-scroll.js` (после переименования)
- **Тесты**: `uv run pytest`, Django `TestCase`, файл `apps/forum/tests.py`

## Design Decisions

1. **JS**: `topic.js` → `forum-scroll.js` — generic файл, подключается на обеих страницах
2. **Backend**: `subforum_topics()` определяет htmx-запрос по заголовку `HX-Request: true`. Отдаёт `subforum_topics_partial.html` для htmx, `subforum.html` для обычных запросов. Добавить `elided_pages` в контекст, `patch_vary_headers`.
3. **Пагинация**: перемещается наверх, `id="pagination"`, `position: sticky; top: 60px`. Все номера страниц — `<a data-page="N">`, эллипсис через `elided_pages`.
4. **Сентинель**: `<div class="sentinel" hx-get="?page=N" hx-trigger="intersect once" hx-swap="outerHTML">` в конце каждого блока тем.
5. **CSS**: изменений нет — `.pagination-sticky` и `.sentinel` уже определены.

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

### Task 1: Переименовать topic.js → forum-scroll.js, обновить topic.html

**Files:**
- Rename: `apps/forum/static/forum/js/topic.js` → `apps/forum/static/forum/js/forum-scroll.js`
- Modify: `apps/forum/templates/forum/topic.html`

- [x] переименовать `topic.js` в `forum-scroll.js`
- [x] обновить `topic.html`: заменить `{% static 'forum/js/topic.js' %}` на `{% static 'forum/js/forum-scroll.js' %}`
- [x] `uv run pytest apps/forum/tests.py` — все тесты проходят

### Task 2: Доработать view subforum_topics()

**Files:**
- Modify: `apps/forum/views.py`

- [x] добавить `is_htmx = request.headers.get("HX-Request") == "true"`
- [x] при `is_htmx=True` рендерить `forum/subforum_topics_partial.html`, иначе — `forum/subforum.html`
- [x] добавить `elided_pages` в контекст (только для не-htmx, как в `topic_posts`)
- [x] добавить `patch_vary_headers(response, ["HX-Request"])`
- [x] написать тест: обычный GET `/forum/f/<pk>/` возвращает полный шаблон `subforum.html`
- [x] написать тест: GET с заголовком `HTTP_HX_REQUEST=true` возвращает partial-шаблон
- [x] написать тест: partial-ответ содержит `.page-block`, не содержит `<html>`
- [x] написать тест: partial с последней страницей не содержит `.sentinel`
- [x] `uv run pytest apps/forum/tests.py` — все тесты проходят

### Task 3: Создать subforum_topics_partial.html

**Files:**
- Create: `apps/forum/templates/forum/subforum_topics_partial.html`

- [x] создать шаблон без `extends` — только фрагмент HTML
- [x] обернуть темы в `<div class="page-block" data-page="{{ page_obj.number }}">`
- [x] скопировать разметку `.topic` из `subforum.html` без изменений
- [x] добавить сентинель в конце если `page_obj.has_next`: `<div class="sentinel" hx-get="?page={{ page_obj.next_page_number }}" hx-trigger="intersect once" hx-swap="outerHTML"></div>`
- [x] `uv run pytest apps/forum/tests.py` — тесты из Task 2 проходят с новым шаблоном

### Task 4: Переписать subforum.html

**Files:**
- Modify: `apps/forum/templates/forum/subforum.html`

- [ ] убрать пагинацию снизу
- [ ] добавить пагинацию сверху (перед `.forum-cat`) с `id="pagination"`, классом `pagination-sticky`, `data-pages="{{ page_obj.paginator.num_pages }}"`
- [ ] все номера страниц — `<a href="?page={{ item.num }}" data-page="{{ item.num }}" ...>` (не `<span>`), эллипсис через `item.is_ellipsis`
- [ ] добавить стрелки `id="pag-prev"` / `id="pag-next"` как в `topic.html`
- [ ] показывать пагинацию только если `page_obj.paginator.num_pages > 1`
- [ ] обернуть темы в `<div class="page-block" data-page="{{ page_obj.number }}">`
- [ ] добавить сентинель после блока тем если `page_obj.has_next`
- [ ] в `{% block extra_js %}` подключить `{% static 'forum/js/htmx.min.js' %}` и `{% static 'forum/js/forum-scroll.js' %}`
- [ ] `uv run pytest apps/forum/tests.py` — все тесты проходят

### Task 5: Проверка требований

- [ ] запустить `uv run pytest` — полный прогон
- [ ] запустить dev-сервер, открыть подфорум с >1 страницей (manual test)
- [ ] проверить: пагинация отображается сверху и прилипает при скролле (manual test)
- [ ] проверить: при скролле к концу страницы подгружается следующая (manual test)
- [ ] проверить: активный номер в пагинации обновляется при скролле (manual test)
- [ ] проверить: последняя страница не создаёт сентинель (manual test)

### Task 6: [Final] Завершение

- [ ] переместить план в `docs/plans/completed/`

## Post-Completion

**Ручная проверка:**
- подфорум с 1 страницей (пагинация не должна отображаться)
- проверить Network tab в DevTools: partial-запросы идут с заголовком `HX-Request: true`, ответ — только HTML-фрагмент без `<html>`
- страница треда всё ещё работает (forum-scroll.js подключён через переименование)
