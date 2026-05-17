import os
from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.forum.models import PostAttachment


class Command(BaseCommand):
    help = "Replace stale media attachment URLs with /forum/a/<pk>/ in post HTML"

    def handle(self, *args, **options):
        attachments = list(
            PostAttachment.objects.select_related("post").order_by(
                "post_id", "phpbb_id"
            )
        )

        by_post = defaultdict(list)
        for att in attachments:
            by_post[att.post_id].append(att)

        updated_posts = 0
        updated_attachments = 0

        for post_id, atts in by_post.items():
            post = atts[0].post
            original_html = post.text_html
            new_html = original_html

            for att in atts:
                basename = os.path.basename(att.physical_filename)
                old_url = f"{settings.MEDIA_URL}forum/attachments/{basename}"
                new_html = new_html.replace(old_url, att.url)

            if new_html != original_html:
                post.text_html = new_html
                post.save(update_fields=["text_html"])
                updated_posts += 1
                updated_attachments += len(atts)

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {updated_posts} posts ({updated_attachments} attachments)"
            )
        )
