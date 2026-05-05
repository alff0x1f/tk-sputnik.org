import json
import os
import urllib.request
from urllib.error import URLError

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.contributors.models import ClubMember, DonationPeriod, MemberDonation


class Command(BaseCommand):
    help = "Sync contributors data from kolco24 API"

    def handle(self, *args, **options):
        api_url = os.environ.get("KOLCO24_API_URL")
        if not api_url:
            raise CommandError("KOLCO24_API_URL environment variable is not set")

        api_token = os.environ.get("KOLCO24_API_TOKEN")
        if not api_token:
            raise CommandError("KOLCO24_API_TOKEN environment variable is not set")

        request = urllib.request.Request(
            api_url,
            headers={"Authorization": f"Bearer {api_token}"},
        )

        try:
            with urllib.request.urlopen(request) as response:
                data = json.loads(response.read().decode())
        except URLError as e:
            raise CommandError(f"Failed to fetch data from API: {e}") from e
        except json.JSONDecodeError as e:
            raise CommandError(f"Failed to parse API response as JSON: {e}") from e

        with transaction.atomic():
            period_map = {}
            for p in data.get("periods", []):
                obj, _ = DonationPeriod.objects.update_or_create(
                    external_id=p["id"],
                    defaults={
                        "name": p["name"],
                        "date": p["date"],
                        "is_active": p["is_active"],
                    },
                )
                period_map[p["id"]] = obj

            member_map = {}
            for m in data.get("members", []):
                obj, _ = ClubMember.objects.update_or_create(
                    external_id=m["id"],
                    defaults={
                        "name": m["name"],
                        "label": m.get("label", ""),
                    },
                )
                member_map[m["id"]] = obj

            for d in data.get("donations", []):
                member = member_map.get(d["member_id"])
                period = period_map.get(d["period_id"])
                if member is None or period is None:
                    continue
                MemberDonation.objects.update_or_create(
                    member=member,
                    period=period,
                    defaults={
                        "is_paid": d["is_paid"],
                        "amount": d.get("amount"),
                        "paid_date": d.get("paid_date") or None,
                        "recipient": d.get("recipient", ""),
                        "note": d.get("note", ""),
                    },
                )

        self.stdout.write(self.style.SUCCESS("Contributors data synced successfully"))
