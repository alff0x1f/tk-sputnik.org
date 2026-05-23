# Pagination "entering" state for infinite scroll

## Overview

Баг: при теме с 22 сообщениями (20 на стр.1, 2 на стр.2) пользователь доскролливает до конца, стр.2 загружается через htmx, но в пагинации страница 2 никогда не выделяется. Причина: блок стр.1 (20 постов) всегда пересекает adjusted viewport, поэтому `Math.min(visible)` всегда равен 1.

Решение: ввести промежуточное состояние `entering` — когда блок страницы виден во viewport (снизу), но первый пост ещё не дошёл до верха. `entering` показывает только границу без заливки. Как только первый пост доходит до верха — переходит в `current` (полная заливка, текущее поведение).

## Context (from discovery)

- `apps/forum/static/forum/js/topic.js` — 58 строк, один IntersectionObserver, `setActivePage()`
- `apps/forum/static/forum/css/forum.css` — пагинация строки 222–251, переменные `--accent`, `--line`
- Тесты в `apps/forum/tests.py` покрывают view-уровень (Django), JS не тестируется напрямую
- Шаблоны изменять не нужно

## Design Decisions

1. Добавить второй `IntersectionObserver` (`viewObserver`, rootMargin по умолчанию) → Set `anyVisible`
2. `visible` (первый observer) — страницы, чей блок-top пересёк adjusted viewport → `current`
3. `anyVisible` (второй observer) — страницы, чей блок хоть чуть виден → кандидат на `entering`
4. `updatePagination()` заменяет `setActivePage()`:
   - `currentPage = Math.min(...visible)` если `visible.size > 0`, иначе `lastPage`
   - `isCurrent = page === currentPage`
   - `isEntering = !isCurrent && anyVisible.has(page) && page > currentPage`
5. `observeBlocks()` регистрирует блоки в обоих observer'ах
6. При скролле назад блок уходит из `anyVisible` → `entering` снимается автоматически

## Development Approach

- **testing approach**: Regular (код сначала, тесты следом)
- JS-логика не покрывается pytest — только ручная проверка
- CSS и Django view — без изменений в тестах (поведение view не меняется)
- Завершить каждую задачу перед следующей

## Testing Strategy

- **unit tests**: JS-изменения не тестируются автоматически (нет Playwright/Cypress)
- **manual**: dev-сервер + браузер, сценарии описаны в Post-Completion
- Запустить `uv run pytest` после изменений для регрессионной проверки view-тестов

## Progress Tracking

- `[x]` — выполнено
- `➕` — новая задача
- `⚠️` — блокер

## Implementation Steps

### Task 1: CSS — добавить класс `.entering`

**Files:**
- Modify: `apps/forum/static/forum/css/forum.css`

- [x] добавить после `.pagination .current { ... }`:
  ```css
  .pagination .entering{
    border-color:var(--accent); color:var(--accent);
  }
  ```
- [x] убедиться, что `.entering` и `.current` взаимно исключают видимый эффект (`.current` имеет фон — порядок правил не важен, оба класса не назначаются одновременно)

### Task 2: JS — рефактор `topic.js` с добавлением `viewObserver`

**Files:**
- Modify: `apps/forum/static/forum/js/topic.js`

- [x] добавить `var anyVisible = new Set();`
- [x] создать `viewObserver` (без rootMargin) для отслеживания видимости блоков:
  ```js
  var viewObserver = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      var page = parseInt(entry.target.dataset.page, 10);
      if (entry.isIntersecting) anyVisible.add(page);
      else anyVisible.delete(page);
    });
    updatePagination();
  });
  ```
- [x] заменить callback первого observer: вместо вызова `setActivePage` вызывать `updatePagination()`
- [x] написать `updatePagination()`, которая:
  - вычисляет `currentPage` через `Math.min(...visible)` или `lastPage` если `visible` пуст
  - для каждого `[data-page]` в пагинации: выставляет `.current` и `.entering` через `classList.toggle`
  - обновляет `pag-prev` / `pag-next` (та же логика, что в `setActivePage`)
- [x] удалить `setActivePage()`
- [x] в `observeBlocks()` добавить `viewObserver.observe(block)` рядом с `observer.observe(block)`
- [x] убедиться, что оба observer'а вызывают `updatePagination()`, а не отдельные функции

### Task 3: Регрессионная проверка тестов

**Files:**
- Read: `apps/forum/tests.py`

- [x] запустить `uv run pytest apps/forum/tests.py` — все тесты проходят (view-логика не менялась)
- [x] запустить `uv run pytest` — полный прогон без регрессий

### Task 4: [Final] Завершение

- [x] переместить план в `docs/plans/completed/`

## Post-Completion

**Ручная проверка (dev-сервер):**

1. **Основной сценарий (баг)**: тема с 22 постами
   - доскроллить до конца → должна появиться граница акцентного цвета на цифре 2 в пагинации
   - прокрутить назад на несколько постов → граница исчезает (стр.2 вышла из viewport)
   - снова скроллить вниз → граница появляется снова

2. **Переход в `current`**: тема с 40+ постами
   - скроллить до начала стр.2 → сначала граница, потом заливка при достижении верха
   - убедиться что стр.1 теряет `current` при этом

3. **Одна страница**: не должно быть ни `entering`, ни лишних выделений

4. **Скролл назад**: загрузить стр.2 и стр.3, скроллить обратно наверх — `entering`/`current` меняются корректно
