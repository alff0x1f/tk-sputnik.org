import datetime
import pathlib
import tempfile

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import ForumCategory, ForumUser, Post, PostAttachment, SubForum, Topic


class ForumCategoryModelTests(TestCase):
    def test_create_category(self):
        cat = ForumCategory.objects.create(phpbb_id=1, name="Приключения", sort_order=1)
        self.assertEqual(ForumCategory.objects.count(), 1)
        self.assertEqual(str(cat), "Приключения")

    def test_category_defaults(self):
        cat = ForumCategory.objects.create(phpbb_id=2, name="Test")
        self.assertEqual(cat.topic_count, 0)
        self.assertEqual(cat.post_count, 0)
        self.assertIsNone(cat.last_post_at)


class SubForumModelTests(TestCase):
    def setUp(self):
        self.category = ForumCategory.objects.create(
            phpbb_id=10, name="Велосипед", sort_order=2
        )

    def test_create_subforum(self):
        sub = SubForum.objects.create(
            phpbb_id=100,
            phpbb_parent_id=10,
            category=self.category,
            name="Походы",
            sort_order=1,
        )
        self.assertEqual(SubForum.objects.count(), 1)
        self.assertEqual(str(sub), "Походы")

    def test_subforum_fk(self):
        SubForum.objects.create(
            phpbb_id=101,
            phpbb_parent_id=10,
            category=self.category,
            name="Велопоходы",
        )
        self.assertEqual(self.category.subforums.count(), 1)

    def test_nested_subforum_has_root_category(self):
        nested = SubForum.objects.create(
            phpbb_id=102,
            phpbb_parent_id=100,
            category=self.category,
            name="Горные велопоходы",
        )
        self.assertEqual(nested.category, self.category)

    def test_subforum_private_defaults(self):
        sub = SubForum.objects.create(
            phpbb_id=103,
            phpbb_parent_id=10,
            category=self.category,
            name="Открытый",
        )
        self.assertFalse(sub.is_private)
        self.assertIsNone(sub.allowed_group)


class ForumUserModelTests(TestCase):
    def test_create_and_retrieve(self):
        user = ForumUser.objects.create(phpbb_id=42, username="Турист")
        retrieved = ForumUser.objects.get(phpbb_id=42)
        self.assertEqual(retrieved.username, "Турист")
        self.assertEqual(str(user), "Турист")

    def test_defaults(self):
        user = ForumUser.objects.create(phpbb_id=99, username="test")
        self.assertEqual(user.post_count, 0)
        self.assertEqual(user.email, "")
        self.assertEqual(user.avatar, "")
        self.assertIsNone(user.registered_at)

    def test_avatar_url_empty(self):
        user = ForumUser(avatar="")
        self.assertEqual(user.avatar_url, "")

    def test_avatar_url_local(self):
        user = ForumUser(avatar="168.jpg")
        self.assertIn("/forum/avatars/168.jpg", user.avatar_url)
        self.assertTrue(user.avatar_url.startswith("/media/"))

    def test_avatar_url_timestamp_format(self):
        user = ForumUser(avatar="5_1316512958.jpg")
        self.assertIn("/forum/avatars/5.jpg", user.avatar_url)

    def test_avatar_url_remote(self):
        url = "https://example.com/avatar.jpg"
        user = ForumUser(avatar=url)
        self.assertEqual(user.avatar_url, url)


