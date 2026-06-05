import datetime
import json

from django.contrib.admin.views.decorators import staff_member_required
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .models import Athlete, Group, Report, SourceMessage, Workout
from .scoring import recompute_athlete_scores

MAX_REPORT_LEN = 2000


@staff_member_required
def review(request):
    messages = list(SourceMessage.objects.order_by("date", "msg_id"))
    workouts_by_msg = {}
    for w in Workout.objects.filter(msg_id__isnull=False).select_related("athlete"):
        workouts_by_msg.setdefault(w.msg_id, []).append(w)

    cards = []
    for msg in messages:
        msg_workouts = workouts_by_msg.get(msg.msg_id, [])
        cards.append(
            {
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
            }
        )

    athletes = list(Athlete.objects.order_by("name").values("telegram_id", "name"))

    return render(
        request,
        "challenge/review.html",
        {
            "cards_json": json.dumps(cards, ensure_ascii=False)
            .replace("</", "<\\/")
            .replace(" ", "\\u2028")
            .replace(" ", "\\u2029"),
            "athletes_json": json.dumps(athletes, ensure_ascii=False)
            .replace("</", "<\\/")
            .replace(" ", "\\u2028")
            .replace(" ", "\\u2029"),
        },
    )


def _workout_response(workout, athlete):
    total = athlete.workouts.aggregate(t=Sum("total_points"))["t"] or 0
    return JsonResponse(
        {
            "workout": {
                "id": workout.pk,
                "base_points": workout.base_points,
                "streak_bonus": workout.streak_bonus,
                "streak_prev_date": (
                    workout.streak_prev_date.isoformat()
                    if workout.streak_prev_date
                    else None
                ),
                "total_points": workout.total_points,
            },
            "athlete_total": total,
        }
    )


