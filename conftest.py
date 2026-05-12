import pytest


@pytest.fixture(scope="session")
def django_db_modify_db_settings():
    from django.conf import settings
    from django.db import connections

    # Replace MySQL phpbb database with SQLite during tests — mysqlclient not installed
    settings.DATABASES["phpbb"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
    # Clear cached connections.settings so configure_settings re-runs and adds
    # required TEST subkeys (MIRROR, CHARSET, etc.) to our new phpbb entry.
    if "settings" in connections.__dict__:
        del connections.__dict__["settings"]
    if hasattr(connections._connections, "phpbb"):
        delattr(connections._connections, "phpbb")
