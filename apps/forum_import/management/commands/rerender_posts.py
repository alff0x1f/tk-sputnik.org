import re

from django.core.management.base import BaseCommand

from apps.forum.models import Post
from apps.forum_import.management.commands.import_phpbb_attachments import (
    _finalize_post_html,
)

_UID_DETECT_RE = re.compile(r"\[[a-zA-Z][a-zA-Z0-9]*:([a-z0-9]{5,12})\]")


def _detect_uid(text: str) -> str:
    m = _UID_DETECT_RE.search(text)
    return m.group(1) if m else ""


class Command(BaseCommand):
    help = "Re-render text_html for all posts from text_bbcode"

    def handle(self, *args, **options):
        posts = list(Post.objects.order_by("phpbb_id"))
        total = len(posts)
        self.stdout.write(f"Re-rendering {total} posts...")

        for i, post in enumerate(posts, start=1):
            uid = post.bbcode_uid or _detect_uid(post.text_bbcode)
            attachments = list(post.attachments.order_by("phpbb_id"))
            post.text_html = _finalize_post_html(post.text_bbcode, uid, attachments)
            post.save(update_fields=["text_html"])

            if i % 100 == 0 or i == total:
                self.stdout.write(f"\r  {i}/{total}", ending="")
                self.stdout.flush()

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Re-rendered {total} posts"))
