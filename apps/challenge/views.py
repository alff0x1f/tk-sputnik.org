from pathlib import Path

from django.conf import settings
from django.db.models import Count, Sum
from django.http import FileResponse, Http404
from django.shortcuts import render

from .models import Athlete, Workout


def challenge_photo(request, filename):
    base = Path(settings.CHALLENGE_CHAT_EXPORT_DIR).resolve()
    photo_path = (base / filename).resolve()
    if not str(photo_path).startswith(str(base)):
        raise Http404
    if not photo_path.is_file():
        raise Http404
    return FileResponse(open(photo_path, "rb"))


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
