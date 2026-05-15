import json
from pathlib import Path

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.http import FileResponse, Http404
from django.shortcuts import render

from .models import Athlete, SourceMessage, Workout


def challenge_photo(request, filename):
    base = Path(settings.CHALLENGE_CHAT_EXPORT_DIR).resolve()
    photo_path = (base / filename).resolve()
    if not str(photo_path).startswith(str(base)):
        raise Http404
    if not photo_path.is_file():
        raise Http404
    return FileResponse(open(photo_path, "rb"))


@staff_member_required
def review(request):
    messages = list(SourceMessage.objects.order_by("date", "msg_id"))
    workouts_by_msg = {}
    for w in Workout.objects.filter(msg_id__isnull=False).select_related("athlete"):
        workouts_by_msg.setdefault(w.msg_id, []).append(w)

    cards = []
    for msg in messages:
        msg_workouts = workouts_by_msg.get(msg.msg_id, [])
        cards.append({
            "msg_id": msg.msg_id,
            "from_name": msg.from_name,
            "date": str(msg.date),
            "text": msg.text,
            "photos": msg.photos,
            "workouts": [
                {
                    "id": w.pk,
                    "athlete_id": w.athlete_id,
                    "athlete_name": w.athlete.name,
                    "date": str(w.date),
                    "activity": w.activity,
                    "activity_display": w.get_activity_display(),
                    "distance_km": w.distance_km,
                    "pace_min_per_km": w.pace_min_per_km,
                    "base_points": w.base_points,
                    "streak_bonus": w.streak_bonus,
                    "total_points": w.total_points,
                }
                for w in msg_workouts
            ],
        })

    return render(request, "challenge/review.html", {
        "cards_json": json.dumps(cards, ensure_ascii=False),
    })


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
