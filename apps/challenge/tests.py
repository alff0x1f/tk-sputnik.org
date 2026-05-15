import datetime

from django.test import TestCase

from .models import Athlete, SourceMessage, Workout
from .scoring import compute_base_points, recompute_athlete_scores


class AthleteModelTests(TestCase):
    def test_create_and_str(self):
        athlete = Athlete.objects.create(telegram_id="u123", name="Иван Иванов")
        self.assertEqual(str(athlete), "Иван Иванов")
        self.assertEqual(Athlete.objects.count(), 1)

    def test_primary_key_is_telegram_id(self):
        Athlete.objects.create(telegram_id="u999", name="Петр")
        retrieved = Athlete.objects.get(pk="u999")
        self.assertEqual(retrieved.name, "Петр")

    def test_duplicate_telegram_id_raises(self):
        Athlete.objects.create(telegram_id="u111", name="First")
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Athlete.objects.create(telegram_id="u111", name="Duplicate")


class WorkoutModelTests(TestCase):
    def setUp(self):
        self.athlete = Athlete.objects.create(telegram_id="u1", name="Тест")

    def test_create_and_str(self):
        w = Workout.objects.create(
            athlete=self.athlete,
            date=datetime.date(2026, 1, 10),
            activity="running",
            distance_km=10.0,
            pace_min_per_km=5.5,
            base_points=2,
            streak_bonus=1,
            total_points=3,
            msg_id=42,
        )
        self.assertIn("running", str(w))
        self.assertIn("Тест", str(w))

    def test_defaults(self):
        w = Workout.objects.create(
            athlete=self.athlete,
            date=datetime.date(2026, 1, 11),
            activity="hiking",
        )
        self.assertEqual(w.base_points, 0)
        self.assertEqual(w.streak_bonus, 0)
        self.assertEqual(w.total_points, 0)
        self.assertIsNone(w.distance_km)
        self.assertIsNone(w.pace_min_per_km)
        self.assertIsNone(w.msg_id)

    def test_fk_cascade_delete(self):
        Workout.objects.create(
            athlete=self.athlete,
            date=datetime.date(2026, 1, 12),
            activity="skiing",
            distance_km=8.0,
        )
        self.assertEqual(Workout.objects.count(), 1)
        self.athlete.delete()
        self.assertEqual(Workout.objects.count(), 0)

    def test_related_name(self):
        Workout.objects.create(
            athlete=self.athlete,
            date=datetime.date(2026, 1, 13),
            activity="cycling",
            distance_km=25.0,
        )
        self.assertEqual(self.athlete.workouts.count(), 1)


class SourceMessageModelTests(TestCase):
    def test_create_and_str(self):
        msg = SourceMessage.objects.create(
            msg_id=1001,
            from_name="Мария",
            date=datetime.date(2026, 1, 5),
            text="Пробежала 10 км",
            photos=["photos/img1.jpg"],
        )
        self.assertIn("1001", str(msg))
        self.assertIn("Мария", str(msg))

    def test_primary_key_is_msg_id(self):
        SourceMessage.objects.create(
            msg_id=2000,
            from_name="Алексей",
            date=datetime.date(2026, 1, 6),
        )
        retrieved = SourceMessage.objects.get(pk=2000)
        self.assertEqual(retrieved.from_name, "Алексей")

    def test_defaults(self):
        msg = SourceMessage.objects.create(
            msg_id=3000,
            from_name="Кто-то",
            date=datetime.date(2026, 1, 7),
        )
        self.assertEqual(msg.text, "")
        self.assertEqual(msg.photos, [])


class ComputeBasePointsTests(TestCase):
    def test_hiking_always_two(self):
        self.assertEqual(compute_base_points("hiking", None, None), 2)
        self.assertEqual(compute_base_points("hiking", 0.0, None), 2)

    def test_running_none_inputs(self):
        self.assertEqual(compute_base_points("running", None, 5.0), 0)
        self.assertEqual(compute_base_points("running", 10.0, None), 0)

    def test_running_pace_too_slow(self):
        self.assertEqual(compute_base_points("running", 10.0, 10.0), 0)
        self.assertEqual(compute_base_points("running", 10.0, 12.0), 0)

    def test_running_below_threshold(self):
        self.assertEqual(compute_base_points("running", 4.9, 5.0), 0)

    def test_running_two_points(self):
        self.assertEqual(compute_base_points("running", 5.0, 5.0), 2)
        self.assertEqual(compute_base_points("running", 9.9, 9.9), 2)

    def test_running_three_points(self):
        self.assertEqual(compute_base_points("running", 10.0, 5.0), 3)
        self.assertEqual(compute_base_points("running", 20.0, 5.0), 3)

    def test_skiing_none_distance(self):
        self.assertEqual(compute_base_points("skiing", None, None), 0)

    def test_skiing_below_threshold(self):
        self.assertEqual(compute_base_points("skiing", 5.9, None), 0)

    def test_skiing_two_points(self):
        self.assertEqual(compute_base_points("skiing", 6.0, None), 2)
        self.assertEqual(compute_base_points("skiing", 11.9, None), 2)

    def test_skiing_three_points(self):
        self.assertEqual(compute_base_points("skiing", 12.0, None), 3)

    def test_cycling_none_distance(self):
        self.assertEqual(compute_base_points("cycling", None, None), 0)

    def test_cycling_below_threshold(self):
        self.assertEqual(compute_base_points("cycling", 19.9, None), 0)

    def test_cycling_two_points(self):
        self.assertEqual(compute_base_points("cycling", 20.0, None), 2)
        self.assertEqual(compute_base_points("cycling", 39.9, None), 2)

    def test_cycling_three_points(self):
        self.assertEqual(compute_base_points("cycling", 40.0, None), 3)

    def test_swimming_none_distance(self):
        self.assertEqual(compute_base_points("swimming", None, None), 0)

    def test_swimming_below_threshold(self):
        self.assertEqual(compute_base_points("swimming", 0.9, None), 0)

    def test_swimming_two_points(self):
        self.assertEqual(compute_base_points("swimming", 1.0, None), 2)
        self.assertEqual(compute_base_points("swimming", 1.9, None), 2)

    def test_swimming_three_points(self):
        self.assertEqual(compute_base_points("swimming", 2.0, None), 3)

    def test_unknown_activity(self):
        self.assertEqual(compute_base_points("yoga", 10.0, 5.0), 0)


