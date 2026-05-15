# Forum: Topic Posts Page

## Overview
Add a topic page at `/forum/t/<phpbb_id>/` that renders all posts in a thread with a modern
Twitter/Threads/Reddit-style layout — no sidebar panel, avatar circle with initials, username and
date inline, HTML content below. The topic title in the subforum list becomes a clickable link.

Problem solved: the forum archive currently has no way to read actual messages; navigation ends at
the topic list.

## Context (from discovery)

- **Files involved:** `apps/forum/views.py`, `apps/forum/urls.py`,
  `apps/forum/templates/forum/subforum.html`, `apps/forum/static/forum/css/forum.css`
- **New file:** `apps/forum/templates/forum/topic.html`
- **Patterns observed:** views use `get_object_or_404`, `Paginator`, `select_related`/`prefetch_related`;
  templates extend `demo/base.html` and use `{% load static %}`; CSS uses CSS variables (`--ink`,
  `--muted`, `--line`, `--surface`, `--accent`, etc.) from the base theme
- **Post content:** `Post.text_html` is phpBB-generated HTML, safe to render as-is (read-only
  import). Quotes are `<blockquote class="quote">` — styled via CSS only, no HTML transformation
- **Pagination:** 20 posts per page (subforum uses 25 for topics)
- **Author display:** `Post.author_username` (fallback) or `Post.author.username`; avatar is
  `ForumUser.avatar` (URL string, may be empty → fall back to initials circle)

## Development Approach

- **Testing approach:** Regular (code first, then tests)
- Complete each task fully before moving to the next
- All tests must pass before starting next task

## Testing Strategy

- **Unit tests:** added to existing `apps/forum/tests.py`
- No e2e tests in project

## Progress Tracking

- Mark completed items with `[x]` immediately when done
- Add newly discovered tasks with ➕ prefix
- Document blockers with ⚠️ prefix

## Solution Overview

1. Add `topic_posts` view — fetch `Topic` by `phpbb_id`, paginate `Post` queryset
   (`select_related("author")`), pass to template
2. Wire URL `t/<int:phpbb_id>/` → `topic-posts`
3. Make topic rows in `subforum.html` clickable links
4. Create `topic.html` with post cards: initials-circle avatar + author name + date header,
   `text_html|safe` body
5. Add CSS for `.post-card`, `.post-author`, `.post-avatar`, `.post-body`, and
   `.post-body blockquote` (Reddit-style quoted block)

## Implementation Steps

### Task 1: Add `topic_posts` view and URL

**Files:**
- Modify: `apps/forum/views.py`
- Modify: `apps/forum/urls.py`

- [x] add `topic_posts(request, phpbb_id)` to `views.py`:
  - `get_object_or_404(Topic, phpbb_id=phpbb_id)`
  - `topic.posts.select_related("author").order_by("created_at")`
  - `Paginator(..., 20).get_page(request.GET.get("page"))`
  - render `forum/topic.html` with context `{"topic": topic, "page_obj": page_obj}`
- [x] add `path("t/<int:phpbb_id>/", views.topic_posts, name="topic-posts")` to `urls.py`
- [x] write tests in `apps/forum/tests.py` — class `TopicPostsViewTest`:
  - `test_returns_200` — valid phpbb_id
  - `test_404_for_unknown_phpbb_id`
  - `test_uses_correct_template` — `forum/topic.html`
  - `test_context_has_topic_and_page_obj`
  - `test_page_obj_contains_only_topic_posts` — posts from another topic are absent
  - `test_pagination_20_per_page` — create 21 posts, check page 1 has 20, page 2 has 1
- [x] run `uv run pytest apps/forum/tests.py` — must pass before task 2

### Task 2: Make topic titles clickable in `subforum.html`

**Files:**
- Modify: `apps/forum/templates/forum/subforum.html`

- [x] wrap `.topic-title` text in `<a href="{% url 'topic-posts' topic.phpbb_id %}">...</a>`
- [x] ensure link inherits existing `.topic-title` color (no underline on hover or `text-decoration:none`)
  — add CSS rule if needed (see Task 3)
- [x] run `uv run pytest apps/forum/tests.py` — must still pass

### Task 3: CSS — post card and blockquote styles

**Files:**
- Modify: `apps/forum/static/forum/css/forum.css`

- [x] add `.post-card` — card container with bottom border separator, no heavy box shadow
- [x] add `.post-author` — flex row: avatar circle + username (`.post-author-name`) + date
  (`.post-date`) spaced apart
- [x] add `.post-avatar` — circle `36px`, `background: var(--accent-soft)`, centered initial letter,
  font-size `14px`, `font-weight:600`
- [x] add `.post-body` — rendered HTML area; set `font-size:14px`, `line-height:1.65`,
  `color:var(--ink)`; handle `p`, `br` spacing
- [x] add `.post-body blockquote` — Reddit-style: `border-left: 3px solid var(--line-strong)`,
  `background: var(--surface-2)`, `padding: 8px 12px`, `margin: 10px 0`,
  `color: var(--muted)`, `font-size:13px`
- [x] add `.topic-title a` rule — `color:inherit; text-decoration:none` with `:hover` underline
- [x] responsive: on `max-width:720px` shrink avatar to `30px`
- [x] no tests needed for CSS; visually verify in browser after task 4

### Task 4: Create `topic.html` template

**Files:**
- Create: `apps/forum/templates/forum/topic.html`

- [ ] extend `demo/base.html`, load static, link `forum/css/forum.css`
- [ ] breadcrumbs: Форум → category name → subforum name → topic title (last item not linked)
- [ ] `<h1>` with topic title + meta line (автор первого поста, дата создания, кол-во сообщений)
- [ ] loop `page_obj`: for each post render `.post-card`:
  - `.post-author`: avatar circle (first letter of display name, or `<img>` if `post.author.avatar`),
    author display name, dot separator, formatted date (`d M Y`)
  - `.post-body`: `{{ post.text_html|safe }}`
- [ ] pagination (reuse `.pagination` CSS already in `forum.css`)
- [ ] display name helper: use `post.author_username` if non-empty, else `post.author.username`,
  else `"—"` — implement as template `{% with %}` block or template tag (prefer `{% with %}`)
- [ ] run `uv run pytest apps/forum/tests.py` — must pass

### Task 5: Verify acceptance criteria

- [ ] start dev server: `uv run python manage.py runserver`
- [ ] open `/forum/` → click subforum → topic list loads with clickable titles
- [ ] click a topic → post list renders with author circles, dates, HTML content
- [ ] check posts with `<blockquote>` — indented left-border style visible
- [ ] check pagination if topic has >20 posts
- [ ] verify mobile layout at `max-width:720px` (resize browser)
- [ ] run full test suite: `uv run pytest`
- [ ] run linter: `uv run ruff check .`

### Task 6: [Final] Move plan

- [ ] move this plan to `docs/plans/completed/20260515-forum-topic-posts.md`

## Post-Completion

**Manual verification:**
- Check a topic with long posts (images, code blocks, complex quotes) for layout issues
- Verify avatar URLs from `ForumUser.avatar` render correctly if present in data
