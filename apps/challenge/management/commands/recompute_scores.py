from django.core.management.base import BaseCommand

from apps.challenge.models import Athlete
from apps.challenge.scoring import recompute_athlete_scores


class Command(BaseCommand):
    help = "Recompute base_points, streak_bonus, and total_points for all athletes"

    def handle(self, *args, **options):
        count = 0
        for athlete in Athlete.objects.all():
            recompute_athlete_scores(athlete)
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Recomputed scores for {count} athletes"))
