from datetime import UTC, datetime
from io import StringIO
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from apps.forum.models import ForumCategory, SubForum


class ForumImportAppConfigTest(TestCase):
    def test_app_registered_in_installed_apps(self):
        self.assertIn("apps.forum_import", settings.INSTALLED_APPS)


class ImportPhpbbForumsCommandTest(TestCase):
    def _make_row(self, forum_id, parent_id, forum_type, name, left_id=1, ts=0):
        return (
            forum_id,
            parent_id,
            forum_type,
            name,
            "",
            0,
            0,
            "",
            "",
            ts,
            left_id,
        )

    def _mock_cursor(self, rows):
        cursor = MagicMock()
        cursor.description = [
            ("forum_id",),
            ("parent_id",),
            ("forum_type",),
            ("forum_name",),
            ("forum_desc",),
            ("forum_topics",),
            ("forum_posts",),
            ("forum_last_post_subject",),
            ("forum_last_poster_name",),
            ("forum_last_post_time",),
            ("left_id",),
        ]
        cursor.fetchall.return_value = rows
        return cursor

    @patch("apps.forum_import.management.commands.import_phpbb_forums.connections")
    def test_imports_categories_and_subforums(self, mock_connections):
        rows = [
            self._make_row(1, 0, 0, "Приключения", left_id=1),
            self._make_row(2, 0, 0, "Велосипед", left_id=3),
            self._make_row(10, 1, 1, "Пешие походы", left_id=2),
            self._make_row(11, 2, 1, "Велопоходы", left_id=4),
            self._make_row(12, 10, 1, "Горные маршруты", left_id=5),
        ]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        out = StringIO()
        call_command("import_phpbb_forums", stdout=out)

        self.assertEqual(ForumCategory.objects.count(), 2)
        self.assertEqual(SubForum.objects.count(), 3)
        self.assertIn("Imported 2 categories, 3 subforums", out.getvalue())

    @patch("apps.forum_import.management.commands.import_phpbb_forums.connections")
    def test_direct_subforum_fk(self, mock_connections):
        rows = [
            self._make_row(1, 0, 0, "Приключения"),
            self._make_row(10, 1, 1, "Пешие походы"),
        ]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_forums", stdout=StringIO())

        cat = ForumCategory.objects.get(phpbb_id=1)
        sub = SubForum.objects.get(phpbb_id=10)
        self.assertEqual(sub.category, cat)
        self.assertEqual(sub.phpbb_parent_id, 1)

    @patch("apps.forum_import.management.commands.import_phpbb_forums.connections")
    def test_nested_subforum_links_to_root_category(self, mock_connections):
        rows = [
            self._make_row(1, 0, 0, "Приключения"),
            self._make_row(10, 1, 1, "Пешие походы"),
            self._make_row(20, 10, 1, "Горные маршруты"),
        ]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_forums", stdout=StringIO())

        cat = ForumCategory.objects.get(phpbb_id=1)
        nested = SubForum.objects.get(phpbb_id=20)
        self.assertEqual(nested.category, cat)
        self.assertEqual(nested.phpbb_parent_id, 10)

    @patch("apps.forum_import.management.commands.import_phpbb_forums.connections")
    def test_unix_timestamp_converted(self, mock_connections):
        ts = 1000000
        rows = [
            self._make_row(1, 0, 0, "Приключения", ts=ts),
            self._make_row(10, 1, 1, "Пешие походы", ts=ts),
        ]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_forums", stdout=StringIO())

        expected = datetime.fromtimestamp(ts, tz=UTC)
        cat = ForumCategory.objects.get(phpbb_id=1)
        sub = SubForum.objects.get(phpbb_id=10)
        self.assertEqual(cat.last_post_at, expected)
        self.assertEqual(sub.last_post_at, expected)

    @patch("apps.forum_import.management.commands.import_phpbb_forums.connections")
    def test_update_or_create_idempotent(self, mock_connections):
        rows = [
            self._make_row(1, 0, 0, "Приключения"),
        ]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_forums", stdout=StringIO())
        call_command("import_phpbb_forums", stdout=StringIO())

        self.assertEqual(ForumCategory.objects.count(), 1)

    @patch("apps.forum_import.management.commands.import_phpbb_forums.connections")
    def test_html_entities_unescaped(self, mock_connections):
        rows = [
            self._make_row(1, 0, 0, "Турклуб &quot;Спутник&quot;"),
            self._make_row(10, 1, 1, "Походы &amp; приключения"),
        ]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_forums", stdout=StringIO())

        cat = ForumCategory.objects.get(phpbb_id=1)
        self.assertEqual(cat.name, 'Турклуб "Спутник"')
        sub = SubForum.objects.get(phpbb_id=10)
        self.assertEqual(sub.name, "Походы & приключения")
