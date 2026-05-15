import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.challenge.models import Athlete, SourceMessage, Workout
from apps.challenge.scoring import recompute_athlete_scores


class Command(BaseCommand):
    help = "Import athletes, workouts, and source messages from JSON files"

    def add_arguments(self, parser):
        default_base = settings.BASE_DIR / "scratch" / "challenge"
        parser.add_argument(
            "--scores",
            default=str(default_base / "scores.json"),
            help="Path to scores.json (default: scratch/challenge/scores.json)",
        )
        parser.add_argument(
            "--messages",
            default=str(default_base / "messages_clean.json"),
            help=(
                "Path to messages_clean.json"
                " (default: scratch/challenge/messages_clean.json)"
            ),
        )

    def handle(self, *args, **options):
        scores_path = Path(options["scores"])
        messages_path = Path(options["messages"])

        athlete_count = workout_count = message_count = 0

        if not scores_path.exists():
            self.stdout.write(
                self.style.WARNING(f"Scores file not found: {scores_path}, skipping")
            )
        else:
            athlete_count, workout_count = self._import_scores(scores_path)

        if not messages_path.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Messages file not found: {messages_path}, skipping"
                )
            )
        else:
            message_count = self._import_messages(messages_path)

        self.stdout.write(
            f"Imported {athlete_count} athletes, {workout_count} workouts,"
            f" {message_count} messages"
        )

    def _import_scores(self, path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        athlete_count = 0
        workout_count = 0

        for athlete_data in data["athletes"]:
            athlete, _ = Athlete.objects.update_or_create(
                telegram_id=athlete_data["id"],
                defaults={"name": athlete_data["name"]},
            )
            athlete_count += 1

            for w in athlete_data["workouts"]:
                Workout.objects.update_or_create(
                    athlete=athlete,
                    date=w["date"],
                    activity=w["activity"],
                    defaults={
                        "distance_km": w.get("distance_km"),
                        "pace_min_per_km": w.get("pace_min_per_km"),
                        "base_points": w.get("base_points", 0),
                        "streak_bonus": w.get("streak_bonus", 0),
                        "total_points": w.get("total_points", 0),
                        "msg_id": w.get("msg_id"),
                    },
                )
                workout_count += 1

            recompute_athlete_scores(athlete)

        return athlete_count, workout_count

    def _import_messages(self, path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        message_count = 0
        for msg in data:
            photo = msg.get("photo")
            photos = [photo] if isinstance(photo, str) else []
            SourceMessage.objects.update_or_create(
                msg_id=msg["msg_id"],
                defaults={
                    "from_name": msg.get("from", ""),
                    "date": msg["date"],
                    "text": msg.get("text", ""),
                    "photos": photos,
                },
            )
            message_count += 1

        return message_count
