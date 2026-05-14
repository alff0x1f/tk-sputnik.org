from django.contrib import admin

from .models import ForumCategory, ForumUser, Post, SubForum, Topic

admin.site.register(ForumCategory)
admin.site.register(SubForum)
admin.site.register(ForumUser)


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ["title", "subforum", "post_count", "created_at"]


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["phpbb_id", "topic", "author_username", "created_at"]