class TopicModelTests(TestCase):
    def setUp(self):
        self.category = ForumCategory.objects.create(phpbb_id=1, name="Cat")
        self.subforum = SubForum.objects.create(
            phpbb_id=10, phpbb_parent_id=1, category=self.category, name="Sub"
        )

    def test_topic_str(self):
        topic = Topic.objects.create(
            phpbb_id=100, subforum=self.subforum, title="Поход на Эльбрус"
        )
        self.assertEqual(str(topic), "Поход на Эльбрус")

    def test_topic_defaults(self):
        topic = Topic.objects.create(phpbb_id=101, subforum=self.subforum, title="Test")
        self.assertEqual(topic.views, 0)
        self.assertEqual(topic.post_count, 0)
        self.assertIsNone(topic.created_at)

    def test_topic_related_name(self):
        Topic.objects.create(phpbb_id=102, subforum=self.subforum, title="A")
        Topic.objects.create(phpbb_id=103, subforum=self.subforum, title="B")
        self.assertEqual(self.subforum.topics.count(), 2)


class PostModelTests(TestCase):
    def setUp(self):
        self.category = ForumCategory.objects.create(phpbb_id=1, name="Cat")
        self.subforum = SubForum.objects.create(
            phpbb_id=10, phpbb_parent_id=1, category=self.category, name="Sub"
        )
        self.topic = Topic.objects.create(
            phpbb_id=100, subforum=self.subforum, title="Topic"
        )
        self.user = ForumUser.objects.create(phpbb_id=42, username="Турист")

    def test_post_str(self):
        post = Post.objects.create(
            phpbb_id=1000,
            topic=self.topic,
            author=self.user,
            text_bbcode="[b]text[/b]",
            text_html="<b>text</b>",
        )
        self.assertIn("1000", str(post))

    def test_post_author_nullable(self):
        post = Post.objects.create(
            phpbb_id=1001,
            topic=self.topic,
            author=None,
            author_username="anonymous",
            text_bbcode="hello",
            text_html="hello",
        )
        self.assertIsNone(post.author)
        self.assertEqual(post.author_username, "anonymous")

    def test_post_related_name(self):
        Post.objects.create(
            phpbb_id=1002, topic=self.topic, text_bbcode="a", text_html="a"
        )
        self.assertEqual(self.topic.posts.count(), 1)

    def test_user_set_null_on_delete(self):
        post = Post.objects.create(
            phpbb_id=1003,
            topic=self.topic,
            author=self.user,
            text_bbcode="x",
            text_html="x",
        )
        self.user.delete()
        post.refresh_from_db()
        self.assertIsNone(post.author)


class PostAttachmentModelTests(TestCase):
    def setUp(self):
        self.category = ForumCategory.objects.create(phpbb_id=1, name="Cat")
        self.subforum = SubForum.objects.create(
            phpbb_id=10, phpbb_parent_id=1, category=self.category, name="Sub"
        )
        self.topic = Topic.objects.create(
            phpbb_id=100, subforum=self.subforum, title="T"
        )
        self.post = Post.objects.create(
            phpbb_id=1000, topic=self.topic, text_bbcode="x", text_html="x"
        )

    def _make_attachment(
        self, phpbb_id=1, physical_filename="abc.jpg", mimetype="image/jpeg"
    ):
        return PostAttachment(
            phpbb_id=phpbb_id,
            post=self.post,
            physical_filename=physical_filename,
            real_filename="photo.jpg",
            mimetype=mimetype,
        )

    def test_postattachment_url_property(self):
        att = PostAttachment.objects.create(
            phpbb_id=1,
            post=self.post,
            physical_filename="somefile_123.jpg",
            real_filename="photo.jpg",
            mimetype="image/jpeg",
        )
        self.assertEqual(att.url, f"/forum/a/{att.pk}/")

    def test_postattachment_is_image_true(self):
        att = self._make_attachment(mimetype="image/jpeg")
        self.assertTrue(att.is_image)

    def test_postattachment_is_image_false_for_pdf(self):
        att = self._make_attachment(mimetype="application/pdf")
        self.assertFalse(att.is_image)

    def test_postattachment_is_image_false_for_empty_mimetype(self):
        att = self._make_attachment(mimetype="")
        self.assertFalse(att.is_image)

    def test_postattachment_ordering_by_phpbb_id(self):
        PostAttachment.objects.create(
            phpbb_id=30,
            post=self.post,
            physical_filename="c.jpg",
            real_filename="c.jpg",
            mimetype="image/jpeg",
        )
        PostAttachment.objects.create(
            phpbb_id=10,
            post=self.post,
            physical_filename="a.jpg",
            real_filename="a.jpg",
            mimetype="image/jpeg",
        )
        PostAttachment.objects.create(
            phpbb_id=20,
            post=self.post,
            physical_filename="b.jpg",
            real_filename="b.jpg",
            mimetype="image/jpeg",
        )
        ids = list(PostAttachment.objects.values_list("phpbb_id", flat=True))
        self.assertEqual(ids, [10, 20, 30])


