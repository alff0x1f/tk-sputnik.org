import html
import re
from datetime import UTC, datetime

import bbcode
from django.core.management.base import BaseCommand
from django.db import connections

from apps.forum.models import ForumUser, Post, Topic

POSTS_TABLE = "vu2_posts"

_parser = bbcode.Parser()


def _to_html(raw: str, uid: str) -> str:
    text = html.unescape(raw or "")
    if uid:
        text = re.sub(rf"\[([^\[\]:]+):{re.escape(uid)}\]", r"[\1]", text)
        text = re.sub(rf"\[/([^\[\]:]+):{re.escape(uid)}\]", r"[/\1]", text)
    return _parser.format(text)


def _unix_to_dt(ts):
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=UTC)


class Command(BaseCommand):
    help = "Import posts from phpBB MySQL database"

    def handle(self, *args, **options):
        cursor = connections["phpbb"].cursor()
        cursor.execute(
            f"SELECT post_id, topic_id, poster_id, post_username,"  # noqa: S608
            f" post_text, bbcode_uid, post_time"
            f" FROM {POSTS_TABLE} ORDER BY post_id"
        )
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        imported = 0
        skipped = 0

        for row in rows:
            try:
                topic = Topic.objects.get(phpbb_id=row["topic_id"])
            except Topic.DoesNotExist:
                self.stderr.write(
                    f"Topic phpbb_id={row['topic_id']} not found"
                    f" for post {row['post_id']}, skipping"
                )
                skipped += 1
                continue

            try:
                author = ForumUser.objects.get(phpbb_id=row["poster_id"])
            except ForumUser.DoesNotExist:
                author = None

            raw_text = row["post_text"] or ""
            uid = row["bbcode_uid"] or ""

            Post.objects.update_or_create(
                phpbb_id=row["post_id"],
                defaults={
                    "topic": topic,
                    "author": author,
                    "author_username": row["post_username"] or "",
                    "text_bbcode": raw_text,
                    "text_html": _to_html(raw_text, uid),
                    "created_at": _unix_to_dt(row["post_time"]),
                },
            )
            imported += 1

        self.stdout.write(f"Imported {imported} posts ({skipped} skipped)")
