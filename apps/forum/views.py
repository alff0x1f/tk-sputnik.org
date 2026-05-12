from django.shortcuts import render

from .models import ForumCategory


def forum_index(request):
    categories = list(ForumCategory.objects.prefetch_related("subforums").all())
    for cat in categories:
        cat.direct_subforum_count = sum(
            1 for sf in cat.subforums.all() if sf.phpbb_parent_id == cat.phpbb_id
        )
    return render(request, "forum/forum.html", {"categories": categories})
