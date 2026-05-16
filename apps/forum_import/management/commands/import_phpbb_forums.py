import html
from datetime import UTC, datetime

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import connections

from apps.forum.models import ForumCategory, SubForum

FORUM_TABLE = "vu2_forums"
ACL_GROUPS_TABLE = "vu2_acl_groups"
ACL_OPTIONS_TABLE = "vu2_acl_options"
ACL_ROLES_DATA_TABLE = "vu2_acl_roles_data"
GROUPS_TABLE = "vu2_groups"


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

        private_ids = _fetch_private_forum_ids(cursor)

        cat_count = 0
        sub_count = 0
        private_count = 0

        for forum_id, row in rows.items():
            if row["forum_type"] != 0:
                continue
            last_post_at = _unix_to_dt(row["forum_last_post_time"])
            ForumCategory.objects.update_or_create(
                id=forum_id,
                defaults={
                    "phpbb_id": forum_id,
                    "name": html.unescape(row["forum_name"]),
                    "description": html.unescape(row["forum_desc"] or ""),
                    "topic_count": row["forum_topics"],
                    "post_count": row["forum_posts"],
                    "last_post_title": html.unescape(
                        row["forum_last_post_subject"] or ""
                    ),
                    "last_post_username": html.unescape(
                        row["forum_last_poster_name"] or ""
                    ),
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
                category = ForumCategory.objects.get(id=root_cat_id)
            except ForumCategory.DoesNotExist:
                self.stderr.write(
                    f"Category phpbb_id={root_cat_id} not found"
                    f" for subforum {forum_id}, skipping"
                )
                continue
            last_post_at = _unix_to_dt(row["forum_last_post_time"])

            is_private = forum_id in private_ids
            allowed_group = None
            if is_private:
                group_name = html.unescape(row["forum_name"]).lower()[:150]
                allowed_group, _ = Group.objects.get_or_create(name=group_name)
                private_count += 1

            SubForum.objects.update_or_create(
                id=forum_id,
                defaults={
                    "phpbb_id": forum_id,
                    "phpbb_parent_id": row["parent_id"],
                    "category": category,
                    "name": html.unescape(row["forum_name"]),
                    "description": html.unescape(row["forum_desc"] or ""),
                    "topic_count": row["forum_topics"],
                    "post_count": row["forum_posts"],
                    "last_post_title": html.unescape(
                        row["forum_last_post_subject"] or ""
                    ),
                    "last_post_username": html.unescape(
                        row["forum_last_poster_name"] or ""
                    ),
                    "last_post_at": last_post_at,
                    "sort_order": row["left_id"],
                    "is_private": is_private,
                    "allowed_group": allowed_group,
                },
            )
            sub_count += 1

        self.stdout.write(f"Imported {cat_count} categories, {sub_count} subforums")
        self.stdout.write(f"Marked {private_count} subforums as private")


def _fetch_private_forum_ids(cursor):
    """Return set of forum IDs that guests cannot read but some other group can."""
    # phpBB stores permissions two ways: direct (auth_role_id=0) and role-based
    # (auth_role_id!=0, actual settings in vu2_acl_roles_data). Both must be checked.
    cursor.execute(  # noqa: S608
        f"SELECT ag.forum_id, g.group_name, ag.auth_setting"
        f" FROM {ACL_GROUPS_TABLE} ag"
        f" JOIN {ACL_OPTIONS_TABLE} ao ON ag.auth_option_id = ao.auth_option_id"
        f" JOIN {GROUPS_TABLE} g ON ag.group_id = g.group_id"
        f" WHERE ao.auth_option = 'f_read' AND ag.auth_role_id = 0"
        f" UNION"
        f" SELECT ag.forum_id, g.group_name, rd.auth_setting"
        f" FROM {ACL_GROUPS_TABLE} ag"
        f" JOIN {GROUPS_TABLE} g ON ag.group_id = g.group_id"
        f" JOIN {ACL_ROLES_DATA_TABLE} rd ON ag.auth_role_id = rd.role_id"
        f" JOIN {ACL_OPTIONS_TABLE} ao ON rd.auth_option_id = ao.auth_option_id"
        f" WHERE ao.auth_option = 'f_read' AND ag.auth_role_id != 0"
    )
    forum_acl: dict[int, dict] = {}
    for row in cursor.fetchall():
        forum_id, group_name, auth_setting = row[0], row[1], row[2]
        forum_acl.setdefault(forum_id, {})[group_name] = auth_setting

    private: set[int] = set()
    for forum_id, group_settings in forum_acl.items():
        if group_settings.get("GUESTS", 0) != 1:
            if any(s == 1 for g, s in group_settings.items() if g != "GUESTS"):
                private.add(forum_id)
    return private


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