@staff_member_required
@require_http_methods(["POST"])
def api_workout_create(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError, UnicodeDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        athlete = Athlete.objects.get(pk=data["athlete_id"])
    except Athlete.DoesNotExist, KeyError:
        return JsonResponse({"error": "Athlete not found"}, status=400)

    try:
        date = datetime.date.fromisoformat(data["date"])
    except KeyError, ValueError:
        return JsonResponse({"error": "Invalid date"}, status=400)

    activity = data.get("activity", "")
    valid_activities = {k for k, _ in Workout.ACTIVITY_CHOICES}
    if activity not in valid_activities:
        return JsonResponse({"error": "Invalid activity"}, status=400)

    msg_id_raw = data.get("msg_id")
    if msg_id_raw is not None:
        try:
            msg_id_raw = int(msg_id_raw)
        except TypeError, ValueError:
            return JsonResponse({"error": "Invalid msg_id"}, status=400)

    distance_km = data.get("distance_km")
    if distance_km is not None:
        try:
            distance_km = float(distance_km)
        except TypeError, ValueError:
            return JsonResponse({"error": "Invalid distance_km"}, status=400)
        if distance_km < 0:
            return JsonResponse(
                {"error": "distance_km must be non-negative"}, status=400
            )

    pace_min_per_km = data.get("pace_min_per_km")
    if pace_min_per_km is not None:
        try:
            pace_min_per_km = float(pace_min_per_km)
        except TypeError, ValueError:
            return JsonResponse({"error": "Invalid pace_min_per_km"}, status=400)
        if pace_min_per_km < 0:
            return JsonResponse(
                {"error": "pace_min_per_km must be non-negative"}, status=400
            )

    with transaction.atomic():
        try:
            workout = Workout.objects.create(
                athlete=athlete,
                date=date,
                activity=activity,
                distance_km=distance_km,
                pace_min_per_km=pace_min_per_km,
                msg_id=msg_id_raw,
            )
        except IntegrityError:
            return JsonResponse(
                {"error": "Workout already exists for this athlete/date/activity"},
                status=400,
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
        with transaction.atomic():
            workout.delete()
            recompute_athlete_scores(old_athlete)
        return HttpResponse(status=204)

    # PUT
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError, UnicodeDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if "athlete_id" in data:
        try:
            workout.athlete = Athlete.objects.get(pk=data["athlete_id"])
        except Athlete.DoesNotExist:
            return JsonResponse({"error": "Athlete not found"}, status=400)

    if "activity" in data:
        if data["activity"] not in {k for k, _ in Workout.ACTIVITY_CHOICES}:
            return JsonResponse({"error": "Invalid activity"}, status=400)
        workout.activity = data["activity"]
    updatable = ["distance_km", "pace_min_per_km"]
    for field in updatable:
        if field in data:
            val = data[field]
            if val is not None:
                try:
                    val = float(val)
                except TypeError, ValueError:
                    return JsonResponse({"error": f"Invalid {field}"}, status=400)
                if val < 0:
                    return JsonResponse(
                        {"error": f"{field} must be non-negative"}, status=400
                    )
            setattr(workout, field, val)

    if "msg_id" in data:
        if data["msg_id"] is not None:
            try:
                workout.msg_id = int(data["msg_id"])
            except TypeError, ValueError:
                return JsonResponse({"error": "Invalid msg_id"}, status=400)
        else:
            workout.msg_id = None

    if "date" in data:
        try:
            workout.date = datetime.date.fromisoformat(data["date"])
        except TypeError, ValueError:
            return JsonResponse({"error": "Invalid date"}, status=400)

    with transaction.atomic():
        try:
            workout.save()
        except IntegrityError:
            return JsonResponse(
                {"error": "Workout already exists for this athlete/date/activity"},
                status=400,
            )
        new_athlete = workout.athlete
        recompute_athlete_scores(new_athlete)
        if old_athlete != new_athlete:
            recompute_athlete_scores(old_athlete)
    workout.refresh_from_db()
    return _workout_response(workout, new_athlete)


def _group_messages(messages, workouts_by_msg, athlete_telegram_id=""):
    groups = []
    msgs = list(messages)
    i = 0
    while i < len(msgs):
        msg = msgs[i]
        group = [msg]
        j = i + 1
        while (
            j < len(msgs)
            and msg.datetime is not None
            and msgs[j].datetime == msg.datetime
        ):
            group.append(msgs[j])
            j += 1

        photos = [p for m in group for p in m.photos]
        text = "\n".join(m.text for m in group if m.text)
        workouts = []
        for m in group:
            if m.msg_id in workouts_by_msg:
                workouts.extend(workouts_by_msg[m.msg_id])
        seen = set()
        foreign_senders = []
        for m in group:
            is_foreign = m.from_id and m.from_id != athlete_telegram_id
            if is_foreign and m.from_id not in seen:
                seen.add(m.from_id)
                foreign_senders.append(m.from_name)
        groups.append(
            {
                "msgs": group,
                "primary_msg_id": group[0].msg_id,
                "photos": photos,
                "text": text,
                "workouts": workouts,
                "date": group[0].date,
                "foreign_senders": foreign_senders,
            }
        )
        i = j
    return groups


@ensure_csrf_cookie
def member_detail(request, telegram_id):
    athlete = get_object_or_404(Athlete, pk=telegram_id)
    all_workouts = list(Workout.objects.filter(athlete=athlete))
    linked_workouts = [w for w in all_workouts if w.msg_id is not None]
    workout_msg_ids = [w.msg_id for w in linked_workouts]
    messages = (
        SourceMessage.objects.filter(
            Q(from_id=athlete.telegram_id) | Q(msg_id__in=workout_msg_ids)
        )
        .order_by("date", "msg_id")
        .distinct()
    )
    workouts_by_msg = {}
    for w in linked_workouts:
        workouts_by_msg.setdefault(w.msg_id, []).append(w)
    groups = _group_messages(messages, workouts_by_msg, athlete.telegram_id)
    if request.user.is_staff:
        primary_ids = [g["primary_msg_id"] for g in groups]
        reports_by_msg = {}
        for r in Report.objects.filter(
            message_id__in=primary_ids, resolved=False, athlete=athlete
        ).order_by("created_at"):
            reports_by_msg.setdefault(r.message_id, []).append(r)
        for g in groups:
            g["reports"] = reports_by_msg.get(g["primary_msg_id"], [])
    total_points = sum(w.total_points for w in all_workouts)
    workout_count = len(all_workouts)
    return render(
        request,
        "challenge/member.html",
        {
            "athlete": athlete,
            "groups": groups,
            "total_points": total_points,
            "workout_count": workout_count,
        },
    )


@require_http_methods(["POST"])
def api_report_create(request, telegram_id):
    athlete = get_object_or_404(Athlete, pk=telegram_id)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError, UnicodeDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    raw_text = data.get("text")
    text = (raw_text.strip() if isinstance(raw_text, str) else "")
    if not text:
        return JsonResponse({"error": "text required"}, status=400)
    if len(text) > MAX_REPORT_LEN:
        return JsonResponse({"error": "text too long"}, status=400)

    raw_msg_id = data.get("msg_id")
    # Use type() not isinstance() to reject bool (True/False subclasses int).
    if type(raw_msg_id) is not int:
        return JsonResponse({"error": "message not found"}, status=400)
    try:
        message = SourceMessage.objects.get(pk=raw_msg_id)
    except SourceMessage.DoesNotExist:
        return JsonResponse({"error": "message not found"}, status=400)

    if (
        message.from_id != athlete.telegram_id
        and not athlete.workouts.filter(msg_id=raw_msg_id).exists()
    ):
        return JsonResponse({"error": "message not found"}, status=400)

    Report.objects.create(message=message, athlete=athlete, text=text)
    return JsonResponse({"ok": True}, status=201)


@staff_member_required
@require_http_methods(["PUT", "DELETE"])
def api_report_detail(request, pk):
    report = get_object_or_404(Report, pk=pk)
    if request.method == "DELETE":
        report.delete()
        return HttpResponse(status=204)
    # PUT
    report.resolved = True
    report.save(update_fields=["resolved"])
    return JsonResponse({"ok": True})


def leaderboard(request):
    athletes = list(
        Athlete.objects.select_related("group")
        .annotate(
            total_score=Sum("workouts__total_points", default=0),
            workout_count=Count("workouts"),
        )
        .order_by("-total_score", "name")
    )
    for i, athlete in enumerate(athletes, 1):
        athlete.rank = i
    return render(request, "challenge/leaderboard.html", {"athletes": athletes})


@staff_member_required
@require_http_methods(["PUT"])
def api_athlete_group(request, telegram_id):
    athlete = get_object_or_404(Athlete, pk=telegram_id)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError, UnicodeDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not isinstance(data, dict) or "group_id" not in data:
        return JsonResponse({"error": "group_id required"}, status=400)

    group_id = data["group_id"]
    if group_id is None:
        athlete.group = None
    else:
        if type(group_id) is not int:
            return JsonResponse(
                {"error": "group_id must be an integer or null"}, status=400
            )
        try:
            athlete.group = Group.objects.get(pk=group_id)
        except Group.DoesNotExist:
            return JsonResponse({"error": "Group not found"}, status=400)
    athlete.save(update_fields=["group"])
    return JsonResponse({"ok": True})


@staff_member_required
def groups(request):
    athletes = Athlete.objects.select_related("group").order_by("name")
    all_groups = Group.objects.all()
    return render(
        request,
        "challenge/groups.html",
        {"athletes": athletes, "groups": all_groups},
    )
