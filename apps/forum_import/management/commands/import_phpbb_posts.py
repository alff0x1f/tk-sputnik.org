import html
import re
from datetime import UTC, datetime

import bbcode
from django.core.management.base import BaseCommand
from django.db import connections

from apps.forum.models import ForumUser, Post, Topic

POSTS_TABLE = "vu2_posts"

_SAFE_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
_HREF_RE = re.compile(r'<a[^>]+href="([^"]+)"')

_SMILEY_RE = re.compile(
    r'<!-- s[^>]* -->'
    r'<img\s+src="\{SMILIES_PATH\}/([^"]+)"[^/]*/>'
    r'<!-- s[^>]* -->'
)
_URL_MARKER_RE = re.compile(r'<!-- m -->(.*?)<!-- m -->', re.DOTALL)
_EMAIL_MARKER_RE = re.compile(r'<!-- e -->(.*?)<!-- e -->', re.DOTALL)
_ALT_RE = re.compile(r'\salt="([^"]*)"')
_REL_RE = re.compile(r'(<a\b)', re.IGNORECASE)


def _extract_phpbb_markers(text: str) -> tuple[str, dict]:
    replacements = {}
    counter = 0

    def store(html_replacement):
        nonlocal counter
        key = f"\x00P{counter}\x00"
        replacements[key] = html_replacement
        counter += 1
        return key

    def replace_smiley(m):
        filename = m.group(1)
        alt_m = _ALT_RE.search(m.group(0))
        alt = alt_m.group(1) if alt_m else ""
        return store(f'<img src="/media/forum/smilies/{html.escape(filename)}" alt="{html.escape(alt)}">')

    def replace_link_marker(m):
        inner = m.group(1)
        inner_with_rel = _REL_RE.sub(r'\1 rel="nofollow"', inner, count=1)
        return store(inner_with_rel)

    text = _SMILEY_RE.sub(replace_smiley, text)
    text = _URL_MARKER_RE.sub(replace_link_marker, text)
    text = _EMAIL_MARKER_RE.sub(replace_link_marker, text)
    return text, replacements


def _render_img(tag_name, value, options, parent, context):
    url = (value or "").strip()
    # The parser auto-links URLs before passing value here; extract href if so.
    m = _HREF_RE.search(url)
    if m:
        url = html.unescape(m.group(1))
    if _SAFE_URL_RE.match(url):
        return f'<img src="{html.escape(url, quote=True)}" alt="">'
    return ""


def _render_size(tag_name, value, options, parent, context):
    size = options.get("size", "")
    if size.isdigit():
        return f'<span style="font-size:{size}%">{value}</span>'
    return value or ""


_parser = bbcode.Parser()
_parser.add_formatter("img", _render_img, render_embedded=False)
_parser.add_formatter("size", _render_size)


def _to_html(raw: str, uid: str) -> str:
    text = html.unescape(raw or "")
    if uid:
        text = re.sub(rf"\[([^\[\]]*?):{re.escape(uid)}\]", r"[\1]", text)
        text = re.sub(rf"\[/([^\[\]]*?):{re.escape(uid)}\]", r"[/\1]", text)
    # Strip phpBB list-type markers (:u unordered, :o ordered, :m item-close)
    # that remain after UID removal and are unknown to the bbcode parser.
    text = re.sub(r"\[list:u\]", "[list]", text, flags=re.IGNORECASE)
    text = re.sub(r"\[list:o\]", "[list=1]", text, flags=re.IGNORECASE)
    text = re.sub(r"\[/list:[uo]\]", "[/list]", text, flags=re.IGNORECASE)
    text = re.sub(r"\[/\*:m\]", "", text, flags=re.IGNORECASE)
    text, replacements = _extract_phpbb_markers(text)
    result = _parser.format(text)
    for key, value in replacements.items():
        result = result.replace(key, value)
    return result


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

        total = len(rows)
        imported = 0
        skipped = 0

        self.stdout.write(f"Importing {total} posts...")

        for i, row in enumerate(rows, start=1):
            try:
                topic = Topic.objects.get(id=row["topic_id"])
            except Topic.DoesNotExist:
                self.stderr.write(
                    f"Topic phpbb_id={row['topic_id']} not found"
                    f" for post {row['post_id']}, skipping"
                )
                skipped += 1
                continue

            try:
                author = ForumUser.objects.get(id=row["poster_id"])
            except ForumUser.DoesNotExist:
                author = None

            raw_text = row["post_text"] or ""
            uid = row["bbcode_uid"] or ""

            Post.objects.update_or_create(
                id=row["post_id"],
                defaults={
                    "phpbb_id": row["post_id"],
                    "topic": topic,
                    "author": author,
                    "author_username": row["post_username"] or "",
                    "text_bbcode": raw_text,
                    "text_html": _to_html(raw_text, uid),
                    "created_at": _unix_to_dt(row["post_time"]),
                },
            )
            imported += 1

            if i % 100 == 0 or i == total:
                self.stdout.write(f"\r  {i}/{total}", ending="")
                self.stdout.flush()

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Imported {imported} posts ({skipped} skipped)")
        )
