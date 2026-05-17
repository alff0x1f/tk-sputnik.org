import html
import re

from django.core.management.base import BaseCommand
from django.db import connections

from apps.forum.models import Post, PostAttachment
from apps.forum_import.management.commands.import_phpbb_posts import _to_html

ATTACHMENTS_TABLE = "vu2_attachments"
POSTS_TABLE = "vu2_posts"

_PLACEHOLDER_RE = re.compile(
    r'<span class="attachment-ref" data-index="(\d+)" data-name="[^"]*"></span>'
)


def _format_size(size_bytes):
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def _render_attachment_html(att):
    url = html.escape(att.url, quote=True)
    name = html.escape(att.real_filename)
    if att.is_image:
        return f'<img src="{url}" alt="{name}">'
    size = _format_size(att.filesize)
    return f'<a href="{url}">{name}</a> ({size})'


def _finalize_post_html(raw_bbcode, uid, attachments):
    """Re-render BBCode and replace attachment placeholders with real HTML."""
    html_text = _to_html(raw_bbcode, uid)
    referenced_indices = set()

    def replace_placeholder(m):
        idx = int(m.group(1))
        referenced_indices.add(idx)
        if idx < len(attachments):
            return _render_attachment_html(attachments[idx])
        return ""

    result = _PLACEHOLDER_RE.sub(replace_placeholder, html_text)

    unreferenced = [
        att for i, att in enumerate(attachments) if i not in referenced_indices
    ]
    if unreferenced:
        footer_items = "".join(_render_attachment_html(att) for att in unreferenced)
        result += f'<div class="post-attachments">{footer_items}</div>'

    return result


class Command(BaseCommand):
    help = "Import attachments from phpBB MySQL database"

    def handle(self, *args, **options):
        cursor = connections["phpbb"].cursor()
        cursor.execute(
            f"SELECT attach_id, post_msg_id, physical_filename, real_filename,"  # noqa: S608
            f" mimetype, filesize, download_count, attach_comment"
            f" FROM {ATTACHMENTS_TABLE}"
            f" WHERE is_orphan = 0 AND in_message = 0 ORDER BY attach_id"
        )
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        total = len(rows)
        imported = 0
        skipped = 0
        affected_post_phpbb_ids = set()

        self.stdout.write(f"Importing {total} attachments...")

        for row in rows:
            post_phpbb_id = row["post_msg_id"]
            try:
                post = Post.objects.get(phpbb_id=post_phpbb_id)
            except Post.DoesNotExist:
                self.stderr.write(
                    f"Post phpbb_id={post_phpbb_id} not found"
                    f" for attachment {row['attach_id']}, skipping"
                )
                skipped += 1
                continue

            PostAttachment.objects.update_or_create(
                id=row["attach_id"],
                defaults={
                    "phpbb_id": row["attach_id"],
                    "post": post,
                    "physical_filename": row["physical_filename"] or "",
                    "real_filename": row["real_filename"] or "",
                    "mimetype": row["mimetype"] or "",
                    "filesize": row["filesize"] or 0,
                    "download_count": row["download_count"] or 0,
                    "attach_comment": row["attach_comment"] or "",
                },
            )
            imported += 1
            affected_post_phpbb_ids.add(post_phpbb_id)

        # Second pass: fetch bbcode_uid for all affected posts, then re-render HTML
        uid_map = {}
        if affected_post_phpbb_ids:
            placeholders = ",".join(["%s"] * len(affected_post_phpbb_ids))
            cursor.execute(
                f"SELECT post_id, bbcode_uid FROM {POSTS_TABLE}"  # noqa: S608
                f" WHERE post_id IN ({placeholders})",
                list(affected_post_phpbb_ids),
            )
            for post_id, bbcode_uid in cursor.fetchall():
                uid_map[post_id] = bbcode_uid or ""

        affected_posts = list(Post.objects.filter(phpbb_id__in=affected_post_phpbb_ids))
        total_posts = len(affected_posts)

        if total_posts:
            self.stdout.write(f"Re-rendering HTML for {total_posts} posts...")
            for i, post in enumerate(affected_posts, start=1):
                uid = uid_map.get(post.phpbb_id, "")
                attachments = list(post.attachments.order_by("phpbb_id"))
                post.text_html = _finalize_post_html(post.text_bbcode, uid, attachments)
                post.save(update_fields=["text_html"])

                if i % 100 == 0 or i == total_posts:
                    self.stdout.write(f"\r  {i}/{total_posts}", ending="")
                    self.stdout.flush()
            self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {imported} attachments ({skipped} skipped)"
            )
        )
