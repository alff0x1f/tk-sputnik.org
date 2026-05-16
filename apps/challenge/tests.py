import datetime
import json
import tempfile
from pathlib import Path

from django.core.management import call_command
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


FIXTURE_SCORES = {
    "generated_at": "2026-01-01T00:00:00",
    "challenge_start": "2025-12-01",
    "challenge_end": "2026-03-31",
    "athletes": [
        {
            "id": "user111",
            "name": "Анна",
            "total_points": 5,
            "workout_count": 2,
            "workouts": [
                {
                    "date": "2025-12-01",
                    "activity": "running",
                    "distance_km": 7.0,
                    "pace_min_per_km": 6.0,
                    "base_points": 2,
                    "streak_bonus": 0,
                    "total_points": 2,
                    "msg_id": 1001,
                },
                {
                    "date": "2025-12-03",
                    "activity": "skiing",
                    "distance_km": 10.0,
                    "pace_min_per_km": None,
                    "base_points": 2,
                    "streak_bonus": 1,
                    "total_points": 3,
                    "msg_id": 1002,
                },
            ],
        },
        {
            "id": "user222",
            "name": "Борис",
            "total_points": 2,
            "workout_count": 1,
            "workouts": [
                {
                    "date": "2025-12-05",
                    "activity": "cycling",
                    "distance_km": 25.0,
                    "pace_min_per_km": None,
                    "base_points": 2,
                    "streak_bonus": 0,
                    "total_points": 2,
                    "msg_id": None,
                },
            ],
        },
    ],
}

FIXTURE_MESSAGES = {
    "messages": [
        {
            "id": 1001,
            "type": "message",
            "date": "2025-12-01T14:03:55",
            "date_unixtime": "1764608635",
            "from": "Анна",
            "from_id": "user111",
            "photo": "photos/photo_001.jpg",
            "text": "Бег 7 км",
        },
        {
            "id": 1002,
            "type": "message",
            "date": "2025-12-03T14:03:55",
            "date_unixtime": "1764781435",
            "from": "Анна",
            "from_id": "user111",
            "text": "",
        },
    ]
}


