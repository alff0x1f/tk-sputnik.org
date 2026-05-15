from datetime import UTC, datetime

from django.core.management.base import BaseCommand
from django.db import connections

from apps.forum.models import ForumUser

USER_TABLE = "vu2_users"


class Command(BaseCommand):
    help = "Import users from phpBB MySQL database"

    def handle(self, *args, **options):
        cursor = connections["phpbb"].cursor()
        cursor.execute(
            f"SELECT user_id, username, user_email, user_avatar, user_avatar_type,"  # noqa: S608
            f" user_regdate, user_posts"
            f" FROM {USER_TABLE}"
            f" WHERE user_id != 1 AND user_type != 2"
        )
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        count = 0
        for row in rows:
            ForumUser.objects.update_or_create(
                id=row["user_id"],
                defaults={
                    "phpbb_id": row["user_id"],
                    "username": row["username"],
                    "email": row["user_email"] or "",
                    "avatar": _avatar(row["user_avatar"]),
                    "registered_at": _unix_to_dt(row["user_regdate"]),
                    "post_count": row["user_posts"],
                },
            )
            count += 1

        self.stdout.write(f"Imported {count} users")


def _avatar(val):
    if not val:
        return ""
    return val


def _unix_to_dt(ts):
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=UTC)
