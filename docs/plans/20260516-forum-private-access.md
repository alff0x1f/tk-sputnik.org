# Forum Private Subforum Access Control

## Overview

Подфорум «Орг» (phpBB id=19) был закрыт для гостей — доступен только избранным участникам. Задача — перенести эту логику в Django-архив:
- маркировать приватные подфорумы при импорте (через чтение phpBB ACL)
- ограничить доступ к темам/постам: анонимные → редирект на login, залогиненные без группы → 403
- на главной странице форума показывать иконку замка для закрытых подфорумов

Это сохраняет оригинальную семантику phpBB-форума в read-only архиве без внедрения полноценной ACL-системы.

## Context (from discovery)

- **Модель**: `apps/forum/models.py` — `SubForum` (нужно добавить `is_private` и `allowed_group`)
- **Импорт**: `apps/forum_import/management/commands/import_phpbb_forums.py` — читает `vu2_forums`, нужно добавить чтение `vu2_acl_options`, `vu2_groups`, `vu2_acl_groups`
- **Views**: `apps/forum/views.py` — `subforum_topics`, `topic_posts`, `forum_index`
- **Шаблон**: `apps/forum/templates/forum/forum.html` — цикл по `category.direct_subforums`
- **Тесты**: `apps/forum/tests.py` — классы `SubforumTopicsViewTest`, `TopicPostsViewTest`, `ForumIndexViewTests`
- Существующая миграция: `0001_initial.py` (нужна новая)

## Development Approach

- **Testing approach**: Regular (code first, then tests)
- Завершать каждую задачу полностью перед переходом к следующей
- Тесты обязательны в каждой задаче
- Все тесты должны проходить перед следующей задачей

## Testing Strategy

- **Unit tests**: `apps/forum/tests.py` — модельные тесты и view-тесты
- **Тест-команды**:
  ```bash
  uv run pytest apps/forum/tests.py
  uv run pytest
  ```

## Solution Overview

1. Добавляем `is_private: BooleanField` и `allowed_group: ForeignKey(auth.Group)` в `SubForum`
2. В импорте: читаем phpBB ACL → форум приватный, если у него есть группа с `f_read=allow` и GUESTS не имеет allow; создаём Django-группу по имени форума
3. В views: хелпер `_can_access(request, subforum)` → анонимный → redirect to login, залогинен без группы → 403
4. Шаблон: замок-иконка для приватных подфорумов без доступа

## Technical Details

**phpBB ACL-таблицы:**
- `vu2_acl_options(auth_option_id, auth_option)` — словарь разрешений (`'f_read'`)
- `vu2_groups(group_id, group_name, group_type)` — группы; GUESTS определяется по `group_name='GUESTS'`
- `vu2_acl_groups(forum_id, group_id, auth_option_id, auth_setting)` — ACL; `auth_setting`: 0=NEVER, 1=YES

**Логика определения приватного форума:**
```python
# forum is private if some group has auth_setting=1 (allowed)
# AND guests group does NOT have auth_setting=1
private = any(s == 1 for s in acl[fid].values()) and acl[fid].get(guests_id, -1) != 1
```

**View-хелпер:**
```python
def _can_access(request, subforum):
    if not subforum.is_private:
        return True
    if not request.user.is_authenticated:
        return False
    if request.user.is_staff:
        return True
    if subforum.allowed_group_id is None:
        return False
    return request.user.groups.filter(pk=subforum.allowed_group_id).exists()
```

## Implementation Steps

### Task 1: Добавить поля is_private и allowed_group в SubForum

**Files:**
- Modify: `apps/forum/models.py`
- Create: `apps/forum/migrations/0002_subforum_private.py` (автогенерация)

- [x] добавить `is_private = models.BooleanField("Приватный", default=False)` в `SubForum`
- [x] добавить `allowed_group = models.ForeignKey("auth.Group", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Группа доступа", related_name="private_subforums")` в `SubForum`
- [x] сгенерировать миграцию: `uv run python manage.py makemigrations forum`
- [x] применить миграцию: `uv run python manage.py migrate`
- [x] написать тест: `SubForum` по умолчанию `is_private=False`, `allowed_group=None`
- [x] запустить тесты — должны проходить