class ImportChallengeCommandTests(TestCase):
    def _write_fixtures(self, tmpdir, scores=None, messages=None):
        scores_path = Path(tmpdir) / "scores.json"
        export_path = Path(tmpdir) / "result.json"
        scores_path.write_text(
            json.dumps(scores if scores is not None else FIXTURE_SCORES),
            encoding="utf-8",
        )
        export_path.write_text(
            json.dumps(messages if messages is not None else FIXTURE_MESSAGES),
            encoding="utf-8",
        )
        return str(scores_path), str(export_path)

    def test_basic_import(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scores_path, messages_path = self._write_fixtures(tmpdir)
            call_command(
                "import_challenge",
                "--scores",
                scores_path,
                "--telegram-export",
                messages_path,
                stdout=open("/dev/null", "w"),
            )

        self.assertEqual(Athlete.objects.count(), 2)
        self.assertEqual(Workout.objects.count(), 3)
        self.assertEqual(SourceMessage.objects.count(), 2)

        anna = Athlete.objects.get(telegram_id="user111")
        self.assertEqual(anna.name, "Анна")
        self.assertEqual(anna.workouts.count(), 2)

    def test_athletes_and_workouts_upserted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scores_path, messages_path = self._write_fixtures(tmpdir)
            call_command(
                "import_challenge",
                "--scores",
                scores_path,
                "--telegram-export",
                messages_path,
                stdout=open("/dev/null", "w"),
            )

        w = Workout.objects.get(
            athlete__telegram_id="user111", date="2025-12-01", activity="running"
        )
        self.assertEqual(w.distance_km, 7.0)
        self.assertEqual(w.msg_id, 1001)

    def test_source_messages_photos_normalized(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scores_path, messages_path = self._write_fixtures(tmpdir)
            call_command(
                "import_challenge",
                "--scores",
                scores_path,
                "--telegram-export",
                messages_path,
                stdout=open("/dev/null", "w"),
            )

        msg1 = SourceMessage.objects.get(pk=1001)
        self.assertEqual(msg1.photos, ["photos/photo_001.jpg"])
        self.assertEqual(msg1.from_name, "Анна")

        msg2 = SourceMessage.objects.get(pk=1002)
        self.assertEqual(msg2.photos, [])

    def test_idempotent_second_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scores_path, messages_path = self._write_fixtures(tmpdir)
            devnull = open("/dev/null", "w")
            call_command(
                "import_challenge",
                "--scores",
                scores_path,
                "--telegram-export",
                messages_path,
                stdout=devnull,
            )
            call_command(
                "import_challenge",
                "--scores",
                scores_path,
                "--telegram-export",
                messages_path,
                stdout=devnull,
            )

        self.assertEqual(Athlete.objects.count(), 2)
        self.assertEqual(Workout.objects.count(), 3)
        self.assertEqual(SourceMessage.objects.count(), 2)

    def test_missing_scores_file_continues(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _, messages_path = self._write_fixtures(tmpdir)
            import io

            out = io.StringIO()
            call_command(
                "import_challenge",
                "--scores",
                "/nonexistent/scores.json",
                "--telegram-export",
                messages_path,
                stdout=out,
            )

        self.assertEqual(Athlete.objects.count(), 0)
        self.assertEqual(Workout.objects.count(), 0)
        self.assertEqual(SourceMessage.objects.count(), 2)

    def test_missing_messages_file_continues(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scores_path, _ = self._write_fixtures(tmpdir)
            import io

            out = io.StringIO()
            call_command(
                "import_challenge",
                "--scores",
                scores_path,
                "--telegram-export",
                "/nonexistent/result.json",
                stdout=out,
            )

        self.assertEqual(Athlete.objects.count(), 2)
        self.assertEqual(Workout.objects.count(), 3)
        self.assertEqual(SourceMessage.objects.count(), 0)

    def test_scores_recomputed_after_import(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scores_path, messages_path = self._write_fixtures(tmpdir)
            call_command(
                "import_challenge",
                "--scores",
                scores_path,
                "--telegram-export",
                messages_path,
                stdout=open("/dev/null", "w"),
            )

        # Anna's second workout (skiing, Dec 3) should have streak_bonus=1 (gap=2 days)
        w2 = Workout.objects.get(
            athlete__telegram_id="user111", date="2025-12-03", activity="skiing"
        )
        self.assertEqual(w2.streak_bonus, 1)
        self.assertEqual(w2.total_points, 3)

    def test_summary_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scores_path, messages_path = self._write_fixtures(tmpdir)
            import io

            out = io.StringIO()
            call_command(
                "import_challenge",
                "--scores",
                scores_path,
                "--telegram-export",
                messages_path,
                stdout=out,
            )

        output = out.getvalue()
        self.assertIn("2 athletes", output)
        self.assertIn("3 workouts", output)
        self.assertIn("2 messages", output)


class PhotoViewTests(TestCase):
    def test_valid_photo_returns_200(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            photo = Path(tmpdir) / "photo_001.jpg"
            photo.write_bytes(b"FAKEJPEG")
            with self.settings(CHALLENGE_CHAT_EXPORT_DIR=tmpdir):
                response = self.client.get("/challenge/photo/photo_001.jpg")
        self.assertEqual(response.status_code, 200)

    def test_missing_photo_returns_404(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.settings(CHALLENGE_CHAT_EXPORT_DIR=tmpdir):
                response = self.client.get("/challenge/photo/nonexistent.jpg")
        self.assertEqual(response.status_code, 404)

    def test_path_traversal_returns_404(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.settings(CHALLENGE_CHAT_EXPORT_DIR=tmpdir):
                response = self.client.get("/challenge/photo/../../etc/passwd")
        self.assertEqual(response.status_code, 404)

    def test_nested_path_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "photos"
            subdir.mkdir()
            photo = subdir / "img.jpg"
            photo.write_bytes(b"FAKEJPEG")
            with self.settings(CHALLENGE_CHAT_EXPORT_DIR=tmpdir):
                response = self.client.get("/challenge/photo/photos/img.jpg")
        self.assertEqual(response.status_code, 200)


class ReviewViewTests(TestCase):
    def setUp(self):
        self.athlete = Athlete.objects.create(telegram_id="u1", name="Анна")
        self.msg = SourceMessage.objects.create(
            msg_id=1001,
            from_name="Анна",
            date=datetime.date(2026, 1, 1),
            text="Пробежала 10 км",
            photos=["photos/img1.jpg"],
        )
        Workout.objects.create(
            athlete=self.athlete,
            date=datetime.date(2026, 1, 1),
            activity="running",
            distance_km=10.0,
            pace_min_per_km=5.0,
            base_points=3,
            streak_bonus=0,
            total_points=3,
            msg_id=1001,
        )
        self.staff = self._make_staff()

    def _make_staff(self):
        from django.contrib.auth.models import User

        return User.objects.create_user(
            username="admin", password="password", is_staff=True
        )

    def _make_regular_user(self):
        from django.contrib.auth.models import User

        return User.objects.create_user(
            username="regular", password="password", is_staff=False
        )

    def test_non_staff_redirected(self):
        response = self.client.get("/challenge/review/")
        self.assertIn(response.status_code, [302, 301])

    def test_regular_user_redirected(self):
        self._make_regular_user()
        self.client.login(username="regular", password="password")
        response = self.client.get("/challenge/review/")
        self.assertIn(response.status_code, [302, 301])

    def test_staff_can_access(self):
        self.client.login(username="admin", password="password")
        response = self.client.get("/challenge/review/")
        self.assertEqual(response.status_code, 200)

    def test_cards_json_in_response(self):
        self.client.login(username="admin", password="password")
        response = self.client.get("/challenge/review/")
        self.assertIn(b"CARDS", response.content)
        self.assertIn(b"1001", response.content)

    def test_athletes_json_in_response(self):
        self.client.login(username="admin", password="password")
        response = self.client.get("/challenge/review/")
        self.assertIn(b"ATHLETES", response.content)
        self.assertIn(b"u1", response.content)

    def test_cards_json_contains_workout(self):
        self.client.login(username="admin", password="password")
        response = self.client.get("/challenge/review/")
        content = response.content.decode("utf-8")
        self.assertIn("running", content)
        self.assertIn("Анна", content)  # "Анна"

    def test_cards_json_contains_photo(self):
        self.client.login(username="admin", password="password")
        response = self.client.get("/challenge/review/")
        content = response.content.decode("utf-8")
        self.assertIn("photos/img1.jpg", content)

    def test_message_without_workouts_included(self):
        SourceMessage.objects.create(
            msg_id=2000,
            from_name="Борис",
            date=datetime.date(2026, 1, 2),
            text="",
        )
        self.client.login(username="admin", password="password")
        response = self.client.get("/challenge/review/")
        content = response.content.decode("utf-8")
        self.assertIn("2000", content)


class ReviewAPITests(TestCase):
    def setUp(self):
        self.athlete = Athlete.objects.create(telegram_id="u1", name="Анна")
        self.workout = Workout.objects.create(
            athlete=self.athlete,
            date=datetime.date(2026, 1, 1),
            activity="running",
            distance_km=10.0,
            pace_min_per_km=5.0,
            base_points=3,
            streak_bonus=0,
            total_points=3,
            msg_id=1001,
        )
        from django.contrib.auth.models import User

        self.staff = User.objects.create_user(
            username="admin", password="password", is_staff=True
        )
        self.regular = User.objects.create_user(
            username="regular", password="password", is_staff=False
        )

    def _post(self, data, user=None):
        if user:
            self.client.force_login(user)
        return self.client.post(
            "/challenge/review/api/workout/",
            data=json.dumps(data),
            content_type="application/json",
        )

    def _put(self, pk, data, user=None):
        if user:
            self.client.force_login(user)
        return self.client.put(
            f"/challenge/review/api/workout/{pk}/",
            data=json.dumps(data),
            content_type="application/json",
        )

    def _delete(self, pk, user=None):
        if user:
            self.client.force_login(user)
        return self.client.delete(f"/challenge/review/api/workout/{pk}/")

    # Auth checks

    def test_create_unauthenticated_redirects(self):
        resp = self._post(
            {"athlete_id": "u1", "date": "2026-01-10", "activity": "hiking"}
        )
        self.assertIn(resp.status_code, [301, 302])

    def test_create_non_staff_redirects(self):
        resp = self._post(
            {"athlete_id": "u1", "date": "2026-01-10", "activity": "hiking"},
            user=self.regular,
        )
        self.assertIn(resp.status_code, [301, 302])

    def test_update_unauthenticated_redirects(self):
        resp = self._put(self.workout.pk, {"distance_km": 12.0})
        self.assertIn(resp.status_code, [301, 302])

    def test_update_non_staff_redirects(self):
        resp = self._put(self.workout.pk, {"distance_km": 12.0}, user=self.regular)
        self.assertIn(resp.status_code, [301, 302])

    def test_delete_unauthenticated_redirects(self):
        resp = self._delete(self.workout.pk)
        self.assertIn(resp.status_code, [301, 302])

    def test_delete_non_staff_redirects(self):
        resp = self._delete(self.workout.pk, user=self.regular)
        self.assertIn(resp.status_code, [301, 302])

    # Create

    def test_create_workout_success(self):
        resp = self._post(
            {"athlete_id": "u1", "date": "2026-01-10", "activity": "hiking"},
            user=self.staff,
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Workout.objects.count(), 2)
        data = json.loads(resp.content)
        self.assertIn("workout", data)
        self.assertIn("athlete_total", data)

    def test_create_workout_recomputes_scores(self):
        resp = self._post(
            {
                "athlete_id": "u1",
                "date": "2026-01-05",
                "activity": "skiing",
                "distance_km": 8.0,
            },
            user=self.staff,
        )
        self.assertEqual(resp.status_code, 201)
        new_id = json.loads(resp.content)["workout"]["id"]
        new_w = Workout.objects.get(pk=new_id)
        # Gap from Jan 1 to Jan 5 is 4 days → streak bonus
        self.assertEqual(new_w.streak_bonus, 1)

    def test_create_invalid_json_returns_400(self):
        self.client.force_login(self.staff)
        resp = self.client.post(
            "/challenge/review/api/workout/",
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_invalid_activity_returns_400(self):
        resp = self._post(
            {"athlete_id": "u1", "date": "2026-01-10", "activity": "yoga"},
            user=self.staff,
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_unknown_athlete_returns_400(self):
        resp = self._post(
            {"athlete_id": "no_such_id", "date": "2026-01-10", "activity": "hiking"},
            user=self.staff,
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_invalid_date_returns_400(self):
        resp = self._post(
            {"athlete_id": "u1", "date": "not-a-date", "activity": "hiking"},
            user=self.staff,
        )
        self.assertEqual(resp.status_code, 400)

    # Update

    def test_update_workout_success(self):
        resp = self._put(self.workout.pk, {"distance_km": 15.0}, user=self.staff)
        self.assertEqual(resp.status_code, 200)
        self.workout.refresh_from_db()
        self.assertEqual(self.workout.distance_km, 15.0)

    def test_update_workout_recomputes(self):
        resp = self._put(
            self.workout.pk,
            {"activity": "hiking", "distance_km": None},
            user=self.staff,
        )
        self.assertEqual(resp.status_code, 200)
        self.workout.refresh_from_db()
        self.assertEqual(self.workout.activity, "hiking")
        self.assertEqual(self.workout.base_points, 2)

    def test_update_invalid_json_returns_400(self):
        self.client.force_login(self.staff)
        resp = self.client.put(
            f"/challenge/review/api/workout/{self.workout.pk}/",
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_update_not_found_returns_404(self):
        resp = self._put(99999, {"distance_km": 5.0}, user=self.staff)
        self.assertEqual(resp.status_code, 404)

    def test_update_athlete_changes_athlete(self):
        Athlete.objects.create(telegram_id="u2", name="Борис")
        resp = self._put(self.workout.pk, {"athlete_id": "u2"}, user=self.staff)
        self.assertEqual(resp.status_code, 200)
        self.workout.refresh_from_db()
        self.assertEqual(self.workout.athlete_id, "u2")

    def test_update_invalid_athlete_returns_400(self):
        resp = self._put(self.workout.pk, {"athlete_id": "no_such_id"}, user=self.staff)
        self.assertEqual(resp.status_code, 400)

    def test_update_returns_athlete_total(self):
        resp = self._put(self.workout.pk, {"distance_km": 15.0}, user=self.staff)
        data = json.loads(resp.content)
        self.assertIn("athlete_total", data)

    # Delete

    def test_delete_workout_success(self):
        resp = self._delete(self.workout.pk, user=self.staff)
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(Workout.objects.count(), 0)

    def test_delete_workout_recomputes(self):
        # Add a second workout that would get streak bonus from the first
        w2 = Workout.objects.create(
            athlete=self.athlete,
            date=datetime.date(2026, 1, 4),
            activity="skiing",
            distance_km=8.0,
            base_points=2,
            streak_bonus=1,
            total_points=3,
        )
        # Delete the first workout — w2 should lose its streak bonus
        resp = self._delete(self.workout.pk, user=self.staff)
        self.assertEqual(resp.status_code, 204)
        w2.refresh_from_db()
        self.assertEqual(w2.streak_bonus, 0)

    def test_delete_not_found_returns_404(self):
        resp = self._delete(99999, user=self.staff)
        self.assertEqual(resp.status_code, 404)


class MemberDetailViewTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        self.athlete = Athlete.objects.create(telegram_id="u1", name="Анна")
        self.other_athlete = Athlete.objects.create(telegram_id="u2", name="Борис")

        self.msg_with_workout = SourceMessage.objects.create(
            msg_id=1001,
            from_name="Анна",
            date=datetime.date(2026, 1, 10),
            text="Пробежала 10 км",
            photos=[],
        )
        self.msg_plain = SourceMessage.objects.create(
            msg_id=1002,
            from_name="Анна",
            date=datetime.date(2026, 1, 11),
            text="Просто сообщение",
            photos=[],
        )
        self.msg_other = SourceMessage.objects.create(
            msg_id=1003,
            from_name="Борис",
            date=datetime.date(2026, 1, 10),
            text="Борис бежит",
            photos=[],
        )

        self.workout = Workout.objects.create(
            athlete=self.athlete,
            date=datetime.date(2026, 1, 10),
            activity="running",
            distance_km=10.0,
            pace_min_per_km=5.0,
            base_points=3,
            streak_bonus=0,
            total_points=3,
            msg_id=1001,
        )

        self.staff = User.objects.create_user(
            username="admin", password="password", is_staff=True
        )
        self.regular = User.objects.create_user(
            username="regular", password="password", is_staff=False
        )

    def _url(self, telegram_id="u1"):
        return f"/challenge/member/{telegram_id}/"

    def test_anonymous_redirected(self):
        response = self.client.get(self._url())
        self.assertIn(response.status_code, [301, 302])

    def test_non_staff_redirected(self):
        self.client.login(username="regular", password="password")
        response = self.client.get(self._url())
        self.assertIn(response.status_code, [301, 302])

    def test_staff_gets_200(self):
        self.client.login(username="admin", password="password")
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    def test_unknown_telegram_id_returns_404(self):
        self.client.login(username="admin", password="password")
        response = self.client.get(self._url("no_such_id"))
        self.assertEqual(response.status_code, 404)

    def test_only_athlete_messages_shown(self):
        self.client.login(username="admin", password="password")
        response = self.client.get(self._url())
        content = response.content.decode("utf-8")
        self.assertIn("Пробежала 10 км", content)
        self.assertIn("Просто сообщение", content)
        self.assertNotIn("Борис бежит", content)

    def test_message_with_workout_has_workout_card(self):
        self.client.login(username="admin", password="password")
        response = self.client.get(self._url())
        content = response.content.decode("utf-8")
        self.assertIn("has-workout", content)
        self.assertIn("Бег", content)
        self.assertIn("= 3 очков", content)

    def test_message_without_workout_no_workout_card(self):
        self.client.login(username="admin", password="password")
        response = self.client.get(self._url())
        content = response.content.decode("utf-8")
        # Only msg 1001 has a workout — exactly one has-workout bubble and one info card
        self.assertEqual(content.count("has-workout"), 1)
        self.assertEqual(content.count("wic-header"), 1)

    def test_athlete_stats_in_response(self):
        self.client.login(username="admin", password="password")
        response = self.client.get(self._url())
        content = response.content.decode("utf-8")
        self.assertIn("Анна", content)
        self.assertIn("3 очков", content)
        self.assertIn("1 активностей", content)

    def test_workout_card_has_edit_button(self):
        self.client.login(username="admin", password="password")
        response = self.client.get(self._url())
        content = response.content.decode("utf-8")
        self.assertIn(f"editWorkout({self.workout.pk})", content)
        self.assertIn(f"deleteWorkout({self.workout.pk})", content)

    def test_workout_card_buttons_absent_without_workout(self):
        self.client.login(username="admin", password="password")
        response = self.client.get(self._url())
        content = response.content.decode("utf-8")
        # msg_plain has no workout — only the one workout bubble should have buttons
        self.assertEqual(content.count("wic-btn-edit"), 1)
        self.assertEqual(content.count("wic-btn-delete"), 1)


class LeaderboardViewTests(TestCase):
    def setUp(self):
        self.anna = Athlete.objects.create(telegram_id="u1", name="Анна")
        self.boris = Athlete.objects.create(telegram_id="u2", name="Борис")
        self.vova = Athlete.objects.create(telegram_id="u3", name="Вова")

        Workout.objects.create(
            athlete=self.anna,
            date=datetime.date(2026, 1, 1),
            activity="running",
            distance_km=10.0,
            pace_min_per_km=5.0,
            base_points=3,
            streak_bonus=0,
            total_points=3,
        )
        Workout.objects.create(
            athlete=self.anna,
            date=datetime.date(2026, 1, 5),
            activity="skiing",
            distance_km=8.0,
            base_points=2,
            streak_bonus=1,
            total_points=3,
        )
        Workout.objects.create(
            athlete=self.boris,
            date=datetime.date(2026, 1, 2),
            activity="cycling",
            distance_km=25.0,
            base_points=2,
            streak_bonus=0,
            total_points=2,
        )
        # Vova has no workouts → score 0

    def test_leaderboard_returns_200(self):
        response = self.client.get("/challenge/")
        self.assertEqual(response.status_code, 200)

    def test_leaderboard_athletes_in_context(self):
        response = self.client.get("/challenge/")
        athletes = response.context["athletes"]
        self.assertEqual(len(athletes), 3)

    def test_leaderboard_ranking_order(self):
        response = self.client.get("/challenge/")
        athletes = response.context["athletes"]
        scores = [a.total_score for a in athletes]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_leaderboard_top_is_anna(self):
        response = self.client.get("/challenge/")
        athletes = response.context["athletes"]
        self.assertEqual(athletes[0].name, "Анна")
        self.assertEqual(athletes[0].total_score, 6)
        self.assertEqual(athletes[0].rank, 1)

    def test_leaderboard_boris_second(self):
        response = self.client.get("/challenge/")
        athletes = response.context["athletes"]
        self.assertEqual(athletes[1].name, "Борис")
        self.assertEqual(athletes[1].total_score, 2)
        self.assertEqual(athletes[1].rank, 2)

    def test_leaderboard_zero_score_athlete_last(self):
        response = self.client.get("/challenge/")
        athletes = response.context["athletes"]
        last = athletes[-1]
        self.assertEqual(last.name, "Вова")
        self.assertEqual(last.total_score, 0)

    def test_leaderboard_athlete_has_workout_list(self):
        response = self.client.get("/challenge/")
        athletes = response.context["athletes"]
        anna = next(a for a in athletes if a.name == "Анна")
        self.assertEqual(len(anna.workout_list), 2)

    def test_leaderboard_no_athletes(self):
        Workout.objects.all().delete()
        Athlete.objects.all().delete()
        response = self.client.get("/challenge/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["athletes"]), 0)
