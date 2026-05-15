from django.urls import path

from . import views

urlpatterns = [
    path("", views.forum_index, name="forum-index"),
    path("f/<int:phpbb_id>/", views.subforum_topics, name="subforum-topics"),
    path("t/<int:phpbb_id>/", views.topic_posts, name="topic-posts"),
]
