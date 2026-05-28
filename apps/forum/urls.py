from django.urls import path

from . import views

urlpatterns = [
    path("", views.forum_index, name="forum-index"),
    path("search/", views.forum_search, name="forum-search"),
    path("f/<int:pk>/", views.subforum_topics, name="subforum-topics"),
    path("t/<int:pk>/", views.topic_posts, name="topic-posts"),
    path("a/<int:pk>/", views.serve_attachment, name="forum-attachment"),
    path("viewtopic.php", views.viewtopic_redirect, name="viewtopic-redirect"),
]
