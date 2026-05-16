from datetime import UTC, datetime
from io import StringIO
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from apps.forum.models import ForumCategory, ForumUser, Post, SubForum, Topic
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


class ToHtmlSmiliesMarkersTest(TestCase):
    def test_smiley_renders_to_img_tag(self):
        raw = '<!-- s:) --><img src="{SMILIES_PATH}/smile.gif" alt=":)" title="Smile" /><!-- s:) -->'
        result = _to_html(raw, "")
        self.assertIn('<img src="/media/forum/smilies/smile.gif"', result)
        self.assertIn('alt=":)"', result)
        self.assertNotIn("{SMILIES_PATH}", result)
        self.assertNotIn("<!-- s", result)

    def test_url_marker_renders_with_rel_nofollow(self):
        raw = '<!-- m --><a class="postlink" href="https://example.com">text</a><!-- m -->'
        result = _to_html(raw, "")
        self.assertIn('href="https://example.com"', result)
        self.assertIn('rel="nofollow"', result)
        self.assertIn(">text<", result)
        self.assertNotIn("<!-- m -->", result)

    def test_email_marker_renders_with_rel_nofollow(self):
        raw = '<!-- e --><a href="mailto:user@example.com">user@example.com</a><!-- e -->'
        result = _to_html(raw, "")
        self.assertIn('href="mailto:user@example.com"', result)
        self.assertIn('rel="nofollow"', result)
        self.assertNotIn("<!-- e -->", result)

    def test_multiple_smileys_all_rendered(self):
        raw = (
            '<!-- s:) --><img src="{SMILIES_PATH}/smile.gif" alt=":)" title="Smile" /><!-- s:) -->'
            " and "
            '<!-- s:D --><img src="{SMILIES_PATH}/grin.gif" alt=":D" title="Grin" /><!-- s:D -->'
        )
        result = _to_html(raw, "")
        self.assertIn("/media/forum/smilies/smile.gif", result)
        self.assertIn("/media/forum/smilies/grin.gif", result)
        self.assertNotIn("{SMILIES_PATH}", result)
        self.assertEqual(result.count("<img"), 2)

    def test_bbcode_and_smiley_mixed(self):
        raw = '[b]hello[/b] <!-- s:) --><img src="{SMILIES_PATH}/smile.gif" alt=":)" title="Smile" /><!-- s:) -->'
        result = _to_html(raw, "")
        self.assertIn("<strong>hello</strong>", result)
        self.assertIn("/media/forum/smilies/smile.gif", result)
        self.assertNotIn("{SMILIES_PATH}", result)
        self.assertNotIn("<!-- s", result)
