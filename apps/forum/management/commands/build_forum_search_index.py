from django.core.management.base import BaseCommand

from apps.forum.search import rebuild_search_index


class Command(BaseCommand):
    help = "Build PostgreSQL full-text search index for forum posts"

    def handle(self, *args, **options):
        self.stdout.write("Building forum search index...")
        count = rebuild_search_index()
        self.stdout.write(self.style.SUCCESS(f"Updated {count} posts"))
