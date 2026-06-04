from .models import Workout


def compute_base_points(activity, distance_km, pace_min_per_km):
    """Return base points (0, 2, or 3) for a single workout."""
    if activity == "hiking":
        return 2

    if activity == "running":
        if distance_km is None:
            return 0
        # Темп указывают не всегда; если он отсутствует, считаем его
        # достаточным (<10 мин/км) и начисляем по дистанции. Ноль ставим
        # только когда темп задан явно и он 10 мин/км или хуже.
        if pace_min_per_km is not None and pace_min_per_km >= 10:
            return 0
        if distance_km >= 10:
            return 3
        if distance_km >= 5:
            return 2
        return 0

    if activity == "skiing":
        if distance_km is None:
            return 0
        if distance_km >= 12:
            return 3
        if distance_km >= 6:
            return 2
        return 0

    if activity == "cycling":
        if distance_km is None:
            return 0
        if distance_km >= 40:
            return 3
        if distance_km >= 20:
            return 2
        return 0

    if activity == "swimming":
        if distance_km is None:
            return 0
        if distance_km >= 2:
            return 3
        if distance_km >= 1:
            return 2
        return 0

    return 0


def recompute_athlete_scores(athlete):
    """Recompute base_points, streak_bonus, total_points for all workouts of an athlete.

    Workouts are processed in date order. Streak bonus (+1) is awarded when the
    gap from the previous qualifying workout (base_points > 0) is ≤ 4 days.
    Same-day deduplication is expected to be handled at import time.
    """
    workouts = list(athlete.workouts.order_by("date", "pk"))

    prev_qualifying_date = None
    for workout in workouts:
        base = compute_base_points(
            workout.activity, workout.distance_km, workout.pace_min_per_km
        )
        workout.base_points = base

        if base > 0:
            if (
                prev_qualifying_date is not None
                and (workout.date - prev_qualifying_date).days <= 4
            ):
                workout.streak_bonus = 1
                workout.streak_prev_date = prev_qualifying_date
            else:
                workout.streak_bonus = 0
                workout.streak_prev_date = None
            prev_qualifying_date = workout.date
        else:
            workout.streak_bonus = 0
            workout.streak_prev_date = None

        workout.total_points = workout.base_points + workout.streak_bonus

    Workout.objects.bulk_update(
        workouts,
        ["base_points", "streak_bonus", "streak_prev_date", "total_points"],
    )
