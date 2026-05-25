# Fix phpBB HTML Comment Link Markers

## Overview

phpBB stores posts in a hybrid BBCode+HTML format where certain inline elements are wrapped in
special HTML comment markers (`<!-- m -->`, `<!-- l -->`, `<!-- w -->`, `<!-- e -->`). The BBCode
renderer handled `<!-- m -->` and `<!-- e -->` but silently dropped `<!-- l -->` (local links) and
`<!-- w -->` (www links), causing the bbcode parser to escape them as visible entities like
`&lt;!&ndash; l &ndash;&gt;` in the rendered HTML.

Additionally, `<!-- l -->` links to `forum.veloufa.ru/viewtopic.php?...` needed to be rewritten to
internal archive URLs (`/forum/viewtopic.php?...`) so that old intra-forum links continue to work.
A new redirect view resolves phpBB-style `viewtopic.php?t=N&p=N&f=N` parameters to the correct
Django archive URLs.

## Context

- **Affected posts**: 624 with `<!-- l -->`, 348 with `<!-- w -->` (out of 115 954 total)
- **Renderer**: `apps/forum_import/management/commands/import_phpbb_posts.py` — `_extract_phpbb_markers()` / `_to_html()`
- **Re-render command**: `apps/forum_import/management/commands/rerender_posts.py`
- **Forum views/URLs**: `apps/forum/views.py`, `apps/forum/urls.py`
- **Tests**: `apps/forum_import/tests.py::ToHtmlSmiliesMarkersTest`, `apps/forum/tests.py::ViewtopicRedirectTests`

## Development Approach

- **Testing approach**: Regular (code first, then tests)
- All tests written and passing before rerender was run on production data

## Solution Overview

1. Added `_WWW_MARKER_RE`, `_LOCAL_MARKER_RE`, `_VELOUFA_VIEWTOPIC_RE` regex constants.
2. Split link marker handling: external links (`m`, `w`, `e`) get `target="_blank" rel="nofollow noreferrer"`; local links (`l`) get plain `<a>` with URL rewrite for viewtopic.php paths.
3. New `viewtopic_redirect` view handles legacy phpBB URL scheme with 301 redirects.
4. Ran `rerender_posts` to update all 115 954 posts in DB.

## Implementation Steps

### Task 1: Fix BBCode marker handling for `<!-- l -->` and `<!-- w -->`

**Files:**
- Modify: `apps/forum_import/management/commands/import_phpbb_posts.py`

- [x] add `_WWW_MARKER_RE = re.compile(r"<!-- w -->(.*?)<!-- w -->", re.DOTALL)`
- [x] add `_LOCAL_MARKER_RE = re.compile(r"<!-- l -->(.*?)<!-- l -->", re.DOTALL)`
- [x] add `_VELOUFA_VIEWTOPIC_RE` to rewrite `http(s)://forum.veloufa.ru/viewtopic.php` → `/forum/viewtopic.php`
- [x] add `replace_local_link_marker()`: rewrites viewtopic.php hrefs, renders without `target`/`nofollow`
- [x] update `replace_link_marker()`: add `target="_blank" rel="nofollow noreferrer"` for `m`, `w`, `e`
- [x] apply `_WWW_MARKER_RE` and `_LOCAL_MARKER_RE` in `_extract_phpbb_markers()`
- [x] write tests: `test_www_marker_renders_with_target_blank`
- [x] write tests: `test_local_marker_veloufa_viewtopic_rewritten`
- [x] write tests: `test_local_marker_non_viewtopic_kept_as_external`
- [x] update existing test: `test_url_marker_renders_with_target_blank` (was `rel_nofollow`)
- [x] run tests — all pass

### Task 2: Add `viewtopic.php` legacy redirect view

**Files:**
- Modify: `apps/forum/views.py`
- Modify: `apps/forum/urls.py`

- [x] add `viewtopic_redirect(request)` view with priority: `p` → post page → 301; `t` → topic → 301; `f` → subforum → 301; fallback → `/forum/`
- [x] page calculation: `posts_before // 20 + 1` (20 posts/page, ordered by `created_at`)
- [x] anchor format: `#post-<django_pk>` (matches template `id="post-{{ post.id }}"`)
- [x] register `path("viewtopic.php", views.viewtopic_redirect, name="viewtopic-redirect")`
- [x] write tests: `ViewtopicRedirectTests` — 7 cases (p/t/f params, page 2 calculation, 404s, no-params)
- [x] run tests — all pass

### Task 3: Re-render posts and verify

- [x] run `uv run python manage.py rerender_posts` — 115 954 posts updated
- [x] spot-check post id=100701: `<!-- l -->` gone, href rewritten to `/forum/viewtopic.php?f=10&t=6057`
- [x] run full test suite: `uv run pytest` — 186/186 passed

## Post-Completion

**Deploy**: run `python manage.py rerender_posts` on production after deploying — already done locally on dev DB.
