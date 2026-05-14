from django.contrib import admin

from .models import ForumCategory, ForumUser, SubForum

admin.site.register(ForumCategory)
admin.site.register(SubForum)
admin.site.register(ForumUser)
