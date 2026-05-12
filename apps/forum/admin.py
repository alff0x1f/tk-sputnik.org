from django.contrib import admin

from .models import ForumCategory, SubForum

admin.site.register(ForumCategory)
admin.site.register(SubForum)
