# Subforum Topic List View

## Overview
Add a topic-list page for each subforum in the phpBB forum archive. Currently the forum shows only the index (categories + subforums). Clicking a subforum leads nowhere — this plan wires up navigation to `/forum/f/<phpbb_id>/` and renders a paginated list of topics with author and last-post info.

## Context (from discovery)
- Branch: `feat/show-subfforums`
- `apps/forum/views.py` — single `forum_index` view; no subforum or topic views
- `apps/forum/urls.py` — single `""` route; no `/f/` path
- `apps/forum/templates/forum/forum.html` — subforum rows are `<div class="subforum">` with no `href`
- `apps/forum/static/forum/css/forum.css` — has all subforum styles; no `.topic` rules yet
- `Topic` model fields: `phpbb_id`, `subforum (FK)`, `title`, `created_at`, `post_count`
- `Post` model fields: `phpbb_id`, `topic (FK)`, `author (FK, nullable)`, `author_username`, `created_at`

## Development Approach
- **Testing approach**: Regular (code first, tests after)
- Complete each task fully before moving to the next
- All tests must pass before starting next task

## Solution Overview
- New URL `/forum/f/<phpbb_id>/` with `?page=N` query param
- View uses `Subquery` annotations to pull `first_author`, `last_post_author`, `last_post_at` onto each `Topic` row — no model changes, no N+1
- Forum index gets `href` links on subforum rows (wrap `.sf-title` in `<a>`)
- New template `forum/subforum.html` mirrors the index style: breadcrumbs, subforum header, topic grid rows, pagination
- Topic CSS extracted from `demo/forum.html` and added to `forum.css`

## Technical Details

**Subquery pattern (view):**
```python
from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404, render
from .models import Post, SubForum

def subforum_topics(request, phpbb_id):
    subforum = get_object_or_404(SubForum, phpbb_id=phpbb_id)
    first_post = Post.objects.filter(topic=OuterRef("pk")).order_by("created_at")
    last_post  = Post.objects.filter(topic=OuterRef("pk")).order_by("-created_at")
    topics_qs = subforum.topics.annotate(
        first_author=Subquery(first_post.values("author_username")[:1]),
        last_post_author=Subquery(last_post.values("author_username")[:1]),
        last_post_at=Subquery(last_post.values("created_at")[:1]),
    ).order_by("-created_at")
    page_obj = Paginator(topics_qs, 25).get_page(request.GET.get("page"))
    return render(request, "forum/subforum.html", {"subforum": subforum, "page_obj": page_obj})
```

**Topic row layout (matches demo):**
```
[ ico ] title                    | replies | last post
        by first_author          |         | author · date
```

**URL naming:**
- `forum-index` → `/forum/` (existing)
- `subforum-topics` → `/forum/f/<phpbb_id>/` (new)

**Pagination:** `?page=N`, rendered only when `page_obj.paginator.num_pages > 1`

## Implementation Steps

### Task 1: Add URL route and view

**Files:**
- Modify: `apps/forum/urls.py`
- Modify: `apps/forum/views.py`

- [x] Add `from django.core.paginator import Paginator` and `from django.shortcuts import get_object_or_404` to `views.py`
- [x] Add `from django.db.models import OuterRef, Subquery` to `views.py`
- [x] Add `Post, SubForum` to the models import in `views.py`
- [x] Implement `subforum_topics(request, phpbb_id)` view using the Subquery pattern above
- [x] Add `path("f/<int:phpbb_id>/", views.subforum_topics, name="subforum-topics")` to `urls.py`
- [x] Run `uv run ruff check apps/forum/views.py apps/forum/urls.py` — fix any issues

### Task 2: Add topic CSS to forum.css

**Files:**
- Modify: `apps/forum/static/forum/css/forum.css`

- [x] Append `.topic`, `.topic-ico`, `.topic-body`, `.topic-title`, `.topic-meta`, `.topic-stats`, `.topic-last` rules from `apps/demo/templates/demo/forum.html` `<style>` block (lines 117–163 of the demo template)
- [x] Add responsive overrides for `.topic` at 1000px and 720px breakpoints (matching demo)
- [x] Add `.pagination` styles for the page navigation (simple `display:flex; gap:4px` row of page links)

### Task 3: Create subforum template

**Files:**
- Create: `apps/forum/templates/forum/subforum.html`

- [x] Extend `demo/base.html`, load `static`, link `forum/css/forum.css`
- [x] Breadcrumbs: Форум (link to `forum-index`) › Category name › Subforum name
- [x] Subforum header block: name as `<h1>`, description, stats (topic_count, post_count)
- [x] Topic list: iterate `page_obj` — one `.topic` row per topic with icon, title + `by {{ topic.first_author|default:"—" }}`, `{{ topic.post_count }}` replies, last post author + date formatted as `d.m.Y`
- [x] Empty state: show "Тем нет" if `page_obj.object_list` is empty
- [x] Pagination block (only if `page_obj.paginator.num_pages > 1`): previous/next links + page numbers using `page_obj.paginator.page_range`

### Task 4: Link subforums on forum index

**Files:**
- Modify: `apps/forum/templates/forum/forum.html`

- [ ] Wrap `.sf-title` text in `<a href="{% url 'subforum-topics' subforum.phpbb_id %}">` on direct subforums
- [ ] Do the same for child subforum `.sf-child` chips (use `child.phpbb_id`)
- [ ] Remove `cursor:pointer` from `.subforum:hover` in `forum.css` (the title link provides navigation; full-row pointer without full-row link is misleading)

### Task 5: Tests

**Files:**
- Modify: `apps/forum/tests.py`

- [ ] Add `SubforumTopicsViewTest` test class
- [ ] Test: GET `/forum/f/<phpbb_id>/` returns 200 and uses `forum/subforum.html` template
- [ ] Test: 404 for unknown phpbb_id
- [ ] Test: `page_obj` in context, contains correct topics for the subforum
- [ ] Test: pagination — create 26 topics, verify page 1 has 25 and `?page=2` has 1
- [ ] Run `uv run pytest apps/forum/tests.py` — must pass

### Task 6: Verify acceptance criteria

- [ ] Run `uv run pytest` — full suite green
- [ ] Run `uv run ruff check .` — no lint errors
- [ ] Manually verify: forum index → click subforum title → topic list loads with correct data
- [ ] Verify breadcrumbs link back to forum index
- [ ] Verify pagination renders correctly when > 25 topics

### Task 7: [Final] Update documentation

- [ ] Update `CLAUDE.md` if new patterns introduced (unlikely — this follows existing patterns)
- [ ] Move this plan to `docs/plans/completed/`

## Post-Completion

**Manual verification:**
- Open forum index in browser, confirm subforum titles are now links
- Navigate into a subforum with many topics, verify pagination controls appear
- Check responsive layout at mobile width (720px) — last-post column should hide
