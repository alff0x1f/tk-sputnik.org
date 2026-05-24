# Forum Topic: Post Separators

## Overview

Небольшая визуальная правка страницы треда `/forum/t/<id>/`: сообщения остаются плоским списком, но получают аккуратные горизонтальные разделители между постами. Карточный вариант был отклонён как слишком тяжёлый для текущего интерфейса.

Решаемая проблема: раньше сообщения почти не отделялись друг от друга, а вертикальная линия между аватарками выглядела как таймлайн и не помогала читать форумный тред.

Интеграция: только CSS в `apps/forum`, без изменений шаблонов, моделей, view и JavaScript.

## Context (from discovery)

- **Файл**: `apps/forum/static/forum/css/forum.css`
- **Шаблоны**: `apps/forum/templates/forum/topic.html` и `apps/forum/templates/forum/topic_posts_partial.html` уже используют `.post-card`, `.post-left`, `.post-thread-line`, `.post-right`
- **Текущий layout**: посты рендерятся grid-строкой `44px 1fr`, слева аватар, справа контент
- **Infinite scroll**: partial-страницы добавляются через `.page-block`, поэтому последний пост промежуточной страницы должен сохранять разделитель

## Design Decisions

1. **Не использовать карточки**: убраны рамки, радиусы, фон и тени вокруг каждого поста.
2. **Разделитель на контентной колонке**: линия добавлена на `.post-right`, чтобы она начиналась после аватара и не пересекала левую колонку.
3. **Вертикальную линию скрыть**: `.post-thread-line { display: none; }`, потому что таймлайн-метафора не подходит форумным сообщениям.
4. **Последний пост**: у последнего поста блока разделитель скрывается, но у последнего поста промежуточного `.page-block` возвращается, чтобы infinite scroll не создавал визуальный разрыв между страницами.
5. **Mobile rhythm**: на экранах до `720px` уменьшены верхний и нижний отступы поста.

## Development Approach

- **testing approach**: CSS-only change, без новых unit-тестов
- Правка ограничена existing selectors, чтобы не менять HTML-контракт partial/full rendering
- Регрессионная проверка через Django system check

## Testing Strategy

- **automated**: `uv run python manage.py check`
- **manual**: открыть тред форума и проверить, что посты отделяются горизонтальными линиями, а вертикальная линия между аватарками отсутствует

## Progress Tracking

- `[x]` — выполнено
- `➕` — новая задача
- `⚠️` — блокер

## Implementation Steps

### Task 1: Убрать карточный вариант сообщений

**Files:**
- Modify: `apps/forum/static/forum/css/forum.css`

- [x] удалить карточные свойства `.post-card`: border, border-radius, background, box-shadow
- [x] вернуть плоский layout с grid-колонками аватара и контента
- [x] убрать flex/gap-обёртку `.page-block`, которая была нужна для карточек

### Task 2: Добавить разделители между сообщениями

**Files:**
- Modify: `apps/forum/static/forum/css/forum.css`

- [x] добавить `border-bottom: 1px solid var(--line)` на `.post-right`
- [x] выставить `padding-bottom: 18px` для нормального расстояния до разделителя
- [x] скрывать разделитель у последнего поста последнего блока
- [x] сохранять разделитель у последнего поста промежуточного `.page-block` для infinite scroll

### Task 3: Убрать вертикальную линию между аватарками

**Files:**
- Modify: `apps/forum/static/forum/css/forum.css`

- [x] заменить прежний `.post-thread-line` на `display: none`
- [x] удалить специальные правила, которые показывали линию между page-block при автоподгрузке

### Task 4: Адаптировать мобильные отступы

**Files:**
- Modify: `apps/forum/static/forum/css/forum.css`

- [x] на `max-width: 720px` оставить `36px 1fr`
- [x] выставить `padding-top: 14px`
- [x] выставить `.post-right { padding-bottom: 14px; }`

### Task 5: Проверка

- [x] запустить `uv run python manage.py check` — system check проходит без ошибок

## Post-Completion

**Результат:**
- сообщения отображаются как плоский список с деликатными разделителями
- вертикальная timeline-линия между аватарками не отображается
- HTML-шаблоны не менялись
- Django system check: `System check identified no issues (0 silenced).`
