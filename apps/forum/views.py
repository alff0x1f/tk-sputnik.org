from django.shortcuts import render

from .models import ForumCategory


def forum_index(request):
    categories = ForumCategory.objects.prefetch_related("subforums").all()
    return render(request, "forum/forum.html", {"categories": categories})
