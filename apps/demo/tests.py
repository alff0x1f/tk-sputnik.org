from django.test import TestCase
from django.urls import reverse


class IndexViewTests(TestCase):
    def test_returns_200(self):
        self.assertEqual(self.client.get(reverse("demo-index")).status_code, 200)

    def test_uses_correct_template(self):
        self.assertTemplateUsed(
            self.client.get(reverse("demo-index")), "demo/index.html"
        )


class ForumViewTests(TestCase):
    def test_returns_200(self):
        self.assertEqual(self.client.get(reverse("demo-forum")).status_code, 200)

    def test_uses_correct_template(self):
        self.assertTemplateUsed(
            self.client.get(reverse("demo-forum")), "demo/forum.html"
        )


class MembersViewTests(TestCase):
    def test_returns_200(self):
        self.assertEqual(self.client.get(reverse("demo-members")).status_code, 200)

    def test_uses_correct_template(self):
        self.assertTemplateUsed(
            self.client.get(reverse("demo-members")), "demo/members.html"
        )
