from django.db.models import Count, Sum
from django.shortcuts import render

from .models import Athlete, Workout


def leaderboard(request):
    athletes = list(
        Athlete.objects.annotate(
            total_score=Sum("workouts__total_points", default=0),
            workout_count=Count("workouts"),
        ).order_by("-total_score", "name")
    )
    for i, athlete in enumerate(athletes, 1):
        athlete.rank = i
        athlete.workout_list = list(
            Workout.objects.filter(athlete=athlete).order_by("date")
        )
    return render(request, "challenge/leaderboard.html", {"athletes": athletes})
