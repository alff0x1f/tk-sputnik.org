from django.shortcuts import render

from .models import ForumCategory


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