### Task 2: Добавить ACL-логику в import_phpbb_forums

**Files:**
- Modify: `apps/forum_import/management/commands/import_phpbb_forums.py`

- [x] добавить функцию `_fetch_private_forum_ids(cursor)` → запрашивает `vu2_acl_options`, `vu2_groups`, `vu2_acl_groups`; возвращает `set[int]` forum_id приватных форумов
- [x] в `handle()` вызвать `_fetch_private_forum_ids` и передавать `is_private` и `allowed_group` в `update_or_create` для `SubForum`
- [x] при создании `allowed_group`: `Group.objects.get_or_create(name=row["forum_name"].lower()[:150])` только для приватных форумов
- [x] добавить в импорт-команду вывод: сколько форумов помечено приватными

> Note: эту задачу нельзя протестировать unit-тестами без MySQL. Тест написать как интеграционный скелет с комментарием TODO или покрыть `_fetch_private_forum_ids` mock-тестом в `apps/forum_import/tests.py`.

- [x] написать unit-тест для `_fetch_private_forum_ids` с mock-курсором, проверяющий логику приватности
- [x] запустить тесты — должны проходить

### Task 3: Добавить контроль доступа в views

**Files:**
- Modify: `apps/forum/views.py`

- [x] добавить хелпер `_can_access(request, subforum) -> bool` согласно дизайну
- [x] в `subforum_topics`: после `get_object_or_404` — проверить `_can_access`; не аутентифицирован → `redirect(f"{settings.LOGIN_URL}?next={request.path}")`; аутентифицирован без доступа → `HttpResponseForbidden()`
- [x] в `topic_posts`: загрузить `topic.subforum` через `select_related("subforum")` и проверить `_can_access`
- [x] в `forum_index`: передавать в контекст `user_group_ids = set(request.user.groups.values_list("id", flat=True)) if request.user.is_authenticated else set()`
- [x] написать тесты в `SubforumTopicsViewTest`:
  - анонимный на приватный subforum → 302 redirect на login
  - залогиненный без группы → 403
  - залогиненный в нужной группе → 200
  - `is_staff` → 200 без группы
- [x] написать тесты в `TopicPostsViewTest` (те же 4 сценария)
- [x] запустить тесты — должны проходить

### Task 4: Показать замок в шаблоне

**Files:**
- Modify: `apps/forum/templates/forum/forum.html`

- [ ] в цикле `{% for subforum in category.direct_subforums %}` добавить проверку `{% if subforum.is_private and subforum.allowed_group_id not in user_group_ids %}` → показать SVG-иконку замка рядом с названием (аналогично существующим SVG в шаблоне)
- [ ] учесть `is_staff`: в `forum_index` передавать `user_is_staff = request.user.is_staff`; у staff замок не показывать
- [ ] написать тест в `ForumIndexViewTests`: контекст содержит `user_group_ids`
- [ ] запустить тесты — должны проходить

### Task 5: Verify acceptance criteria

- [ ] анонимный запрос к приватному subforum → redirect 302 на login URL
- [ ] залогиненный без нужной группы → 403
- [ ] залогиненный в нужной группе → 200
- [ ] staff → 200 независимо от группы
- [ ] публичный subforum по-прежнему отдаёт 200 всем
- [ ] запустить полный suite: `uv run pytest`
- [ ] запустить линтер: `uv run ruff check .`

### Task 6: [Final] Обновить документацию

**Files:**
- Modify: `CLAUDE.md`

- [ ] добавить в раздел **Import status** пункт: `- [x] Private subforum access control (is_private + allowed_group)`
- [ ] переместить план в `docs/plans/completed/`

## Post-Completion

**Ручное тестирование (MySQL):**
- Запустить `docker compose --profile phpbb up -d phpbb_db`, загрузить дамп
- Выполнить `uv run python manage.py import_phpbb_forums`
- Проверить в Django admin: SubForum id=19 должен иметь `is_private=True` и `allowed_group` != None

**Django admin:**
- Добавить пользователя в группу «орг» (или соответствующее имя) вручную через `/admin/auth/group/`
- Убедиться, что у него открывается subforum id=19
