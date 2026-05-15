from django.core.management.base import BaseCommand
from django.db import connection

_TABLES = [
    "forum_forumcategory",
    "forum_subforum",
    "forum_forumuser",
    "forum_topic",
    "forum_post",
]


class Command(BaseCommand):
    help = "Reset PostgreSQL sequences for forum tables after import with explicit IDs"

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            self.stdout.write("Skipping: not a PostgreSQL database")
            return
        with connection.cursor() as cursor:
            for table in _TABLES:
                cursor.execute(f"SELECT MAX(id) FROM {table}")  # noqa: S608
                max_id = cursor.fetchone()[0]
                if max_id is not None:
                    cursor.execute(
                        "SELECT setval(pg_get_serial_sequence(%s, %s), %s)",
                        [table, "id", max_id],
                    )
                    self.stdout.write(f"  {table}: seq → {max_id}")
                else:
                    self.stdout.write(f"  {table}: empty, skipped")
        self.stdout.write(self.style.SUCCESS("Done"))
