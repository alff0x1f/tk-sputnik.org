from django.db.backends.mysql import base


class DatabaseWrapper(base.DatabaseWrapper):
    def check_database_version_supported(self):
        pass
