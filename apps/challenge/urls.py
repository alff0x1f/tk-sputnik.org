from django.urls import path

from . import views

urlpatterns = [
    path("", views.leaderboard, name="challenge-leaderboard"),
    path("review/", views.review, name="challenge-review"),
    path(
        "review/api/workout/",
        views.api_workout_create,
        name="challenge-api-workout-create",
    ),
    path(
        "review/api/workout/<int:pk>/",
        views.api_workout_detail,
        name="challenge-api-workout-detail",
    ),
    path("photo/<path:filename>", views.challenge_photo, name="challenge-photo"),
]
