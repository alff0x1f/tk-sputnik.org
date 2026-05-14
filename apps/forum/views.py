from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery
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


def subforum_topics(request, phpbb_id):
    subforum = get_object_or_404(SubForum, phpbb_id=phpbb_id)
    first_post = Post.objects.filter(topic=OuterRef("pk")).order_by("created_at")
    last_post = Post.objects.filter(topic=OuterRef("pk")).order_by("-created_at")
    topics_qs = subforum.topics.annotate(
        first_author=Subquery(first_post.values("author_username")[:1]),
        last_post_author=Subquery(last_post.values("author_username")[:1]),
        last_post_at=Subquery(last_post.values("created_at")[:1]),
    ).order_by("-created_at")
    page_obj = Paginator(topics_qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "forum/subforum.html",
        {"subforum": subforum, "page_obj": page_obj},
    )
