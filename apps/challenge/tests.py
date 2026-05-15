import datetime

from django.test import TestCase

from .models import Athlete, SourceMessage, Workout


class AthleteModelTests(TestCase):
    def test_create_and_str(self):
        athlete = Athlete.objects.create(telegram_id="u123", name="Иван Иванов")
        self.assertEqual(str(athlete), "Иван Иванов")
        self.assertEqual(Athlete.objects.count(), 1)

    def test_primary_key_is_telegram_id(self):
        athlete = Athlete.objects.create(telegram_id="u999", name="Петр")
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
