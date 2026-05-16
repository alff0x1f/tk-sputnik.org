import datetime
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.challenge.models import Athlete, SourceMessage, Workout
from apps.challenge.scoring import recompute_athlete_scores


def _extract_text(raw):
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        return "".join(
            part if isinstance(part, str) else part.get("text", "")
            for part in raw
        )
    return ""


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
            "--telegram-export",
            default=str(default_base / "ChatExport_2026-04-02" / "result.json"),
            help="Path to Telegram chat export result.json",
        )

    def handle(self, *args, **options):
        scores_path = Path(options["scores"])
        export_path = Path(options["telegram_export"])

        athlete_count = workout_count = message_count = 0

        if not scores_path.exists():
            self.stdout.write(
                self.style.WARNING(f"Scores file not found: {scores_path}, skipping")
            )
        else:
            athlete_count, workout_count = self._import_scores(scores_path)

        if not export_path.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Telegram export not found: {export_path}, skipping"
                )
            )
        else:
            message_count = self._import_messages(export_path)

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

        messages = data.get("messages", data) if isinstance(data, dict) else data

        message_count = 0
        for msg in messages:
            if msg.get("type") != "message":
                continue
            if not msg.get("from_id"):
                continue

            ts = msg.get("date_unixtime")
            msg_datetime = (
                datetime.datetime.fromtimestamp(int(ts), tz=datetime.UTC)
                if ts
                else None
            )
            msg_date = (
                msg_datetime.date()
                if msg_datetime
                else datetime.date.fromisoformat(msg["date"][:10])
            )

            photo = msg.get("photo")
            photos = [photo] if isinstance(photo, str) else []

            SourceMessage.objects.update_or_create(
                msg_id=msg["id"],
                defaults={
                    "from_name": msg.get("from", ""),
                    "date": msg_date,
                    "datetime": msg_datetime,
                    "text": _extract_text(msg.get("text", "")),
                    "photos": photos,
                },
            )
            message_count += 1

        return message_count
