from .models import Workout


def compute_base_points(activity, distance_km, pace_min_per_km):
    """Return base points (0, 2, or 3) for a single workout."""
    if activity == "hiking":
        return 2

    if activity == "running":
        if distance_km is None or pace_min_per_km is None:
            return 0
        if pace_min_per_km >= 10:
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
    workouts = list(athlete.workouts.order_by("date"))

    prev_qualifying_date = None
    for workout in workouts:
        base = compute_base_points(
            workout.activity, workout.distance_km, workout.pace_min_per_km
        )
        workout.base_points = base

        if base > 0:
            if prev_qualifying_date is not None:
                gap = (workout.date - prev_qualifying_date).days
                workout.streak_bonus = 1 if gap <= 4 else 0
            else:
                workout.streak_bonus = 0
            prev_qualifying_date = workout.date
        else:
            workout.streak_bonus = 0

        workout.total_points = workout.base_points + workout.streak_bonus

    Workout.objects.bulk_update(
        workouts, ["base_points", "streak_bonus", "total_points"]
    )
