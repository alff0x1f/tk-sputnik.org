from django.urls import path

from . import views

urlpatterns = [
    path("", views.leaderboard, name="challenge-leaderboard"),
    path("photo/<path:filename>", views.challenge_photo, name="challenge-photo"),
]
