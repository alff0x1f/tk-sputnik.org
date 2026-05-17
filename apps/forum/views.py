from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import F, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce, NullIf
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .models import ForumCategory, Post, SubForum, Topic


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


def forum_index(request):
    categories = list(ForumCategory.objects.prefetch_related("subforums").all())
    for cat in categories:
        by_parent = {}
        for sf in cat.subforums.all():
            by_parent.setdefault(sf.phpbb_parent_id, []).append(sf)
        cat.direct_subforums = by_parent.get(cat.id, [])
        for sf in cat.direct_subforums:
            sf.children = by_parent.get(sf.id, [])
    if request.user.is_authenticated:
        user_group_ids = set(request.user.groups.values_list("id", flat=True))
    else:
        user_group_ids = set()
    return render(
        request,
        "forum/forum.html",
        {
            "categories": categories,
            "user_group_ids": user_group_ids,
            "user_is_staff": request.user.is_staff,
        },
    )


def _display_name(qs):
    return qs.annotate(
        _name=Coalesce(NullIf("author_username", Value("")), "author__username")
    ).values("_name")


def subforum_topics(request, pk):
    subforum = get_object_or_404(SubForum, pk=pk)
    if not _can_access(request, subforum):
        if not request.user.is_authenticated:
            return redirect(f"{settings.LOGIN_URL}?next={request.get_full_path()}")
        return HttpResponseForbidden()
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


def topic_posts(request, pk):
    topic = get_object_or_404(Topic.objects.select_related("subforum"), pk=pk)
    if not _can_access(request, topic.subforum):
        if not request.user.is_authenticated:
            return redirect(f"{settings.LOGIN_URL}?next={request.get_full_path()}")
        return HttpResponseForbidden()
    posts_qs = topic.posts.select_related("author").order_by("created_at")
    page_obj = Paginator(posts_qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "forum/topic.html",
        {"topic": topic, "page_obj": page_obj},
    )
