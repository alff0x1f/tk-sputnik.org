from datetime import UTC, datetime

from django.core.management.base import BaseCommand
from django.db import connections

from apps.forum.models import ForumCategory, SubForum

FORUM_TABLE = "vu2_forums"


class Command(BaseCommand):
    help = "Import forum categories and subforums from phpBB MySQL database"

    def handle(self, *args, **options):
        cursor = connections["phpbb"].cursor()
        cursor.execute(
            f"SELECT forum_id, parent_id, forum_type, forum_name, forum_desc,"  # noqa: S608
            f" forum_topics, forum_posts, forum_last_post_subject,"
            f" forum_last_poster_name, forum_last_post_time, left_id"
            f" FROM {FORUM_TABLE}"
        )
        columns = [col[0] for col in cursor.description]
        rows = {row[0]: dict(zip(columns, row)) for row in cursor.fetchall()}

        cat_count = 0
        sub_count = 0

        for forum_id, row in rows.items():
            if row["forum_type"] != 0:
                continue
            last_post_at = _unix_to_dt(row["forum_last_post_time"])
            ForumCategory.objects.update_or_create(
                phpbb_id=forum_id,
                defaults={
                    "name": row["forum_name"],
                    "description": row["forum_desc"] or "",
                    "topic_count": row["forum_topics"],
                    "post_count": row["forum_posts"],
                    "last_post_title": row["forum_last_post_subject"] or "",
                    "last_post_username": row["forum_last_poster_name"] or "",
                    "last_post_at": last_post_at,
                    "sort_order": row["left_id"],
                },
            )
            cat_count += 1

        for forum_id, row in rows.items():
            if row["forum_type"] != 1:
                continue
            root_cat_id = _find_root_category(forum_id, rows)
            if root_cat_id is None:
                self.stderr.write(f"No root category for subforum {forum_id}, skipping")
                continue
            try:
                category = ForumCategory.objects.get(phpbb_id=root_cat_id)
            except ForumCategory.DoesNotExist:
                self.stderr.write(
                    f"Category phpbb_id={root_cat_id} not found"
                    f" for subforum {forum_id}, skipping"
                )
                continue
            last_post_at = _unix_to_dt(row["forum_last_post_time"])
            SubForum.objects.update_or_create(
                phpbb_id=forum_id,
                defaults={
                    "phpbb_parent_id": row["parent_id"],
                    "category": category,
                    "name": row["forum_name"],
                    "description": row["forum_desc"] or "",
                    "topic_count": row["forum_topics"],
                    "post_count": row["forum_posts"],
                    "last_post_title": row["forum_last_post_subject"] or "",
                    "last_post_username": row["forum_last_poster_name"] or "",
                    "last_post_at": last_post_at,
                    "sort_order": row["left_id"],
                },
            )
            sub_count += 1

        self.stdout.write(f"Imported {cat_count} categories, {sub_count} subforums")


def _unix_to_dt(ts):
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=UTC)


def _find_root_category(forum_id, rows, _visited=None):
    if _visited is None:
        _visited = set()
    if forum_id in _visited:
        return None
    _visited.add(forum_id)
    row = rows.get(forum_id)
    if row is None:
        return None
    if row["forum_type"] == 0:
        return forum_id
    parent_id = row["parent_id"]
    if parent_id == 0 or parent_id not in rows:
        return None
    return _find_root_category(parent_id, rows, _visited)
