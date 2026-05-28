import html as _html
import re

from django.contrib.postgres.search import SearchVector
from django.db.models import Value
from django.utils.html import strip_tags

from .models import Post, Topic

SNIPPET_START_SEL = "@@HLS@@"
SNIPPET_STOP_SEL = "@@HLE@@"

_BATCH_SIZE = 500

# Tags that act as word separators — replace with a space before stripping so
# adjacent words across tag boundaries don't merge into one token (e.g.
# "foo<br>bar" → "foo bar", not "foobar").
_SEPARATOR_TAGS_RE = re.compile(
    r"</?(?:br|p|li|ul|ol|div|blockquote|h[1-6]|tr|td|th|hr)(?:\s[^>]*)?/?>",
    re.IGNORECASE,
)


def _html_to_text(html: str) -> str:
    text = _SEPARATOR_TAGS_RE.sub(" ", html)
    text = _html.unescape(strip_tags(text))
    return " ".join(text.split())


def rebuild_search_index(queryset=None):
    """Populate search_text and search_vector for forum posts.

    Returns number of posts processed.
    """
    if queryset is None:
        queryset = Post.objects.all()

    # Strip HTML markup and HTML entities → search_text
    total = 0
    batch = []
    for post in queryset.only("id", "text_html").iterator(chunk_size=_BATCH_SIZE):
        post.search_text = _html_to_text(post.text_html)
        batch.append(post)
        total += 1
        if len(batch) >= _BATCH_SIZE:
            Post.objects.bulk_update(batch, ["search_text"])
            batch = []
    if batch:
        Post.objects.bulk_update(batch, ["search_text"])

    # Phase 1: body weight B for every post in the queryset
    queryset.update(
        search_vector=SearchVector("search_text", weight="B", config="russian")
    )

    # Phase 2: add title weight A to the first post of each relevant topic.
    # The true first post is determined from ALL posts in the topic (not just
    # the queryset subset) so that a partial rebuild cannot promote a later post
    # to title weight when the actual first post was not included.
    topic_ids = queryset.values_list("topic_id", flat=True).distinct()
    for topic in Topic.objects.filter(id__in=topic_ids).only("id", "title"):
        true_first = (
            Post.objects.filter(topic_id=topic.id)
            .order_by("created_at", "id")
            .values("id")
            .first()
        )
        # Only apply title weight if the true first post is part of this rebuild.
        in_queryset = true_first and queryset.filter(id=true_first["id"]).exists()
        first = true_first if in_queryset else None
        if first:
            Post.objects.filter(id=first["id"]).update(
                search_vector=(
                    SearchVector("search_text", weight="B", config="russian")
                    + SearchVector(Value(topic.title), weight="A", config="russian")
                )
            )

    return total