class RecomputeAthleteScoresTests(TestCase):
    def setUp(self):
        self.athlete = Athlete.objects.create(telegram_id="u1", name="Тест")

    def _make_workout(self, date, activity, distance_km=None, pace_min_per_km=None):
        return Workout.objects.create(
            athlete=self.athlete,
            date=date,
            activity=activity,
            distance_km=distance_km,
            pace_min_per_km=pace_min_per_km,
        )

    def test_streak_chain_within_four_days(self):
        d1 = datetime.date(2026, 1, 1)
        d2 = datetime.date(2026, 1, 4)  # gap = 3 days
        d3 = datetime.date(2026, 1, 8)  # gap = 4 days
        w1 = self._make_workout(d1, "skiing", distance_km=8.0)
        w2 = self._make_workout(d2, "skiing", distance_km=8.0)
        w3 = self._make_workout(d3, "skiing", distance_km=8.0)

        recompute_athlete_scores(self.athlete)

        w1.refresh_from_db()
        w2.refresh_from_db()
        w3.refresh_from_db()

        self.assertEqual(w1.base_points, 2)
        self.assertEqual(w1.streak_bonus, 0)
        self.assertEqual(w1.total_points, 2)

        self.assertEqual(w2.base_points, 2)
        self.assertEqual(w2.streak_bonus, 1)
        self.assertEqual(w2.total_points, 3)

        self.assertEqual(w3.base_points, 2)
        self.assertEqual(w3.streak_bonus, 1)
        self.assertEqual(w3.total_points, 3)

    def test_gap_over_four_days_resets_bonus(self):
        d1 = datetime.date(2026, 1, 1)
        d2 = datetime.date(2026, 1, 6)  # gap = 5 days → no bonus
        w1 = self._make_workout(d1, "skiing", distance_km=8.0)
        w2 = self._make_workout(d2, "skiing", distance_km=8.0)

        recompute_athlete_scores(self.athlete)

        w1.refresh_from_db()
        w2.refresh_from_db()

        self.assertEqual(w1.streak_bonus, 0)
        self.assertEqual(w2.streak_bonus, 0)
        self.assertEqual(w2.total_points, 2)

    def test_zero_point_workout_does_not_count_for_streak(self):
        # A zero-point workout in the middle should not continue the streak chain.
        d1 = datetime.date(2026, 1, 1)
        d2 = datetime.date(2026, 1, 3)  # zero-point (distance too short)
        d3 = datetime.date(2026, 1, 5)  # gap from d1 = 4 days → still gets bonus
        w1 = self._make_workout(d1, "skiing", distance_km=8.0)
        w2 = self._make_workout(d2, "skiing", distance_km=1.0)  # < 6 km → 0 pts
        w3 = self._make_workout(d3, "skiing", distance_km=8.0)

        recompute_athlete_scores(self.athlete)

        w1.refresh_from_db()
        w2.refresh_from_db()
        w3.refresh_from_db()

        self.assertEqual(w2.base_points, 0)
        self.assertEqual(w2.streak_bonus, 0)
        # w3 gap from last qualifying (w1, Jan 1) = 4 days → streak
        self.assertEqual(w3.streak_bonus, 1)

    def test_no_workouts(self):
        # Should not raise with empty workout list.
        recompute_athlete_scores(self.athlete)

    def test_single_workout_no_streak(self):
        w = self._make_workout(datetime.date(2026, 1, 1), "hiking")
        recompute_athlete_scores(self.athlete)
        w.refresh_from_db()
        self.assertEqual(w.base_points, 2)
        self.assertEqual(w.streak_bonus, 0)
        self.assertEqual(w.total_points, 2)

    def test_recompute_updates_existing_wrong_values(self):
        # Simulate stale DB values that need correction.
        w = Workout.objects.create(
            athlete=self.athlete,
            date=datetime.date(2026, 1, 1),
            activity="cycling",
            distance_km=50.0,
            base_points=0,
            streak_bonus=99,
            total_points=99,
        )
        recompute_athlete_scores(self.athlete)
        w.refresh_from_db()
        self.assertEqual(w.base_points, 3)
        self.assertEqual(w.streak_bonus, 0)
        self.assertEqual(w.total_points, 3)
