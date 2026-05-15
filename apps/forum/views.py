from django.core.paginator import Paginator
from django.db.models import F, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce, NullIf
from django.shortcuts import get_object_or_404, render

from .models import ForumCategory, Post, SubForum


def forum_index(request):
    categories = list(ForumCategory.objects.prefetch_related("subforums").all())
    for cat in categories:
        by_parent = {}
        for sf in cat.subforums.all():
            by_parent.setdefault(sf.phpbb_parent_id, []).append(sf)
        cat.direct_subforums = by_parent.get(cat.phpbb_id, [])
        for sf in cat.direct_subforums:
            sf.children = by_parent.get(sf.phpbb_id, [])
    return render(request, "forum/forum.html", {"categories": categories})


def _display_name(qs):
    return qs.annotate(
        _name=Coalesce(NullIf("author_username", Value("")), "author__username")
    ).values("_name")


def subforum_topics(request, phpbb_id):
    subforum = get_object_or_404(SubForum, phpbb_id=phpbb_id)
    first_post = Post.objects.filter(topic=OuterRef("pk")).order_by("created_at")
    last_post = Post.objects.filter(topic=OuterRef("pk")).order_by("-created_at")
    topics_qs = subforum.topics.annotate(
        first_author=Subquery(_display_name(first_post)[:1]),
        last_post_author=Subquery(_display_name(last_post)[:1]),
        last_post_at=Subquery(last_post.values("created_at")[:1]),
    ).order_by(F("last_post_at").desc(nulls_last=True))
    page_obj = Paginator(topics_qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "forum/subforum.html",
        {"subforum": subforum, "page_obj": page_obj},
    )
