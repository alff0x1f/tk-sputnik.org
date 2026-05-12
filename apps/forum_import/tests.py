from django.conf import settings
from django.test import TestCase


class ForumImportAppConfigTest(TestCase):
    def test_app_registered_in_installed_apps(self):
        self.assertIn("apps.forum_import", settings.INSTALLED_APPS)
