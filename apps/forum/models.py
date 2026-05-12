from django.db import models


class ForumCategory(models.Model):
    phpbb_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    topic_count = models.IntegerField(default=0)
    post_count = models.IntegerField(default=0)
    last_post_title = models.CharField(max_length=255, blank=True)
    last_post_username = models.CharField(max_length=255, blank=True)
    last_post_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self):
        return self.name


class SubForum(models.Model):
    phpbb_id = models.IntegerField(unique=True)
    phpbb_parent_id = models.IntegerField()
    category = models.ForeignKey(
        ForumCategory, on_delete=models.CASCADE, related_name="subforums"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    topic_count = models.IntegerField(default=0)
    post_count = models.IntegerField(default=0)
    last_post_title = models.CharField(max_length=255, blank=True)
    last_post_username = models.CharField(max_length=255, blank=True)
    last_post_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self):
        return self.name
