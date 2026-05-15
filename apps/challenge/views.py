import datetime
import json
from pathlib import Path

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from .models import Athlete, SourceMessage, Workout
from .scoring import recompute_athlete_scores


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

    athletes = list(Athlete.objects.order_by("name").values("telegram_id", "name"))

    return render(request, "challenge/review.html", {
        "cards_json": json.dumps(cards, ensure_ascii=False),
        "athletes_json": json.dumps(athletes, ensure_ascii=False),
    })


def _workout_response(workout, athlete):
    total = athlete.workouts.aggregate(t=Sum("total_points"))["t"] or 0
    return JsonResponse({
        "workout": {
            "id": workout.pk,
            "base_points": workout.base_points,
            "streak_bonus": workout.streak_bonus,
            "total_points": workout.total_points,
        },
        "athlete_total": total,
    })


@staff_member_required
@require_http_methods(["POST"])
def api_workout_create(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        athlete = Athlete.objects.get(pk=data["athlete_id"])
    except (Athlete.DoesNotExist, KeyError):
        return JsonResponse({"error": "Athlete not found"}, status=400)

    try:
        date = datetime.date.fromisoformat(data["date"])
    except (KeyError, ValueError):
        return JsonResponse({"error": "Invalid date"}, status=400)

    activity = data.get("activity", "")
    valid_activities = {k for k, _ in Workout.ACTIVITY_CHOICES}
    if activity not in valid_activities:
        return JsonResponse({"error": "Invalid activity"}, status=400)

    workout = Workout.objects.create(
        athlete=athlete,
        date=date,
        activity=activity,
        distance_km=data.get("distance_km"),
        pace_min_per_km=data.get("pace_min_per_km"),
        msg_id=data.get("msg_id"),
    )
    recompute_athlete_scores(athlete)
    workout.refresh_from_db()
    response = _workout_response(workout, athlete)
    response.status_code = 201
    return response


@staff_member_required
@require_http_methods(["PUT", "DELETE"])
def api_workout_detail(request, pk):
    workout = get_object_or_404(Workout, pk=pk)
    old_athlete = workout.athlete

    if request.method == "DELETE":
        workout.delete()
        recompute_athlete_scores(old_athlete)
        return JsonResponse({}, status=204)

    # PUT
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if "athlete_id" in data:
        try:
            workout.athlete = Athlete.objects.get(pk=data["athlete_id"])
        except Athlete.DoesNotExist:
            return JsonResponse({"error": "Athlete not found"}, status=400)

    updatable = ["activity", "distance_km", "pace_min_per_km", "msg_id"]
    for field in updatable:
        if field in data:
            setattr(workout, field, data[field])

    if "date" in data:
        try:
            workout.date = datetime.date.fromisoformat(data["date"])
        except ValueError:
            return JsonResponse({"error": "Invalid date"}, status=400)

    workout.save()
    new_athlete = workout.athlete
    recompute_athlete_scores(new_athlete)
    if old_athlete != new_athlete:
        recompute_athlete_scores(old_athlete)
    workout.refresh_from_db()
    return _workout_response(workout, new_athlete)


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
