import os

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.db.models import F, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce, NullIf
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.cache import patch_vary_headers

from .models import ForumCategory, Post, PostAttachment, SubForum, Topic


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
            return redirect_to_login(request.get_full_path())
        return HttpResponseForbidden()
    first_post = Post.objects.filter(topic=OuterRef("pk")).order_by("created_at")
    last_post = Post.objects.filter(topic=OuterRef("pk")).order_by("-created_at")
    topics_qs = subforum.topics.annotate(
        first_author=Subquery(_display_name(first_post)[:1]),
        last_post_author=Subquery(_display_name(last_post)[:1]),
        last_post_at=Subquery(last_post.values("created_at")[:1]),
    ).order_by(F("last_post_at").desc(nulls_last=True))
    paginator = Paginator(topics_qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    is_htmx = request.headers.get("HX-Request") == "true"
    template = (
        "forum/subforum_topics_partial.html" if is_htmx else "forum/subforum.html"
    )
    context = {"subforum": subforum, "page_obj": page_obj}
    if not is_htmx:
        page_range = paginator.get_elided_page_range(
            page_obj.number, on_each_side=2, on_ends=2
        )
        context["elided_pages"] = [
            {"num": n, "is_ellipsis": n == Paginator.ELLIPSIS} for n in page_range
        ]
    response = render(request, template, context)
    patch_vary_headers(response, ["HX-Request"])
    return response


def topic_posts(request, pk):
    topic = get_object_or_404(Topic.objects.select_related("subforum"), pk=pk)
    if not _can_access(request, topic.subforum):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        return HttpResponseForbidden()
    posts_qs = topic.posts.select_related("author").order_by("created_at", "id")
    paginator = Paginator(posts_qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    is_htmx = request.headers.get("HX-Request") == "true"
    template = "forum/topic_posts_partial.html" if is_htmx else "forum/topic.html"
    context = {"topic": topic, "page_obj": page_obj}
    if not is_htmx:
        page_range = paginator.get_elided_page_range(
            page_obj.number, on_each_side=2, on_ends=2
        )
        context["elided_pages"] = [
            {"num": n, "is_ellipsis": n == Paginator.ELLIPSIS} for n in page_range
        ]
    response = render(request, template, context)
    patch_vary_headers(response, ["HX-Request"])
    return response


def viewtopic_redirect(request):
    p = request.GET.get("p")
    t = request.GET.get("t")
    f_id = request.GET.get("f")

    if p:
        try:
            post = Post.objects.select_related("topic").get(phpbb_id=int(p))
        except (Post.DoesNotExist, ValueError, TypeError):
            raise Http404
        posts_before = Post.objects.filter(
            topic=post.topic,
        ).filter(
            Q(created_at__lt=post.created_at)
            | Q(created_at=post.created_at, id__lt=post.id)
        ).count()
        page = posts_before // 20 + 1
        url = f"/forum/t/{post.topic.pk}/"
        if page > 1:
            url += f"?page={page}"
        return redirect(f"{url}#post-{post.pk}", permanent=True)

    if t:
        try:
            topic = Topic.objects.get(phpbb_id=int(t))
        except (Topic.DoesNotExist, ValueError, TypeError):
            raise Http404
        start = request.GET.get("start")
        page = 1
        if start:
            try:
                page = int(start) // 20 + 1
            except (ValueError, TypeError):
                pass
        url = f"/forum/t/{topic.pk}/"
        if page > 1:
            url += f"?page={page}"
        return redirect(url, permanent=True)

    if f_id:
        try:
            subforum = SubForum.objects.get(phpbb_id=int(f_id))
        except (SubForum.DoesNotExist, ValueError, TypeError):
            raise Http404
        return redirect(f"/forum/f/{subforum.pk}/", permanent=True)

    return redirect("/forum/", permanent=True)


def serve_attachment(request, pk):
    att = get_object_or_404(
        PostAttachment.objects.select_related("post__topic__subforum"), pk=pk
    )
    if not _can_access(request, att.post.topic.subforum):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        return HttpResponseForbidden()
    path = (
        settings.MEDIA_ROOT
        / "forum"
        / "attachments"
        / os.path.basename(att.physical_filename)
    )
    if not path.is_file():
        raise Http404
    SAFE_INLINE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    serve_inline = att.mimetype in SAFE_INLINE_TYPES
    return FileResponse(
        open(path, "rb"),
        as_attachment=not serve_inline,
        filename=att.real_filename,
        content_type=att.mimetype or "application/octet-stream",
    )
