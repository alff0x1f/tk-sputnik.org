from django.test import TestCase

from .models import ForumCategory, SubForum


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
