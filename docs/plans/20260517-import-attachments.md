# Import phpBB Attachments

## Overview

Импорт вложений (attachments) из архива phpBB форума (2007–2014).

Вложения хранятся в MySQL-таблице `vu2_attachments` и в виде файлов в `scratch/forum/files/`.
После импорта файлы раздаются через `MEDIA_ROOT/forum/attachments/`, метаданные — в PostgreSQL.

Inline-вложения (`[attachment=N]`) рендерятся прямо в тексте поста; остальные — списком внизу.

## Context (from discovery)

- **files/components involved:**
  - `apps/forum/models.py` — добавляем `PostAttachment`
  - `apps/forum/migrations/` — новая миграция
  - `apps/forum_import/management/commands/import_phpbb_posts.py` — обновляем `_to_html`
  - `apps/forum_import/management/commands/import_phpbb_attachments.py` — новая команда
  - `CLAUDE.md` — обновить Import status
- **related patterns:**
  - `update_or_create(id=phpbb_id, ...)` — id совпадает с phpbb_id (паттерн Post/Topic)
  - `_to_html(raw, uid)` — BBCode → HTML в `import_phpbb_posts.py`
  - `phpbb_id` unique field — связь с MySQL первичным ключом
  - `ordering = ["phpbb_id"]` — порядок вложений = индексы `[attachment=N]`
- **dependencies:**
  - MySQL `vu2_attachments` + `vu2_posts` (для `bbcode_uid`)
  - `DATABASES['phpbb']` уже настроен
  - `Post.text_bbcode` и `Post.text_html` уже хранятся

## Development Approach

- **testing approach**: Regular (code first, then tests)
- Каждую задачу завершать полностью до перехода к следующей
- Тесты обязательны для каждой задачи
- Все тесты должны проходить перед следующей задачей

## Testing Strategy

- **unit tests**: для `_to_html` (новый attachment regex), для логики второго прохода HTML
- **integration**: импорт-команды тестируются с фикстурами (mock MySQL cursor — паттерн есть в `forum_import/tests.py`)

## Solution Overview

**Статический подход:** вложения финализируются в `text_html` на этапе импорта.

1. `PostAttachment` модель хранит метаданные + указывает на файл в MEDIA_ROOT
2. `_to_html` конвертирует `[attachment=N]filename[/attachment]` → placeholder `<span class="attachment-ref" data-index="N" data-name="filename">`
3. `import_phpbb_attachments` создаёт PostAttachment-записи, затем для каждого затронутого поста перерендеривает `text_html`: заменяет placeholders на реальный HTML, добавляет footer-блок для unreferenced вложений

**Workflow:**
```bash
cp -r scratch/forum/files/ media/forum/attachments/
uv run python manage.py import_phpbb_attachments
```

## Technical Details

**`vu2_attachments` (MySQL):** `attach_id`, `post_msg_id`, `topic_id`, `in_message`, `poster_id`, `is_orphan`, `physical_filename`, `real_filename`, `extension`, `mimetype`, `filesize`, `filetime`, `download_count`, `attach_comment`, `thumbnail`

**Индексирование вложений в phpBB:** для каждого поста вложения нумеруются 0, 1, 2… по возрастанию `attach_id`. Тег `[attachment=N]` ссылается на N-е вложение (0-based) в этом порядке.

**Placeholder format:** `<span class="attachment-ref" data-index="N" data-name="escaped_filename"></span>`

**Inline rendering:**
- изображение (`mimetype` startswith `image/`): `<img src="{url}" alt="{real_filename}">`
- прочее: `<a href="{url}">{real_filename}</a> ({size})`

**Footer rendering (unreferenced):**
```html
<div class="post-attachments">
  <img src="..." alt="...">   <!-- или <a>...) -->
  ...
</div>
```

## Implementation Steps

### Task 1: Add PostAttachment model + migration

**Files:**
- Modify: `apps/forum/models.py`
- Create: `apps/forum/migrations/0004_postattachment.py` (номер уточнить)

- [x] добавить класс `PostAttachment` в `apps/forum/models.py`:
  - поля: `phpbb_id` (IntegerField unique), `post` FK→Post cascade, `physical_filename` (CharField 255), `real_filename` (CharField 255), `mimetype` (CharField 100 blank), `filesize` (IntegerField default 0), `download_count` (IntegerField default 0), `attach_comment` (TextField blank)
  - property `url` → `f"{settings.MEDIA_URL}forum/attachments/{self.physical_filename}"`
  - property `is_image` → `self.mimetype.startswith("image/")`
  - `Meta: ordering = ["phpbb_id"]`, verbose_name рус.
