# Member page: badge for foreign-sender messages

## Overview

На странице `/challenge/member/<telegram_id>/` сообщения подгружаются двумя путями:
1. по `from_id == athlete.telegram_id` — собственные сообщения атлета
2. по `msg_id__in=workout_msg_ids` — сообщения, к которым привязана тренировка атлета

Второй путь может принести сообщения другого отправителя (например, когда администратор привязал тренировку к чужому сообщению). Сейчас это никак не обозначается, что вводит в заблуждение.

**Решение:** вычислить список имён чужих отправителей (`foreign_senders`) в view и показать в шапке пузыря бейдж «От: Имя» для каждого такого сообщения. Видно всем пользователям.

## Context (from discovery)

- `apps/challenge/views.py:235` — `_group_messages(messages, workouts_by_msg)`, формирует список групп; сюда добавляем поле `foreign_senders`
- `apps/challenge/views.py:271` — `member_detail`, вызывает `_group_messages`; передаём `athlete.telegram_id`
- `apps/challenge/templates/challenge/member.html:31` — шапка `.msg-bubble`; сюда добавляем бейдж
- `apps/challenge/static/challenge/css/challenge.css` — добавляем `.msg-foreign-badge`
- `apps/challenge/tests.py:898` — `MemberDetailViewTests`; расширяем существующий `test_unknown_athlete_shows_messages_via_msg_id` и добавляем новый тест

## Development Approach

- **testing approach**: Regular (code first, then tests)
- complete each task fully before moving to the next
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Solution Overview

`_group_messages` получает новый параметр `athlete_telegram_id`. Для каждой группы собирается список `foreign_senders` — уникальные `from_name` из сообщений группы, где `from_id` непустой и отличается от `athlete_telegram_id`. В шаблоне, если `group.foreign_senders` непустой, перед текстом сообщения показывается бейдж с именами. CSS-класс `.msg-foreign-badge` — маленький, приглушённый стиль.

## Implementation Steps

### Task 1: Добавить `foreign_senders` в `_group_messages` и `member_detail`

**Files:**
- Modify: `apps/challenge/views.py`

- [x] изменить сигнатуру `_group_messages(messages, workouts_by_msg, athlete_telegram_id)` — добавить параметр
- [x] в теле функции, при формировании каждого `group`-словаря, вычислить `foreign_senders`: список уникальных `msg.from_name` из сообщений группы, где `msg.from_id` непустой и `msg.from_id != athlete_telegram_id`
- [x] в `member_detail` передать `athlete.telegram_id` третьим аргументом в `_group_messages`
- [x] написать unit-тесты для `_group_messages` напрямую: группа со своим отправителем → `foreign_senders == []`; группа с чужим → `foreign_senders == ['Имя']`; `from_id` пустой → не считается чужим
- [x] написать HTTP-тест в `MemberDetailViewTests`: athlete `unknown_abc` с workout, привязанным к сообщению от `user9999` (Неизвестный) → страница содержит `msg-foreign-badge` и имя отправителя
- [x] запустить `uv run pytest apps/challenge/tests.py` — все тесты должны пройти

### Task 2: Шаблон и CSS

**Files:**
- Modify: `apps/challenge/templates/challenge/member.html`
- Modify: `apps/challenge/static/challenge/css/challenge.css`

- [x] в `member.html` — внутри `.msg-bubble`, до `{% if group.text %}`, добавить блок: если `group.foreign_senders` непустой — вывести `<div class="msg-foreign-badge">От: {{ group.foreign_senders|join:", " }}</div>`
- [x] в `challenge.css` добавить стиль `.msg-foreign-badge`: маленький шрифт (11–12px), цвет `var(--muted)`, фон `var(--surface-2)`, рамка `1px solid var(--line)`, `border-radius: 4px`, `padding: 2px 8px`, `display: inline-block`, `margin-bottom: 6px`
- [x] убедиться, что бейдж не появляется на сообщениях от самого атлета (регрессия)
- [x] запустить `uv run pytest apps/challenge/tests.py` — все тесты должны пройти

### Task 3: Verify acceptance criteria

- [ ] открыть страницу атлета с чужими сообщениями и убедиться, что бейдж отображается
- [ ] открыть страницу атлета без чужих сообщений — бейджа нет
- [ ] запустить полный тест: `uv run pytest` — все тесты проходят
- [ ] запустить `uv run ruff check .` — нет ошибок

### Task 4: Завершение

**Files:**
- Move: `docs/plans/20260528-member-foreign-sender-badge.md` → `docs/plans/completed/`

- [ ] переместить этот план в `docs/plans/completed/`

## Post-Completion

**Ручная проверка:**
- зайти на страницу `unknown_участник_с_ижевска` (если есть в prod-данных) и убедиться, что бейдж отображается корректно на всех "чужих" сообщениях
