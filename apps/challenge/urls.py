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
    path("groups/", views.groups, name="challenge-groups"),
    path(
        "groups/api/athlete/<str:telegram_id>/",
        views.api_athlete_group,
        name="challenge-api-athlete-group",
    ),
    path("photo/<path:filename>", views.challenge_photo, name="challenge-photo"),
    path("member/<str:telegram_id>/", views.member_detail, name="challenge-member"),
    path(
        "member/<str:telegram_id>/api/report/",
        views.api_report_create,
        name="challenge-api-report-create",
    ),
    path(
        "review/api/report/<int:pk>/",
        views.api_report_detail,
        name="challenge-api-report-detail",
    ),
]
