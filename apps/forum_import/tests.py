from datetime import UTC, datetime
from io import StringIO
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from apps.forum.models import (
    ForumCategory,
    ForumUser,
    Post,
    PostAttachment,
    SubForum,
    Topic,
)
from apps.forum_import.management.commands.import_phpbb_posts import _to_html


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

    def _mock_cursor(self, rows, *, acl_rows=None):
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
        # Two fetchall calls per command run: forums then ACL data.
        cursor.fetchall.side_effect = [rows, acl_rows if acl_rows is not None else []]
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
        # Command runs twice → 4 fetchall calls: (forums, acl) × 2
        cursor.fetchall.side_effect = [rows, [], rows, []]
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

    @patch("apps.forum_import.management.commands.import_phpbb_forums.connections")
    def test_private_subforum_gets_is_private_and_group(self, mock_connections):
        rows = [
            self._make_row(1, 0, 0, "Приключения"),
            self._make_row(19, 1, 1, "Орг"),
        ]
        # ACL: group "ORG" can read forum 19, GUESTS cannot
        acl_rows = [(19, "ORG", 1)]
        cursor = self._mock_cursor(rows, acl_rows=acl_rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        out = StringIO()
        call_command("import_phpbb_forums", stdout=out)

        sub = SubForum.objects.get(phpbb_id=19)
        self.assertTrue(sub.is_private)
        self.assertIsNotNone(sub.allowed_group)
        self.assertEqual(sub.allowed_group.name, "орг")
        self.assertIn("Marked 1 subforums as private", out.getvalue())

    @patch("apps.forum_import.management.commands.import_phpbb_forums.connections")
    def test_public_subforum_gets_is_private_false(self, mock_connections):
        rows = [
            self._make_row(1, 0, 0, "Приключения"),
            self._make_row(10, 1, 1, "Пешие походы"),
        ]
        # ACL: GUESTS can read forum 10
        acl_rows = [(10, "GUESTS", 1), (10, "REGISTERED", 1)]
        cursor = self._mock_cursor(rows, acl_rows=acl_rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_forums", stdout=StringIO())

        sub = SubForum.objects.get(phpbb_id=10)
        self.assertFalse(sub.is_private)
        self.assertIsNone(sub.allowed_group)


class FetchPrivateForumIdsTest(TestCase):
    def _acl_cursor(self, acl_rows):
        cursor = MagicMock()
        cursor.fetchall.return_value = acl_rows
        return cursor

    def _call(self, acl_rows):
        from apps.forum_import.management.commands.import_phpbb_forums import (
            _fetch_private_forum_ids,
        )

        return _fetch_private_forum_ids(self._acl_cursor(acl_rows))

    def test_group_allowed_guests_absent_is_private(self):
        result = self._call([(19, "ORG", 1)])
        self.assertIn(19, result)

    def test_guests_allowed_is_not_private(self):
        result = self._call([(1, "GUESTS", 1), (1, "REGISTERED", 1)])
        self.assertNotIn(1, result)

    def test_no_group_allowed_is_not_private(self):
        result = self._call([(5, "ORG", 0)])
        self.assertNotIn(5, result)

    def test_guests_never_other_group_allowed_is_private(self):
        result = self._call([(7, "GUESTS", 0), (7, "MODS", 1)])
        self.assertIn(7, result)

    def test_multiple_forums_mixed(self):
        acl_rows = [
            (1, "GUESTS", 1),
            (1, "REGISTERED", 1),
            (19, "ORG", 1),
            (7, "GUESTS", 0),
            (7, "MODS", 1),
        ]
        result = self._call(acl_rows)
        self.assertNotIn(1, result)
        self.assertIn(19, result)
        self.assertIn(7, result)

    def test_empty_acl_returns_empty_set(self):
        result = self._call([])
        self.assertEqual(result, set())

    def test_query_includes_role_based_acl_table(self):
        cursor = self._acl_cursor([])
        from apps.forum_import.management.commands.import_phpbb_forums import (
            _fetch_private_forum_ids,
        )

        _fetch_private_forum_ids(cursor)
        executed_sql = cursor.execute.call_args[0][0]
        self.assertIn("acl_roles_data", executed_sql)


class ImportPhpbbUsersCommandTest(TestCase):
    def _make_user_row(
        self,
        user_id=10,
        username="testuser",
        email="test@example.com",
        avatar="",
        avatar_type=0,
        regdate=1000000,
        posts=5,
    ):
        return (user_id, username, email, avatar, avatar_type, regdate, posts)

    def _mock_user_cursor(self, rows):
        cursor = MagicMock()
        cursor.description = [
            ("user_id",),
            ("username",),
            ("user_email",),
            ("user_avatar",),
            ("user_avatar_type",),
            ("user_regdate",),
            ("user_posts",),
        ]
        cursor.fetchall.return_value = rows
        return cursor

    @patch("apps.forum_import.management.commands.import_phpbb_users.connections")
    def test_imports_users_and_prints_count(self, mock_connections):
        rows = [
            self._make_user_row(10, "alice", "alice@example.com"),
            self._make_user_row(11, "bob", "bob@example.com"),
        ]
        cursor = self._mock_user_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        out = StringIO()
        call_command("import_phpbb_users", stdout=out)

        self.assertEqual(ForumUser.objects.count(), 2)
        self.assertIn("Imported 2 users", out.getvalue())

    @patch("apps.forum_import.management.commands.import_phpbb_users.connections")
    def test_anon_user_excluded_by_sql_filter(self, mock_connections):
        cursor = self._mock_user_cursor([])
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_users", stdout=StringIO())

        executed_sql = cursor.execute.call_args[0][0]
        self.assertIn("user_id != 1", executed_sql)

    @patch("apps.forum_import.management.commands.import_phpbb_users.connections")
    def test_bot_user_excluded_by_sql_filter(self, mock_connections):
        cursor = self._mock_user_cursor([])
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_users", stdout=StringIO())

        executed_sql = cursor.execute.call_args[0][0]
        self.assertIn("user_type != 2", executed_sql)

    @patch("apps.forum_import.management.commands.import_phpbb_users.connections")
    def test_remote_avatar_stored_as_is(self, mock_connections):
        url = "https://example.com/avatar.jpg"
        rows = [self._make_user_row(10, avatar=url, avatar_type=2)]
        cursor = self._mock_user_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_users", stdout=StringIO())

        user = ForumUser.objects.get(phpbb_id=10)
        self.assertEqual(user.avatar, url)

    @patch("apps.forum_import.management.commands.import_phpbb_users.connections")
    def test_uploaded_avatar_stored_as_filename(self, mock_connections):
        filename = "10_abc123.jpg"
        rows = [self._make_user_row(10, avatar=filename, avatar_type=1)]
        cursor = self._mock_user_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_users", stdout=StringIO())

        user = ForumUser.objects.get(phpbb_id=10)
        self.assertEqual(user.avatar, filename)

    @patch("apps.forum_import.management.commands.import_phpbb_users.connections")
    def test_empty_avatar_stored_as_empty_string(self, mock_connections):
        rows = [self._make_user_row(10, avatar="", avatar_type=0)]
        cursor = self._mock_user_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_users", stdout=StringIO())

        user = ForumUser.objects.get(phpbb_id=10)
        self.assertEqual(user.avatar, "")

    @patch("apps.forum_import.management.commands.import_phpbb_users.connections")
    def test_regdate_timestamp_converted_to_aware_datetime(self, mock_connections):
        ts = 1000000
        rows = [self._make_user_row(10, regdate=ts)]
        cursor = self._mock_user_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_users", stdout=StringIO())

        user = ForumUser.objects.get(phpbb_id=10)
        expected = datetime.fromtimestamp(ts, tz=UTC)
        self.assertEqual(user.registered_at, expected)

    @patch("apps.forum_import.management.commands.import_phpbb_users.connections")
    def test_idempotency(self, mock_connections):
        rows = [self._make_user_row(10, "alice")]
        cursor = self._mock_user_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_users", stdout=StringIO())
        call_command("import_phpbb_users", stdout=StringIO())

        self.assertEqual(ForumUser.objects.count(), 1)


class ImportPhpbbTopicsCommandTest(TestCase):
    def setUp(self):
        cat = ForumCategory.objects.create(id=1, phpbb_id=1, name="Категория")
        self.subforum = SubForum.objects.create(
            id=10, phpbb_id=10, phpbb_parent_id=1, category=cat, name="Подфорум"
        )

    def _make_row(
        self, topic_id=100, forum_id=10, title="Тема", ts=1000000, views=5, replies=3
    ):
        return (topic_id, forum_id, title, ts, views, replies)

    def _mock_cursor(self, rows):
        cursor = MagicMock()
        cursor.description = [
            ("topic_id",),
            ("forum_id",),
            ("topic_title",),
            ("topic_time",),
            ("topic_views",),
            ("topic_replies",),
        ]
        cursor.fetchall.return_value = rows
        return cursor

    @patch("apps.forum_import.management.commands.import_phpbb_topics.connections")
    def test_imports_topics(self, mock_connections):
        rows = [
            self._make_row(100, 10, "Первая тема"),
            self._make_row(101, 10, "Вторая тема"),
        ]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        out = StringIO()
        call_command("import_phpbb_topics", stdout=out)

        self.assertEqual(Topic.objects.count(), 2)
        self.assertIn("Imported 2 topics (0 skipped)", out.getvalue())

    @patch("apps.forum_import.management.commands.import_phpbb_topics.connections")
    def test_skips_unknown_subforum(self, mock_connections):
        rows = [
            self._make_row(100, 10, "Нормальная тема"),
            self._make_row(101, 99, "Тема с неизвестным форумом"),
        ]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        out = StringIO()
        err = StringIO()
        call_command("import_phpbb_topics", stdout=out, stderr=err)

        self.assertEqual(Topic.objects.count(), 1)
        self.assertIn("Imported 1 topics (1 skipped)", out.getvalue())
        self.assertIn("phpbb_id=99", err.getvalue())

    @patch("apps.forum_import.management.commands.import_phpbb_topics.connections")
    def test_idempotency(self, mock_connections):
        rows = [self._make_row(100, 10, "Тема")]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_topics", stdout=StringIO())
        call_command("import_phpbb_topics", stdout=StringIO())

        self.assertEqual(Topic.objects.count(), 1)

    @patch("apps.forum_import.management.commands.import_phpbb_topics.connections")
    def test_unix_timestamp_converted(self, mock_connections):
        ts = 1000000
        rows = [self._make_row(100, 10, ts=ts)]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_topics", stdout=StringIO())

        topic = Topic.objects.get(phpbb_id=100)
        expected = datetime.fromtimestamp(ts, tz=UTC)
        self.assertEqual(topic.created_at, expected)

    @patch("apps.forum_import.management.commands.import_phpbb_topics.connections")
    def test_post_count_includes_first_post(self, mock_connections):
        rows = [self._make_row(100, 10, replies=7)]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_topics", stdout=StringIO())

        topic = Topic.objects.get(phpbb_id=100)
        self.assertEqual(topic.post_count, 8)


class ImportPhpbbPostsCommandTest(TestCase):
    def setUp(self):
        cat = ForumCategory.objects.create(id=1, phpbb_id=1, name="Категория")
        subforum = SubForum.objects.create(
            id=10, phpbb_id=10, phpbb_parent_id=1, category=cat, name="Подфорум"
        )
        self.topic = Topic.objects.create(
            id=100, phpbb_id=100, subforum=subforum, title="Тема"
        )
        self.user = ForumUser.objects.create(id=5, phpbb_id=5, username="alice")

    def _make_row(
        self,
        post_id=200,
        topic_id=100,
        poster_id=5,
        post_username="alice",
        post_text="Hello [b]world[/b]",
        bbcode_uid="",
        post_time=1000000,
    ):
        return (
            post_id,
            topic_id,
            poster_id,
            post_username,
            post_text,
            bbcode_uid,
            post_time,
        )

    def _mock_cursor(self, rows):
        cursor = MagicMock()
        cursor.description = [
            ("post_id",),
            ("topic_id",),
            ("poster_id",),
            ("post_username",),
            ("post_text",),
            ("bbcode_uid",),
            ("post_time",),
        ]
        cursor.fetchall.return_value = rows
        return cursor

    @patch("apps.forum_import.management.commands.import_phpbb_posts.connections")
    def test_imports_posts(self, mock_connections):
        rows = [
            self._make_row(200, 100),
            self._make_row(201, 100),
        ]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        out = StringIO()
        call_command("import_phpbb_posts", stdout=out)

        self.assertEqual(Post.objects.count(), 2)
        self.assertIn("Imported 2 posts (0 skipped)", out.getvalue())

    @patch("apps.forum_import.management.commands.import_phpbb_posts.connections")
    def test_skips_unknown_topic(self, mock_connections):
        rows = [
            self._make_row(200, 100),
            self._make_row(201, 999),
        ]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        out = StringIO()
        err = StringIO()
        call_command("import_phpbb_posts", stdout=out, stderr=err)

        self.assertEqual(Post.objects.count(), 1)
        self.assertIn("Imported 1 posts (1 skipped)", out.getvalue())
        self.assertIn("phpbb_id=999", err.getvalue())

    @patch("apps.forum_import.management.commands.import_phpbb_posts.connections")
    def test_null_author_for_missing_user(self, mock_connections):
        rows = [self._make_row(200, 100, poster_id=9999, post_username="ghost")]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_posts", stdout=StringIO())

        post = Post.objects.get(phpbb_id=200)
        self.assertIsNone(post.author)
        self.assertEqual(post.author_username, "ghost")

    @patch("apps.forum_import.management.commands.import_phpbb_posts.connections")
    def test_idempotency(self, mock_connections):
        rows = [self._make_row(200, 100)]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_posts", stdout=StringIO())
        call_command("import_phpbb_posts", stdout=StringIO())

        self.assertEqual(Post.objects.count(), 1)

    @patch("apps.forum_import.management.commands.import_phpbb_posts.connections")
    def test_bbcode_uid_stripped(self, mock_connections):
        uid = "12hsql24"
        rows = [
            self._make_row(
                200, 100, post_text=f"[b:{uid}]bold[/b:{uid}]", bbcode_uid=uid
            )
        ]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_posts", stdout=StringIO())

        post = Post.objects.get(phpbb_id=200)
        self.assertIn("bold", post.text_html)
        self.assertNotIn(f":{uid}", post.text_html)

    @patch("apps.forum_import.management.commands.import_phpbb_posts.connections")
    def test_bbcode_uid_stripped_url(self, mock_connections):
        uid = "12hsql24"
        # phpBB stores colons in URLs as &#58;; after html.unescape they become ':'
        rows = [
            self._make_row(
                200,
                100,
                post_text=f"[url=http&#58;//example.com:{uid}]link[/url:{uid}]",
                bbcode_uid=uid,
            )
        ]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_posts", stdout=StringIO())

        post = Post.objects.get(phpbb_id=200)
        self.assertNotIn(f":{uid}", post.text_html)
        self.assertIn("example.com", post.text_html)

    @patch("apps.forum_import.management.commands.import_phpbb_posts.connections")
    def test_bbcode_uid_stripped_list(self, mock_connections):
        uid = "12hsql24"
        rows = [
            self._make_row(
                200,
                100,
                post_text=f"[list:u:{uid}][*:{uid}]item[/*:m:{uid}][/list:u:{uid}]",
                bbcode_uid=uid,
            )
        ]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_posts", stdout=StringIO())

        post = Post.objects.get(phpbb_id=200)
        self.assertNotIn(f":{uid}", post.text_html)
        self.assertNotIn("[list", post.text_html)
        self.assertIn("<ul>", post.text_html)
        self.assertIn("<li>", post.text_html)

    @patch("apps.forum_import.management.commands.import_phpbb_posts.connections")
    def test_html_entities_unescaped(self, mock_connections):
        # &#1087;&#1088;&#1080;&#1074;&#1077;&#1090; = привет
        rows = [
            self._make_row(
                200,
                100,
                post_text="&#1087;&#1088;&#1080;&#1074;&#1077;&#1090;",
            )
        ]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_posts", stdout=StringIO())

        post = Post.objects.get(phpbb_id=200)
        self.assertIn("привет", post.text_html)

    @patch("apps.forum_import.management.commands.import_phpbb_posts.connections")
    def test_unix_timestamp_converted(self, mock_connections):
        ts = 1000000
        rows = [self._make_row(200, 100, post_time=ts)]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_posts", stdout=StringIO())

        post = Post.objects.get(phpbb_id=200)
        expected = datetime.fromtimestamp(ts, tz=UTC)
        self.assertEqual(post.created_at, expected)

    @patch("apps.forum_import.management.commands.import_phpbb_posts.connections")
    def test_img_tag_converted_to_html(self, mock_connections):
        uid = "abc123"
        rows = [
            self._make_row(
                200,
                100,
                post_text=f"[img:{uid}]http://example.com/a.jpg[/img:{uid}]",
                bbcode_uid=uid,
            )
        ]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_posts", stdout=StringIO())

        post = Post.objects.get(phpbb_id=200)
        self.assertIn('<img src="http://example.com/a.jpg"', post.text_html)
        self.assertNotIn("[img]", post.text_html)
        self.assertNotIn("[/img]", post.text_html)

    @patch("apps.forum_import.management.commands.import_phpbb_posts.connections")
    def test_size_tag_converted_to_html(self, mock_connections):
        uid = "abc123"
        rows = [
            self._make_row(
                200,
                100,
                post_text=f"[size=150:{uid}]big text[/size:{uid}]",
                bbcode_uid=uid,
            )
        ]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_posts", stdout=StringIO())

        post = Post.objects.get(phpbb_id=200)
        self.assertIn("big text", post.text_html)
        self.assertIn("font-size:150%", post.text_html)
        self.assertNotIn("[size", post.text_html)


class ToHtmlSpoilerTest(TestCase):
    def test_spoiler_with_title_renders_details(self):
        uid = "abc123"
        raw = f"[spoiler=Секрет:{uid}]скрытый текст[/spoiler:{uid}]"
        result = _to_html(raw, uid)
        self.assertIn("<details", result)
        self.assertIn("<summary>Секрет</summary>", result)
        self.assertIn('class="spoiler-body"', result)
        self.assertIn("скрытый текст", result)
        self.assertNotIn("[spoiler", result)

    def test_spoiler_title_is_escaped(self):
        raw = "[spoiler=<script>alert(1)</script>]content[/spoiler]"
        result = _to_html(raw, "")
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)

    def test_spoiler_empty_title_uses_default(self):
        raw = "[spoiler=]content[/spoiler]"
        result = _to_html(raw, "")
        self.assertIn("<summary>Spoiler</summary>", result)

    def test_spoiler_has_css_class(self):
        raw = "[spoiler=Заголовок]текст[/spoiler]"
        result = _to_html(raw, "")
        self.assertIn('class="spoiler"', result)


class ToHtmlSmiliesMarkersTest(TestCase):
    def test_smiley_renders_to_img_tag(self):
        raw = (
            '<!-- s:) --><img src="{SMILIES_PATH}/smile.gif"'
            ' alt=":)" title="Smile" /><!-- s:) -->'
        )
        result = _to_html(raw, "")
        self.assertIn('<img src="/media/forum/smilies/smile.gif"', result)
        self.assertIn('alt=":)"', result)
        self.assertNotIn("{SMILIES_PATH}", result)
        self.assertNotIn("<!-- s", result)

    def test_url_marker_renders_with_target_blank(self):
        raw = (
            '<!-- m --><a class="postlink" href="https://example.com">'
            "text</a><!-- m -->"
        )
        result = _to_html(raw, "")
        self.assertIn('href="https://example.com"', result)
        self.assertIn('rel="nofollow noreferrer"', result)
        self.assertIn('target="_blank"', result)
        self.assertIn(">text<", result)
        self.assertNotIn("<!-- m -->", result)

    def test_www_marker_renders_with_target_blank(self):
        raw = (
            '<!-- w --><a class="postlink" href="http://www.example.com">'
            "www.example.com</a><!-- w -->"
        )
        result = _to_html(raw, "")
        self.assertIn('href="http://www.example.com"', result)
        self.assertIn('target="_blank"', result)
        self.assertIn('rel="nofollow noreferrer"', result)
        self.assertNotIn("<!-- w -->", result)

    def test_email_marker_renders_with_rel_nofollow(self):
        raw = (
            '<!-- e --><a href="mailto:user@example.com">user@example.com</a><!-- e -->'
        )
        result = _to_html(raw, "")
        self.assertIn('href="mailto:user@example.com"', result)
        self.assertIn('rel="nofollow noreferrer"', result)
        self.assertNotIn("<!-- e -->", result)

    def test_local_marker_veloufa_viewtopic_rewritten(self):
        raw = (
            '<!-- l --><a class="postlink-local"'
            ' href="http://forum.veloufa.ru/viewtopic.php?f=10&amp;t=6057">'
            "viewtopic.php?f=10&amp;t=6057</a><!-- l -->"
        )
        result = _to_html(raw, "")
        self.assertIn('href="/forum/viewtopic.php?f=10&amp;t=6057"', result)
        self.assertNotIn("forum.veloufa.ru", result)
        self.assertNotIn("<!-- l -->", result)
        self.assertNotIn('target="_blank"', result)
        self.assertNotIn("nofollow", result)

    def test_local_marker_veloufa_path_viewtopic_rewritten(self):
        raw = (
            '<!-- l --><a class="postlink-local"'
            ' href="http://www.veloufa.ru/forum/viewtopic.php?t=468">'
            "viewtopic.php?t=468</a><!-- l -->"
        )
        result = _to_html(raw, "")
        self.assertIn('href="/forum/viewtopic.php?t=468"', result)
        self.assertNotIn("veloufa.ru", result)
        self.assertNotIn("<!-- l -->", result)

    def test_local_marker_non_viewtopic_kept_as_external(self):
        raw = (
            '<!-- l --><a class="postlink-local"'
            ' href="http://forum.veloufa.ru/memberlist.php">'
            "memberlist</a><!-- l -->"
        )
        result = _to_html(raw, "")
        self.assertIn('href="http://forum.veloufa.ru/memberlist.php"', result)
        self.assertNotIn("<!-- l -->", result)

    def test_multiple_smileys_all_rendered(self):
        raw = (
            '<!-- s:) --><img src="{SMILIES_PATH}/smile.gif"'
            ' alt=":)" title="Smile" /><!-- s:) -->'
            " and "
            '<!-- s:D --><img src="{SMILIES_PATH}/grin.gif"'
            ' alt=":D" title="Grin" /><!-- s:D -->'
        )
        result = _to_html(raw, "")
        self.assertIn("/media/forum/smilies/smile.gif", result)
        self.assertIn("/media/forum/smilies/grin.gif", result)
        self.assertNotIn("{SMILIES_PATH}", result)
        self.assertEqual(result.count("<img"), 2)

    def test_bbcode_and_smiley_mixed(self):
        raw = (
            "[b]hello[/b] "
            '<!-- s:) --><img src="{SMILIES_PATH}/smile.gif"'
            ' alt=":)" title="Smile" /><!-- s:) -->'
        )
        result = _to_html(raw, "")
        self.assertIn("<strong>hello</strong>", result)
        self.assertIn("/media/forum/smilies/smile.gif", result)
        self.assertNotIn("{SMILIES_PATH}", result)
        self.assertNotIn("<!-- s", result)

    def test_smiley_with_slash_in_alt_renders(self):
        raw = (
            '<!-- s:/ --><img src="{SMILIES_PATH}/neutral.gif"'
            ' alt=":/" title="Neutral" /><!-- s:/ -->'
        )
        result = _to_html(raw, "")
        self.assertIn("/media/forum/smilies/neutral.gif", result)
        self.assertIn('alt=":/"', result)
        self.assertNotIn("{SMILIES_PATH}", result)

    def test_malformed_url_marker_produces_no_html(self):
        raw = "<!-- m --><img src=x onerror=alert(1)><!-- m -->"
        result = _to_html(raw, "")
        self.assertNotIn("<img", result)
        self.assertNotIn("onerror", result)

    def test_unsafe_scheme_in_url_marker_suppressed(self):
        raw = '<!-- m --><a href="javascript:alert(1)">click</a><!-- m -->'
        result = _to_html(raw, "")
        self.assertNotIn("javascript", result)
        self.assertNotIn("<a", result)


class ToHtmlAttachmentTest(TestCase):
    def test_attachment_tag_becomes_placeholder(self):
        raw = "[attachment=0]photo.jpg[/attachment]"
        result = _to_html(raw, "")
        self.assertIn('class="attachment-ref"', result)
        self.assertIn('data-index="0"', result)
        self.assertIn('data-name="photo.jpg"', result)
        self.assertNotIn("[attachment", result)

    def test_attachment_tag_with_uid(self):
        uid = "abc"
        raw = f"[attachment=0:{uid}]photo.jpg[/attachment:{uid}]"
        result = _to_html(raw, uid)
        self.assertIn('class="attachment-ref"', result)
        self.assertIn('data-index="0"', result)
        self.assertIn('data-name="photo.jpg"', result)
        self.assertNotIn(f":{uid}", result)

    def test_no_attachment_tag_unchanged(self):
        raw = "[b]hello[/b]"
        result = _to_html(raw, "")
        self.assertIn("<strong>hello</strong>", result)
        self.assertNotIn("attachment-ref", result)


class ImportPhpbbAttachmentsCommandTest(TestCase):
    def setUp(self):
        cat = ForumCategory.objects.create(id=1, phpbb_id=1, name="Категория")
        subforum = SubForum.objects.create(
            id=10, phpbb_id=10, phpbb_parent_id=1, category=cat, name="Подфорум"
        )
        topic = Topic.objects.create(
            id=100, phpbb_id=100, subforum=subforum, title="Тема"
        )
        self.post = Post.objects.create(
            id=200,
            phpbb_id=200,
            topic=topic,
            text_bbcode="[b]hello[/b]",
            text_html="<strong>hello</strong>",
        )

    def _make_att_row(
        self,
        attach_id=1,
        post_msg_id=200,
        physical_filename="file.jpg",
        real_filename="photo.jpg",
        mimetype="image/jpeg",
        filesize=1024,
        download_count=0,
        attach_comment="",
    ):
        return (
            attach_id,
            post_msg_id,
            physical_filename,
            real_filename,
            mimetype,
            filesize,
            download_count,
            attach_comment,
        )

    def _mock_cursor(self, att_rows, uid_rows=None):
        cursor = MagicMock()
        cursor.description = [
            ("attach_id",),
            ("post_msg_id",),
            ("physical_filename",),
            ("real_filename",),
            ("mimetype",),
            ("filesize",),
            ("download_count",),
            ("attach_comment",),
        ]
        cursor.fetchall.side_effect = [
            att_rows,
            uid_rows if uid_rows is not None else [(200, "")],
        ]
        return cursor

    @patch("apps.forum_import.management.commands.import_phpbb_attachments.connections")
    def test_import_creates_postattachment(self, mock_connections):
        rows = [self._make_att_row(1, 200)]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        out = StringIO()
        call_command("import_phpbb_attachments", stdout=out)

        self.assertEqual(PostAttachment.objects.count(), 1)
        att = PostAttachment.objects.get(phpbb_id=1)
        self.assertEqual(att.post, self.post)
        self.assertEqual(att.real_filename, "photo.jpg")
        self.assertIn("Imported 1 attachments (0 skipped)", out.getvalue())

    @patch("apps.forum_import.management.commands.import_phpbb_attachments.connections")
    def test_import_skips_orphans(self, mock_connections):
        cursor = self._mock_cursor([], uid_rows=[])
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_attachments", stdout=StringIO())

        executed_sql = cursor.execute.call_args_list[0][0][0]
        self.assertIn("is_orphan", executed_sql)

    @patch("apps.forum_import.management.commands.import_phpbb_attachments.connections")
    def test_import_skips_unknown_post(self, mock_connections):
        rows = [self._make_att_row(1, 9999)]
        cursor = self._mock_cursor(rows, uid_rows=[])
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        out = StringIO()
        err = StringIO()
        call_command("import_phpbb_attachments", stdout=out, stderr=err)

        self.assertEqual(PostAttachment.objects.count(), 0)
        self.assertIn("Imported 0 attachments (1 skipped)", out.getvalue())
        self.assertIn("phpbb_id=9999", err.getvalue())

    @patch("apps.forum_import.management.commands.import_phpbb_attachments.connections")
    def test_import_updates_post_html_inline(self, mock_connections):
        self.post.text_bbcode = "[attachment=0]photo.jpg[/attachment]"
        self.post.text_html = (
            '<span class="attachment-ref" data-index="0" data-name="photo.jpg"></span>'
        )
        self.post.save()

        rows = [
            self._make_att_row(
                1,
                200,
                physical_filename="file.jpg",
                real_filename="photo.jpg",
                mimetype="image/jpeg",
            )
        ]
        cursor = self._mock_cursor(rows, uid_rows=[(200, "")])
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_attachments", stdout=StringIO())

        self.post.refresh_from_db()
        self.assertIn("<img src=", self.post.text_html)
        self.assertIn("/forum/a/1/", self.post.text_html)
        self.assertNotIn("attachment-ref", self.post.text_html)

    @patch("apps.forum_import.management.commands.import_phpbb_attachments.connections")
    def test_import_excludes_private_message_attachments(self, mock_connections):
        cursor = self._mock_cursor([], uid_rows=[])
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_attachments", stdout=StringIO())

        executed_sql = cursor.execute.call_args_list[0][0][0]
        self.assertIn("in_message = 0", executed_sql)

    @patch("apps.forum_import.management.commands.import_phpbb_attachments.connections")
    def test_import_appends_footer_for_unreferenced(self, mock_connections):
        self.post.text_bbcode = "plain text"
        self.post.text_html = "<p>plain text</p>"
        self.post.save()

        rows = [
            self._make_att_row(
                1,
                200,
                physical_filename="file.jpg",
                real_filename="photo.jpg",
                mimetype="image/jpeg",
            )
        ]
        cursor = self._mock_cursor(rows, uid_rows=[(200, "")])
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_attachments", stdout=StringIO())

        self.post.refresh_from_db()
        self.assertIn('class="post-attachments"', self.post.text_html)
        self.assertIn("<img src=", self.post.text_html)


class DelTagRenderingTest(TestCase):
    def test_del_tag_renders_to_del_element(self):
        result = _to_html("[del]text[/del]", "")
        self.assertIn("<del>text</del>", result)

    def test_center_tag_renders_centered_paragraph(self):
        result = _to_html("[center]hello[/center]", "")
        self.assertIn('<p style="text-align:center">hello</p>', result)

    def test_del_tag_with_uid_stripped_and_rendered(self):
        uid = "abc12"
        result = _to_html(f"[del:{uid}]removed[/del:{uid}]", uid)
        self.assertIn("<del>removed</del>", result)
        self.assertNotIn(f":{uid}", result)
        self.assertNotIn("[del]", result)


class YoutubeTagRenderingTest(TestCase):
    def test_youtube_tag_renders_iframe(self):
        uid = "abc12"
        result = _to_html(
            f"[youtube:{uid}]https://www.youtube.com/watch?v=ABC123[/youtube:{uid}]",
            uid,
        )
        self.assertIn("<iframe", result)
        self.assertIn("https://www.youtube.com/embed/ABC123", result)
        self.assertNotIn("[youtube]", result)

    def test_youtube_youtu_be_url(self):
        uid = "abc12"
        result = _to_html(
            f"[youtube:{uid}]https://youtu.be/ABC123[/youtube:{uid}]",
            uid,
        )
        self.assertIn("https://www.youtube.com/embed/ABC123", result)

    def test_youtube_invalid_url_falls_back(self):
        result = _to_html("[youtube]not-a-url[/youtube]", "")
        self.assertNotIn("<iframe", result)
        self.assertNotIn("[youtube]", result)


class ImportPhpbbPostsBbcodeUidSavedTest(TestCase):
    def setUp(self):
        cat = ForumCategory.objects.create(id=1, phpbb_id=1, name="Категория")
        subforum = SubForum.objects.create(
            id=10, phpbb_id=10, phpbb_parent_id=1, category=cat, name="Подфорум"
        )
        self.topic = Topic.objects.create(
            id=100, phpbb_id=100, subforum=subforum, title="Тема"
        )

    def _make_row(self, post_id=200, uid="xhj7k"):
        return (post_id, 100, 0, "", "hello", uid, 1000000)

    def _mock_cursor(self, rows):
        cursor = MagicMock()
        cursor.description = [
            ("post_id",),
            ("topic_id",),
            ("poster_id",),
            ("post_username",),
            ("post_text",),
            ("bbcode_uid",),
            ("post_time",),
        ]
        cursor.fetchall.return_value = rows
        return cursor

    @patch("apps.forum_import.management.commands.import_phpbb_posts.connections")
    def test_bbcode_uid_saved_on_import(self, mock_connections):
        uid = "xhj7k"
        rows = [self._make_row(200, uid)]
        cursor = self._mock_cursor(rows)
        mock_connections.__getitem__.return_value.cursor.return_value = cursor

        call_command("import_phpbb_posts", stdout=StringIO())

        post = Post.objects.get(phpbb_id=200)
        self.assertEqual(post.bbcode_uid, uid)


class RerenderPostsCommandTest(TestCase):
    def setUp(self):
        cat = ForumCategory.objects.create(phpbb_id=1, name="Категория")
        subforum = SubForum.objects.create(
            phpbb_id=10, phpbb_parent_id=1, category=cat, name="Подфорум"
        )
        self.topic = Topic.objects.create(phpbb_id=100, subforum=subforum, title="Тема")

    def _make_post(self, phpbb_id, text_bbcode, bbcode_uid="", text_html="old"):
        return Post.objects.create(
            phpbb_id=phpbb_id,
            topic=self.topic,
            text_bbcode=text_bbcode,
            text_html=text_html,
            bbcode_uid=bbcode_uid,
        )

    def test_rerender_updates_del_tag(self):
        uid = "abc12"
        post = self._make_post(
            300,
            f"[del:{uid}]removed[/del:{uid}]",
            bbcode_uid=uid,
        )
        call_command("rerender_posts", stdout=StringIO())
        post.refresh_from_db()
        self.assertIn("<del>removed</del>", post.text_html)
        self.assertNotIn("[del]", post.text_html)

    def test_rerender_updates_youtube_tag(self):
        uid = "abc12"
        post = self._make_post(
            301,
            f"[youtube:{uid}]https://www.youtube.com/watch?v=XYZ999[/youtube:{uid}]",
            bbcode_uid=uid,
        )
        call_command("rerender_posts", stdout=StringIO())
        post.refresh_from_db()
        self.assertIn("<iframe", post.text_html)
        self.assertIn("https://www.youtube.com/embed/XYZ999", post.text_html)

    def test_rerender_preserves_attachments(self):
        uid = "abc12"
        post = self._make_post(
            302,
            f"[attachment=0:{uid}]photo.jpg[/attachment:{uid}]",
            bbcode_uid=uid,
        )
        PostAttachment.objects.create(
            phpbb_id=1,
            post=post,
            physical_filename="file.jpg",
            real_filename="photo.jpg",
            mimetype="image/jpeg",
            filesize=1024,
        )
        call_command("rerender_posts", stdout=StringIO())
        post.refresh_from_db()
        self.assertIn("<img src=", post.text_html)
        self.assertNotIn("attachment-ref", post.text_html)

    def test_rerender_uid_autodetect(self):
        uid = "xhj7k"
        post = self._make_post(
            303,
            f"[del:{uid}]old[/del:{uid}]",
            bbcode_uid="",
        )
        call_command("rerender_posts", stdout=StringIO())
        post.refresh_from_db()
        self.assertIn("<del>old</del>", post.text_html)
        self.assertNotIn(f":{uid}", post.text_html)


class PostBbcodeUidFieldTest(TestCase):
    def setUp(self):
        cat = ForumCategory.objects.create(phpbb_id=1, name="Категория")
        subforum = SubForum.objects.create(
            phpbb_id=10, phpbb_parent_id=1, category=cat, name="Подфорум"
        )
        self.topic = Topic.objects.create(phpbb_id=100, subforum=subforum, title="Тема")

    def test_post_created_with_bbcode_uid(self):
        post = Post.objects.create(
            phpbb_id=300,
            topic=self.topic,
            text_bbcode="hello",
            text_html="<p>hello</p>",
            bbcode_uid="abc12",
        )
        post.refresh_from_db()
        self.assertEqual(post.bbcode_uid, "abc12")

    def test_post_created_without_bbcode_uid_defaults_to_empty(self):
        post = Post.objects.create(
            phpbb_id=301,
            topic=self.topic,
            text_bbcode="hello",
            text_html="<p>hello</p>",
        )
        post.refresh_from_db()
        self.assertEqual(post.bbcode_uid, "")
