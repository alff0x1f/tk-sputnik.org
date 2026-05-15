from django.urls import path

from . import views

urlpatterns = [
    path("", views.forum_index, name="forum-index"),
    path("f/<int:pk>/", views.subforum_topics, name="subforum-topics"),
    path("t/<int:pk>/", views.topic_posts, name="topic-posts"),
]