class ForumIndexViewTests(TestCase):
    def setUp(self):
        self.cat1 = ForumCategory.objects.create(
            id=1, phpbb_id=1, name="Приключения", sort_order=1
        )
        self.cat2 = ForumCategory.objects.create(
            id=2, phpbb_id=2, name="Велосипед", sort_order=2
        )
        SubForum.objects.create(
            id=10,
            phpbb_id=10,
            phpbb_parent_id=1,
            category=self.cat1,
            name="Горные походы",  # noqa: E501
        )

    def test_forum_index_returns_200(self):
        response = self.client.get(reverse("forum-index"))
        self.assertEqual(response.status_code, 200)

    def test_forum_index_context_has_categories(self):
        response = self.client.get(reverse("forum-index"))
        self.assertIn("categories", response.context)

    def test_forum_index_categories_count(self):
        response = self.client.get(reverse("forum-index"))
        self.assertEqual(len(response.context["categories"]), 2)

    def test_forum_index_categories_have_subforums(self):
        response = self.client.get(reverse("forum-index"))
        categories = list(response.context["categories"])
        cat1 = next(c for c in categories if c.id == 1)
        self.assertEqual(cat1.subforums.count(), 1)

    def test_forum_index_uses_correct_template(self):
        response = self.client.get(reverse("forum-index"))
        self.assertTemplateUsed(response, "forum/forum.html")

    def test_forum_index_context_has_user_group_ids(self):
        response = self.client.get(reverse("forum-index"))
        self.assertIn("user_group_ids", response.context)
        self.assertIsInstance(response.context["user_group_ids"], set)

    def test_forum_index_context_has_user_is_staff(self):
        response = self.client.get(reverse("forum-index"))
        self.assertIn("user_is_staff", response.context)
        self.assertFalse(response.context["user_is_staff"])


