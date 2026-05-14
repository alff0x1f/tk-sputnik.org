from datetime import datetime, timezone

from django.test import TestCase
from django.urls import reverse

from .models import ForumCategory, ForumUser, Post, SubForum, Topic


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


class ForumIndexViewTests(TestCase):
    def setUp(self):
        self.cat1 = ForumCategory.objects.create(
            phpbb_id=1, name="Приключения", sort_order=1
        )
        self.cat2 = ForumCategory.objects.create(
            phpbb_id=2, name="Велосипед", sort_order=2
        )
        SubForum.objects.create(
            phpbb_id=10, phpbb_parent_id=1, category=self.cat1, name="Горные походы"
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
        cat1 = next(c for c in categories if c.phpbb_id == 1)
        self.assertEqual(cat1.subforums.count(), 1)

    def test_forum_index_uses_correct_template(self):
        response = self.client.get(reverse("forum-index"))
        self.assertTemplateUsed(response, "forum/forum.html")


class SubforumTopicsViewTest(TestCase):
    def setUp(self):
        self.category = ForumCategory.objects.create(phpbb_id=1, name="Cat", sort_order=1)
        self.subforum = SubForum.objects.create(
            phpbb_id=42, phpbb_parent_id=1, category=self.category, name="Походы"
        )
        self.other_subforum = SubForum.objects.create(
            phpbb_id=99, phpbb_parent_id=1, category=self.category, name="Other"
        )
        self.topic = Topic.objects.create(
            phpbb_id=1000,
            subforum=self.subforum,
            title="Эльбрус 2010",
            created_at=datetime(2010, 6, 1, tzinfo=timezone.utc),
        )
        self.other_topic = Topic.objects.create(
            phpbb_id=2000,
            subforum=self.other_subforum,
            title="Other topic",
            created_at=datetime(2010, 7, 1, tzinfo=timezone.utc),
        )

    def test_returns_200(self):
        url = reverse("subforum-topics", kwargs={"phpbb_id": 42})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_uses_correct_template(self):
        url = reverse("subforum-topics", kwargs={"phpbb_id": 42})
        response = self.client.get(url)
        self.assertTemplateUsed(response, "forum/subforum.html")

    def test_404_for_unknown_phpbb_id(self):
        url = reverse("subforum-topics", kwargs={"phpbb_id": 9999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_context_has_page_obj_with_correct_topics(self):
        url = reverse("subforum-topics", kwargs={"phpbb_id": 42})
        response = self.client.get(url)
        self.assertIn("page_obj", response.context)
        topic_ids = [t.phpbb_id for t in response.context["page_obj"].object_list]
        self.assertIn(1000, topic_ids)
        self.assertNotIn(2000, topic_ids)

    def test_pagination_page1_has_25_topics(self):
        for i in range(1, 26):
            Topic.objects.create(
                phpbb_id=3000 + i,
                subforum=self.subforum,
                title=f"Topic {i}",
                created_at=datetime(2011, 1, i, tzinfo=timezone.utc),
            )
        url = reverse("subforum-topics", kwargs={"phpbb_id": 42})
        response = self.client.get(url)
        self.assertEqual(len(response.context["page_obj"].object_list), 25)

    def test_pagination_page2_has_remaining_topics(self):
        for i in range(1, 26):
            Topic.objects.create(
                phpbb_id=3000 + i,
                subforum=self.subforum,
                title=f"Topic {i}",
                created_at=datetime(2011, 1, i, tzinfo=timezone.utc),
            )
        url = reverse("subforum-topics", kwargs={"phpbb_id": 42})
        response = self.client.get(url + "?page=2")
        self.assertEqual(len(response.context["page_obj"].object_list), 1)
