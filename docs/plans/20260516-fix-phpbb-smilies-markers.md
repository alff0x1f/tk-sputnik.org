# Fix phpBB Smilies and Raw-HTML Markers Rendering

## Overview

phpBB stores three kinds of raw-HTML constructs inside `post_text` alongside BBCode:

1. **Smileys**: `<!-- s:) --><img src="{SMILIES_PATH}/smile.gif" alt=":)" title="Smile" /><!-- s:) -->`
2. **URL markers**: `<!-- m --><a class="postlink" href="URL">text</a><!-- m -->`
3. **Email markers**: `<!-- e --><a href="mailto:X">X</a><!-- e -->`

The `bbcode` library treats these as plain text and HTML-escapes them, so they end up in `Post.text_html` as escaped strings (e.g., `&lt;img src=&quot;{SMILIES_PATH}/smile.gif&quot;...&gt;`) and display as literal text in the browser instead of rendered images/links.

Fix: extract these markers **before** BBCode parsing using placeholders, then restore them with correct URLs after parsing. Re-run `import_phpbb_posts` to regenerate all `text_html` values.

## Context (from discovery)

- Main file: `apps/forum_import/management/commands/import_phpbb_posts.py` — `_to_html()` function
- Tests: `apps/forum_import/tests.py` — class `ImportPhpbbPostsCommandTest`, tests call command via mock cursor
- Smiley files: `scratch/forum/images/smilies/` (61 `.gif` files)
- Media destination: `media/forum/smilies/` (analogous to `media/forum/avatars/`)
- Template renders `post.text_html` with `|safe`: `apps/forum/templates/forum/topic.html:53`
- Smileys served via `MEDIA_URL` (set in `config/settings.py`, already used for avatars)

## Development Approach

- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- Make small, focused changes
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**
- Run tests: `uv run pytest apps/forum_import/tests.py -v`

## Testing Strategy

- **Unit tests** for `_to_html()` imported directly:
  `from apps.forum_import.management.commands.import_phpbb_posts import _to_html`
- Tests added to `apps/forum_import/tests.py` as a new class `ToHtmlSmiliesMarkersTest`
- Cover: smiley rendering, URL marker rendering, email marker rendering, combined cases, no regression on existing BBCode

## Progress Tracking

- mark completed items with `[x]` immediately when done
- add newly discovered tasks with ➕ prefix
- document issues/blockers with ⚠️ prefix

## Solution Overview

Use a placeholder-based pre/post-processing approach around the BBCode parser:

1. Before `_parser.format()`: regex-extract all phpBB raw-HTML markers, replace with null-byte placeholders (`\x00SMILEY0\x00`, `\x00PHPLINK0\x00`) that the bbcode parser passes through unescaped.
2. After `_parser.format()`: replace placeholders with correct HTML.
3. Smiley img URLs → `/media/forum/smilies/<filename>`; remove `{SMILIES_PATH}`.
4. URL/email link wrappers → keep inner `<a>` but add `rel="nofollow"`.

## Technical Details

**Regex patterns to add at module level:**

```python
_SMILEY_RE = re.compile(
    r'<!-- s[^>]* -->'
    r'<img\s+src="\{SMILIES_PATH\}/([^"]+)"[^>]*/>'
    r'<!-- s[^>]* -->'
)
_URL_MARKER_RE = re.compile(r'<!-- m -->(.*?)<!-- m -->', re.DOTALL)
_EMAIL_MARKER_RE = re.compile(r'<!-- e -->(.*?)<!-- e -->', re.DOTALL)
```

**Placeholder strategy:**
- Use `\x00` (null byte) as delimiter — it is not HTML-escaped by the bbcode library.
- Keys: `\x00P0\x00`, `\x00P1\x00`, ... (shared counter across all three types).

**Smiley replacement:**
- `{SMILIES_PATH}` → `/media/forum/smilies`
- Strip `<!-- s:X -->` wrappers.
- Preserve `alt` attribute from the original tag.

**URL/email replacement:**
- Strip `<!-- m -->`/`<!-- e -->` wrappers.
- Add `rel="nofollow"` to the inner `<a>` tag.

## What Goes Where

**Implementation Steps** — code changes in this repo.

**Post-Completion** — manual steps after implementation:
- Copy smilies to media (one-time): `mkdir -p media/forum/smilies && cp scratch/forum/images/smilies/* media/forum/smilies/`
- Re-run post import: `uv run python manage.py import_phpbb_posts`
- Verify smiley images display in browser on a post that uses smileys (e.g. phpbb_id=122150).

---

## Implementation Steps

### Task 1: Fix `_to_html()` to handle phpBB raw-HTML markers

**Files:**
- Modify: `apps/forum_import/management/commands/import_phpbb_posts.py`

- [ ] Add `_SMILEY_RE`, `_URL_MARKER_RE`, `_EMAIL_MARKER_RE` regex constants at module level
- [ ] Add `_extract_phpbb_markers(text)` helper that:
  - iterates over all three patterns with a shared counter
  - builds a `{placeholder: html_replacement}` dict
  - returns `(modified_text, replacements_dict)`
  - for smileys: replacement is `<img src="/media/forum/smilies/<file>" alt="<alt>">`
  - for URL/email markers: replacement is inner `<a>` with `rel="nofollow"` injected
- [ ] Modify `_to_html()` to call `_extract_phpbb_markers()` before `_parser.format()` and restore placeholders after
- [ ] Run `uv run pytest apps/forum_import/tests.py -v` — existing tests must still pass

### Task 2: Add unit tests for phpBB marker handling

**Files:**
- Modify: `apps/forum_import/tests.py`

- [ ] Add class `ToHtmlSmiliesMarkersTest(TestCase)` with direct imports of `_to_html`
- [ ] Test: smiley `<!-- s:) --><img src="{SMILIES_PATH}/smile.gif" alt=":)" title="Smile" /><!-- s:) -->` → `<img src="/media/forum/smilies/smile.gif" alt=":)">`
- [ ] Test: URL marker `<!-- m --><a class="postlink" href="https://example.com">text</a><!-- m -->` → `<a ... rel="nofollow">text</a>` (no `<!-- m -->` in output)
- [ ] Test: email marker `<!-- e --><a href="mailto:user@example.com">user@example.com</a><!-- e -->` → `<a href="mailto:..." rel="nofollow">...</a>` (no `<!-- e -->` in output)
- [ ] Test: text with multiple smileys renders all of them correctly
- [ ] Test: text mixing BBCode and smiley (e.g. `[b]hello[/b] <!-- s:) -->...<!-- s:) -->`) → both BBCode and smiley render correctly, no `{SMILIES_PATH}` in output
- [ ] Run `uv run pytest apps/forum_import/tests.py -v` — all tests must pass

### Task 3: Verify acceptance criteria

- [ ] Run full test suite: `uv run pytest`
- [ ] Confirm no `{SMILIES_PATH}` string appears in any stored `text_html` after re-import (checked manually or via shell query)
- [ ] Run `uv run ruff check . && uv run ruff format --check .`

## Post-Completion

**Manual steps (after tests pass):**

1. Copy smiley files to media:
   ```bash
   mkdir -p media/forum/smilies
   cp scratch/forum/images/smilies/* media/forum/smilies/
   ```

2. Re-run post import to regenerate `text_html` for all posts:
   ```bash
   uv run python manage.py import_phpbb_posts
   ```

3. Start dev server and verify post phpbb_id=122150 shows the smiley image (`:)`) instead of raw text.

4. Spot-check a post with external links to confirm `rel="nofollow"` is present and links are clickable.