class SubforumTopicsViewTest(TestCase):
    def setUp(self):
        self.category = ForumCategory.objects.create(
            id=1, phpbb_id=1, name="Cat", sort_order=1
        )
        self.subforum = SubForum.objects.create(
            id=42, phpbb_id=42, phpbb_parent_id=1, category=self.category, name="Походы"
        )
        self.other_subforum = SubForum.objects.create(
            id=99, phpbb_id=99, phpbb_parent_id=1, category=self.category, name="Other"
        )
        self.topic = Topic.objects.create(
            id=1000,
            phpbb_id=1000,
            subforum=self.subforum,
            title="Эльбрус 2010",
            created_at=datetime.datetime(2010, 6, 1, tzinfo=datetime.UTC),
        )
        self.other_topic = Topic.objects.create(
            id=2000,
            phpbb_id=2000,
            subforum=self.other_subforum,
            title="Other topic",
            created_at=datetime.datetime(2010, 7, 1, tzinfo=datetime.UTC),
        )

    def test_returns_200(self):
        url = reverse("subforum-topics", kwargs={"pk": 42})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_uses_correct_template(self):
        url = reverse("subforum-topics", kwargs={"pk": 42})
        response = self.client.get(url)
        self.assertTemplateUsed(response, "forum/subforum.html")

    def test_404_for_unknown_id(self):
        url = reverse("subforum-topics", kwargs={"pk": 9999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_context_has_page_obj_with_correct_topics(self):
        url = reverse("subforum-topics", kwargs={"pk": 42})
        response = self.client.get(url)
        self.assertIn("page_obj", response.context)
        topic_ids = [t.id for t in response.context["page_obj"].object_list]
        self.assertIn(1000, topic_ids)
        self.assertNotIn(2000, topic_ids)

    def test_pagination_page1_has_25_topics(self):
        for i in range(1, 26):
            Topic.objects.create(
                id=3000 + i,
                phpbb_id=3000 + i,
                subforum=self.subforum,
                title=f"Topic {i}",
                created_at=datetime.datetime(2011, 1, i, tzinfo=datetime.UTC),
            )
        url = reverse("subforum-topics", kwargs={"pk": 42})
        response = self.client.get(url)
        self.assertEqual(len(response.context["page_obj"].object_list), 25)

    def test_pagination_page2_has_remaining_topics(self):
        for i in range(1, 26):
            Topic.objects.create(
                id=3000 + i,
                phpbb_id=3000 + i,
                subforum=self.subforum,
                title=f"Topic {i}",
                created_at=datetime.datetime(2011, 1, i, tzinfo=datetime.UTC),
            )
        url = reverse("subforum-topics", kwargs={"pk": 42})
        response = self.client.get(url + "?page=2")
        self.assertEqual(len(response.context["page_obj"].object_list), 1)


class TopicPostsViewTest(TestCase):
    def setUp(self):
        self.category = ForumCategory.objects.create(
            id=1, phpbb_id=1, name="Cat", sort_order=1
        )
        self.subforum = SubForum.objects.create(
            id=10, phpbb_id=10, phpbb_parent_id=1, category=self.category, name="Sub"
        )
        self.topic = Topic.objects.create(
            id=500, phpbb_id=500, subforum=self.subforum, title="Поход на Алтай"
        )
        self.other_topic = Topic.objects.create(
            id=600, phpbb_id=600, subforum=self.subforum, title="Other"
        )
        self.user = ForumUser.objects.create(id=7, phpbb_id=7, username="Иван")
        self.post = Post.objects.create(
            id=9001,
            phpbb_id=9001,
            topic=self.topic,
            author=self.user,
            text_bbcode="hello",
            text_html="<p>hello</p>",
            created_at=datetime.datetime(2010, 8, 1, tzinfo=datetime.UTC),
        )
        self.other_post = Post.objects.create(
            id=9002,
            phpbb_id=9002,
            topic=self.other_topic,
            author=self.user,
            text_bbcode="other",
            text_html="<p>other</p>",
            created_at=datetime.datetime(2010, 8, 2, tzinfo=datetime.UTC),
        )

    def _url(self, pk=500):
        return reverse("topic-posts", kwargs={"pk": pk})

    def test_returns_200(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    def test_404_for_unknown_id(self):
        response = self.client.get(self._url(pk=9999))
        self.assertEqual(response.status_code, 404)

    def test_uses_correct_template(self):
        response = self.client.get(self._url())
        self.assertTemplateUsed(response, "forum/topic.html")

    def test_context_has_topic_and_page_obj(self):
        response = self.client.get(self._url())
        self.assertIn("topic", response.context)
        self.assertIn("page_obj", response.context)
        self.assertEqual(response.context["topic"].id, 500)

    def test_page_obj_contains_only_topic_posts(self):
        response = self.client.get(self._url())
        ids = [p.id for p in response.context["page_obj"].object_list]
        self.assertIn(9001, ids)
        self.assertNotIn(9002, ids)

    def test_pagination_20_per_page(self):
        for i in range(1, 22):
            Post.objects.create(
                id=10000 + i,
                phpbb_id=10000 + i,
                topic=self.topic,
                text_bbcode="x",
                text_html="<p>x</p>",
                created_at=datetime.datetime(2010, 9, 1, tzinfo=datetime.UTC),
            )
        response = self.client.get(self._url())
        self.assertEqual(len(response.context["page_obj"].object_list), 20)
        response2 = self.client.get(self._url() + "?page=2")
        self.assertEqual(len(response2.context["page_obj"].object_list), 2)


class TopicPostsHtmxTest(TestCase):
    def setUp(self):
        self.category = ForumCategory.objects.create(
            id=1, phpbb_id=1, name="Cat", sort_order=1
        )
        self.subforum = SubForum.objects.create(
            id=10, phpbb_id=10, phpbb_parent_id=1, category=self.category, name="Sub"
        )
        self.topic = Topic.objects.create(
            id=700, phpbb_id=700, subforum=self.subforum, title="Htmx Topic"
        )
        for i in range(1, 22):
            Post.objects.create(
                id=20000 + i,
                phpbb_id=20000 + i,
                topic=self.topic,
                text_bbcode="x",
                text_html=f"<p>post {i}</p>",
                created_at=datetime.datetime(2010, 9, 1, tzinfo=datetime.UTC),
            )

    def _url(self):
        return reverse("topic-posts", kwargs={"pk": 700})

    def test_normal_get_uses_full_template(self):
        response = self.client.get(self._url())
        self.assertTemplateUsed(response, "forum/topic.html")

    def test_htmx_get_uses_partial_template(self):
        response = self.client.get(self._url(), HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(response, "forum/topic_posts_partial.html")

    def test_partial_contains_page_block_not_html_tag(self):
        response = self.client.get(self._url(), HTTP_HX_REQUEST="true")
        self.assertContains(response, "page-block")
        self.assertNotContains(response, "<html")

    def test_partial_last_page_has_no_sentinel(self):
        response = self.client.get(self._url() + "?page=2", HTTP_HX_REQUEST="true")
        self.assertNotContains(response, 'class="sentinel"')

    def test_partial_non_last_page_has_sentinel(self):
        response = self.client.get(self._url(), HTTP_HX_REQUEST="true")
        self.assertContains(response, 'class="sentinel"')

    def test_vary_header_on_normal_response(self):
        response = self.client.get(self._url())
        self.assertIn("HX-Request", response.get("Vary", ""))

    def test_vary_header_on_partial_response(self):
        response = self.client.get(self._url(), HTTP_HX_REQUEST="true")
        self.assertIn("HX-Request", response.get("Vary", ""))


class SubforumTopicsAccessControlTest(TestCase):
    def setUp(self):
        self.group = Group.objects.create(name="орг")
        self.category = ForumCategory.objects.create(
            phpbb_id=1, name="Cat", sort_order=1
        )
        self.private_subforum = SubForum.objects.create(
            id=19,
            phpbb_id=19,
            phpbb_parent_id=1,
            category=self.category,
            name="Орг",
            is_private=True,
            allowed_group=self.group,
        )
        self.topic = Topic.objects.create(
            phpbb_id=200, subforum=self.private_subforum, title="Private Topic"
        )
        self.url = reverse("subforum-topics", kwargs={"pk": 19})

    def test_anonymous_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_logged_in_without_group_gets_403(self):
        User.objects.create_user(username="nogroup", password="pass")
        self.client.login(username="nogroup", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_logged_in_with_group_gets_200(self):
        user = User.objects.create_user(username="member", password="pass")
        user.groups.add(self.group)
        self.client.login(username="member", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_staff_gets_200_without_group(self):
        User.objects.create_user(username="admin", password="pass", is_staff=True)
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_public_subforum_accessible_to_anonymous(self):
        SubForum.objects.create(
            id=20, phpbb_id=20, phpbb_parent_id=1, category=self.category, name="Public"
        )
        url = reverse("subforum-topics", kwargs={"pk": 20})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class TopicPostsAccessControlTest(TestCase):
    def setUp(self):
        self.group = Group.objects.create(name="орг")
        self.category = ForumCategory.objects.create(
            phpbb_id=1, name="Cat", sort_order=1
        )
        self.private_subforum = SubForum.objects.create(
            id=19,
            phpbb_id=19,
            phpbb_parent_id=1,
            category=self.category,
            name="Орг",
            is_private=True,
            allowed_group=self.group,
        )
        self.topic = Topic.objects.create(
            id=300, phpbb_id=300, subforum=self.private_subforum, title="Private Topic"
        )
        self.url = reverse("topic-posts", kwargs={"pk": 300})

    def test_anonymous_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_logged_in_without_group_gets_403(self):
        User.objects.create_user(username="nogroup", password="pass")
        self.client.login(username="nogroup", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_logged_in_with_group_gets_200(self):
        user = User.objects.create_user(username="member", password="pass")
        user.groups.add(self.group)
        self.client.login(username="member", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_staff_gets_200_without_group(self):
        User.objects.create_user(username="admin", password="pass", is_staff=True)
        self.client.login(username="admin", password="pass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_public_subforum_topic_accessible_to_anonymous(self):
        public = SubForum.objects.create(
            id=20, phpbb_id=20, phpbb_parent_id=1, category=self.category, name="Public"
        )
        Topic.objects.create(
            id=400, phpbb_id=400, subforum=public, title="Public Topic"
        )
        url = reverse("topic-posts", kwargs={"pk": 400})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class ForumIndexContextTest(TestCase):
    def setUp(self):
        self.category = ForumCategory.objects.create(
            phpbb_id=1, name="Cat", sort_order=1
        )

    def test_context_has_user_group_ids_anonymous(self):
        response = self.client.get(reverse("forum-index"))
        self.assertIn("user_group_ids", response.context)
        self.assertEqual(response.context["user_group_ids"], set())

    def test_context_has_user_group_ids_for_logged_in_user(self):
        group = Group.objects.create(name="test_group")
        user = User.objects.create_user(username="tester", password="pass")
        user.groups.add(group)
        self.client.login(username="tester", password="pass")
        response = self.client.get(reverse("forum-index"))
        self.assertIn("user_group_ids", response.context)
        self.assertIn(group.id, response.context["user_group_ids"])

    def test_private_child_subforum_shows_lock_for_anonymous(self):
        group = Group.objects.create(name="secret")
        cat = ForumCategory.objects.create(
            id=50, phpbb_id=50, name="TestCat", sort_order=1
        )
        SubForum.objects.create(
            id=60, phpbb_id=60, phpbb_parent_id=50, category=cat, name="ParentSub"
        )
        SubForum.objects.create(
            id=61,
            phpbb_id=61,
            phpbb_parent_id=60,
            category=cat,
            name="PrivateChild",
            is_private=True,
            allowed_group=group,
        )
        response = self.client.get(reverse("forum-index"))
        self.assertContains(response, "sf-lock")


class ServeAttachmentViewTest(TestCase):
    def setUp(self):
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir_obj.cleanup)
        self.tmp_dir = self.tmp_dir_obj.name
        self.group = Group.objects.create(name="members")
        self.category = ForumCategory.objects.create(
            phpbb_id=1, name="Cat", sort_order=1
        )
        self.public_subforum = SubForum.objects.create(
            id=10, phpbb_id=10, phpbb_parent_id=1, category=self.category, name="Public"
        )
        self.private_subforum = SubForum.objects.create(
            id=20,
            phpbb_id=20,
            phpbb_parent_id=1,
            category=self.category,
            name="Private",
            is_private=True,
            allowed_group=self.group,
        )
        self.public_topic = Topic.objects.create(
            id=100, phpbb_id=100, subforum=self.public_subforum, title="Public Topic"
        )
        self.private_topic = Topic.objects.create(
            id=200, phpbb_id=200, subforum=self.private_subforum, title="Private Topic"
        )
        self.public_post = Post.objects.create(
            id=1000,
            phpbb_id=1000,
            topic=self.public_topic,
            text_bbcode="x",
            text_html="x",
        )
        self.private_post = Post.objects.create(
            id=2000,
            phpbb_id=2000,
            topic=self.private_topic,
            text_bbcode="x",
            text_html="x",
        )

    def _make_attachment(
        self, post, phpbb_id, physical_filename, real_filename, mimetype
    ):
        att = PostAttachment.objects.create(
            phpbb_id=phpbb_id,
            post=post,
            physical_filename=physical_filename,
            real_filename=real_filename,
            mimetype=mimetype,
        )
        attachments_dir = pathlib.Path(self.tmp_dir) / "forum" / "attachments"
        attachments_dir.mkdir(parents=True, exist_ok=True)
        (attachments_dir / physical_filename).write_bytes(b"dummy content")
        return att

    def test_public_subforum_anonymous_gets_file(self):
        att = self._make_attachment(
            self.public_post, 1, "16_abc123", "report.pdf", "application/pdf"
        )
        with override_settings(MEDIA_ROOT=pathlib.Path(self.tmp_dir)):
            url = reverse("forum-attachment", kwargs={"pk": att.pk})
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn('filename="report.pdf"', response["Content-Disposition"])

    def test_public_subforum_anonymous_gets_correct_content_type(self):
        att = self._make_attachment(
            self.public_post, 2, "17_def456", "photo.jpg", "image/jpeg"
        )
        with override_settings(MEDIA_ROOT=pathlib.Path(self.tmp_dir)):
            url = reverse("forum-attachment", kwargs={"pk": att.pk})
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")

    def test_private_subforum_anonymous_redirects_to_login(self):
        att = self._make_attachment(
            self.private_post, 3, "18_ghi789", "secret.doc", "application/msword"
        )
        with override_settings(MEDIA_ROOT=pathlib.Path(self.tmp_dir)):
            url = reverse("forum-attachment", kwargs={"pk": att.pk})
            response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_private_subforum_non_member_gets_403(self):
        att = self._make_attachment(
            self.private_post, 4, "19_jkl012", "secret.doc", "application/msword"
        )
        User.objects.create_user(username="nogroup", password="pass")
        self.client.login(username="nogroup", password="pass")
        with override_settings(MEDIA_ROOT=pathlib.Path(self.tmp_dir)):
            url = reverse("forum-attachment", kwargs={"pk": att.pk})
            response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_private_subforum_member_gets_file(self):
        att = self._make_attachment(
            self.private_post, 5, "20_mno345", "members_only.pdf", "application/pdf"
        )
        user = User.objects.create_user(username="member", password="pass")
        user.groups.add(self.group)
        self.client.login(username="member", password="pass")
        with override_settings(MEDIA_ROOT=pathlib.Path(self.tmp_dir)):
            url = reverse("forum-attachment", kwargs={"pk": att.pk})
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('filename="members_only.pdf"', response["Content-Disposition"])

    def test_private_subforum_staff_gets_file(self):
        att = self._make_attachment(
            self.private_post, 6, "21_pqr678", "admin_file.pdf", "application/pdf"
        )
        User.objects.create_user(username="admin", password="pass", is_staff=True)
        self.client.login(username="admin", password="pass")
        with override_settings(MEDIA_ROOT=pathlib.Path(self.tmp_dir)):
            url = reverse("forum-attachment", kwargs={"pk": att.pk})
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_nonexistent_pk_gets_404(self):
        url = reverse("forum-attachment", kwargs={"pk": 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_no_mimetype_falls_back_to_octet_stream(self):
        att = self._make_attachment(
            self.public_post, 7, "22_stu901", "unknown_file", ""
        )
        with override_settings(MEDIA_ROOT=pathlib.Path(self.tmp_dir)):
            url = reverse("forum-attachment", kwargs={"pk": att.pk})
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/octet-stream")
