import pytest


@pytest.fixture(autouse=True)
def use_plain_static_storage(settings):
    settings.STORAGES = {
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        }
    }
