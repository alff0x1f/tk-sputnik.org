import html
from datetime import UTC, datetime

from django.core.management.base import BaseCommand
from django.db import connections

from apps.forum.models import SubForum, Topic

TOPICS_TABLE = "vu2_topics"


class Command(BaseCommand):
    help = "Import topics from phpBB MySQL database"

    def handle(self, *args, **options):
        cursor = connections["phpbb"].cursor()
        cursor.execute(
            f"SELECT topic_id, forum_id, topic_title, topic_time,"  # noqa: S608
            f" topic_views, topic_replies"
            f" FROM {TOPICS_TABLE}"
        )
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        total = len(rows)
        imported = 0
        skipped = 0

        self.stdout.write(f"Importing {total} topics...")

        for i, row in enumerate(rows, start=1):
            try:
                subforum = SubForum.objects.get(id=row["forum_id"])
            except SubForum.DoesNotExist:
                self.stderr.write(
                    f"SubForum phpbb_id={row['forum_id']} not found"
                    f" for topic {row['topic_id']}, skipping"
                )
                skipped += 1
                continue

            Topic.objects.update_or_create(
                id=row["topic_id"],
                defaults={
                    "phpbb_id": row["topic_id"],
                    "subforum": subforum,
                    "title": html.unescape(row["topic_title"] or ""),
                    "created_at": _unix_to_dt(row["topic_time"]),
                    "views": row["topic_views"],
                    "post_count": row["topic_replies"] + 1,
                },
            )
            imported += 1

            if i % 100 == 0 or i == total:
                self.stdout.write(f"\r  {i}/{total}", ending="")
                self.stdout.flush()

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Imported {imported} topics ({skipped} skipped)")
        )


def _unix_to_dt(ts):
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=UTC)
