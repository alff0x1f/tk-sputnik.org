from django.conf import settings
from django.test import TestCase


class PhpbbDatabaseSettingsTests(TestCase):
    def test_phpbb_database_configured(self):
        self.assertIn("phpbb", settings.DATABASES)

    def test_phpbb_engine_is_mysql(self):
        self.assertEqual(
            settings.DATABASES["phpbb"]["ENGINE"],
            "django.db.backends.mysql",
        )