- [x] запустить `uv run python manage.py makemigrations forum` и проверить сгенерированный файл
- [x] запустить `uv run python manage.py migrate` — убедиться, что миграция проходит
- [x] написать тест `test_postattachment_url_property` и `test_postattachment_is_image` в `apps/forum/tests.py`
- [x] запустить `uv run pytest apps/forum/tests.py` — тесты должны проходить

### Task 2: Update _to_html to handle [attachment=N] tags

**Files:**
- Modify: `apps/forum_import/management/commands/import_phpbb_posts.py`


- [x] добавить в начало файла регекс:
  ```python
  _ATTACHMENT_RE = re.compile(
      r'\[attachment=(\d+)\](.*?)\[/attachment\]',
      re.IGNORECASE | re.DOTALL,
  )
  ```
- [x] добавить функцию `_replace_attachment(m)` возвращающую `<span class="attachment-ref" data-index="{index}" data-name="{html.escape(name)}"></span>`
- [x] в `_to_html`, после UID-стрипа (строки с `re.sub(rf"\[...")`), до вызова `_extract_phpbb_markers`, добавить: `text = _ATTACHMENT_RE.sub(_replace_attachment, text)`
- [x] написать тесты в `apps/forum_import/tests.py`:
  - `test_attachment_tag_becomes_placeholder` — `[attachment=0]photo.jpg[/attachment]` → правильный span
  - `test_attachment_tag_with_uid` — `[attachment=0:abc]photo.jpg[/attachment:abc]` → placeholder (uid стрипается раньше, проверить порядок)
  - `test_no_attachment_tag_unchanged` — текст без вложений не меняется
- [x] запустить `uv run pytest apps/forum_import/tests.py` — тесты должны проходить

### Task 3: Create import_phpbb_attachments command

**Files:**
- Create: `apps/forum_import/management/commands/import_phpbb_attachments.py`

- [x] создать команду `import_phpbb_attachments` с `help = "Import attachments from phpBB MySQL database"`
- [x] в `handle()`: выполнить запрос `SELECT attach_id, post_msg_id, physical_filename, real_filename, mimetype, filesize, download_count, attach_comment FROM vu2_attachments WHERE is_orphan = 0 ORDER BY attach_id`
- [x] для каждой строки: `PostAttachment.objects.update_or_create(id=row['attach_id'], defaults={"phpbb_id": row['attach_id'], ...})` — `id` совпадает с `phpbb_id`, как у Post/Topic; пропускать если `Post.objects.filter(phpbb_id=row['post_msg_id'])` не существует (логировать в stderr)
- [x] после создания всех записей — собрать множество `post_ids` затронутых постов
- [x] второй проход: для каждого `post_id` из `post_ids`:
  - достать `post = Post.objects.get(phpbb_id=post_id)`
  - достать `bbcode_uid` из MySQL: `SELECT bbcode_uid FROM vu2_posts WHERE post_id = %s`
  - перерендерить: `html_with_placeholders = _to_html(post.text_bbcode, uid)`
  - достать `attachments = list(post.attachments.order_by('phpbb_id'))`
  - заменить каждый `<span class="attachment-ref" data-index="N">` на inline HTML (img или a+size)
  - собрать unreferenced attachments (те, чей индекс не встретился в тексте), добавить footer `<div class="post-attachments">...</div>`
  - сохранить `post.text_html = final_html; post.save(update_fields=["text_html"])`
- [x] прогресс-репортинг (`{i}/{total}`) и итоговое `Imported N attachments (M skipped)`
- [x] написать тесты (с mock MySQL cursor):
  - `test_import_creates_postattachment` — запись создаётся
  - `test_import_skips_orphans` — orphan-вложения игнорируются
  - `test_import_updates_post_html_inline` — inline placeholder заменяется
  - `test_import_appends_footer_for_unreferenced` — unreferenced → footer блок
- [x] запустить `uv run pytest apps/forum_import/tests.py` — все тесты проходят

### Task 4: Verify and update docs

**Files:**
- Modify: `CLAUDE.md`

- [ ] добавить в CLAUDE.md раздел Import status пункт: `- [x] Attachments (PostAttachment) — done`
- [ ] добавить в CLAUDE.md workflow: `uv run python manage.py import_phpbb_attachments`
- [ ] запустить `uv run pytest` — полный suite проходит
- [ ] запустить `uv run ruff check .` — нет ошибок
- [ ] переместить этот план в `docs/plans/completed/`

## Post-Completion

**Ручная проверка:**
- `cp -r scratch/forum/files/ media/forum/attachments/`
- `uv run python manage.py import_phpbb_attachments`
- Открыть в браузере тему с вложениями, убедиться что img/a рендерятся корректно
- Проверить пост с inline `[attachment=N]` — изображение должно быть на месте тега
- Проверить пост без inline-тегов — вложения в footer-блоке
