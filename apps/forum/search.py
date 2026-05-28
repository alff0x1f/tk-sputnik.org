import html as _html

from django.contrib.postgres.search import SearchVector
from django.db.models import Value
from django.utils.html import strip_tags

from .models import Post, Topic

SNIPPET_START_SEL = "@@HLS@@"
SNIPPET_STOP_SEL = "@@HLE@@"

_BATCH_SIZE = 500


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
        post.search_text = _html.unescape(strip_tags(post.text_html))
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

    # Phase 2: add title weight A to the first post of each relevant topic
    topic_ids = queryset.values_list("topic_id", flat=True).distinct()
    for topic in Topic.objects.filter(id__in=topic_ids).only("id", "title"):
        first = (
            Post.objects.filter(topic_id=topic.id)
            .order_by("created_at", "id")
            .values("id")
            .first()
        )
        if first:
            Post.objects.filter(id=first["id"]).update(
                search_vector=(
                    SearchVector("search_text", weight="B", config="russian")
                    + SearchVector(Value(topic.title), weight="A", config="russian")
                )
            )

    return total
