from django.db import models


class ForumCategory(models.Model):
    phpbb_id = models.IntegerField("ID в phpBB", unique=True)
    name = models.CharField("Название", max_length=255)
    description = models.TextField("Описание", blank=True)
    topic_count = models.IntegerField("Количество тем", default=0)
    post_count = models.IntegerField("Количество сообщений", default=0)
    last_post_title = models.CharField(
        "Заголовок последнего поста", max_length=255, blank=True
    )
    last_post_username = models.CharField(
        "Автор последнего поста", max_length=255, blank=True
    )
    last_post_at = models.DateTimeField("Дата последнего поста", null=True, blank=True)
    sort_order = models.IntegerField("Порядок сортировки", default=0)

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Категория форума"
        verbose_name_plural = "Категории форума"

    def __str__(self):
        return self.name


class SubForum(models.Model):
    phpbb_id = models.IntegerField("ID в phpBB", unique=True)
    phpbb_parent_id = models.IntegerField("ID родителя в phpBB")
    category = models.ForeignKey(
        ForumCategory,
        on_delete=models.CASCADE,
        related_name="subforums",
        verbose_name="Категория",
    )
    name = models.CharField("Название", max_length=255)
    description = models.TextField("Описание", blank=True)
    topic_count = models.IntegerField("Количество тем", default=0)
    post_count = models.IntegerField("Количество сообщений", default=0)
    last_post_title = models.CharField(
        "Заголовок последнего поста", max_length=255, blank=True
    )
    last_post_username = models.CharField(
        "Автор последнего поста", max_length=255, blank=True
    )
    last_post_at = models.DateTimeField("Дата последнего поста", null=True, blank=True)
    sort_order = models.IntegerField("Порядок сортировки", default=0)

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Подфорум"
        verbose_name_plural = "Подфорумы"

    def __str__(self):
        return self.name


class ForumUser(models.Model):
    phpbb_id = models.IntegerField("ID в phpBB", unique=True)
    username = models.CharField("Имя пользователя", max_length=255)
    email = models.EmailField("Email", blank=True)
    avatar = models.CharField("Аватар", max_length=500, blank=True)
    registered_at = models.DateTimeField("Дата регистрации", null=True, blank=True)
    post_count = models.IntegerField("Количество сообщений", default=0)

    class Meta:
        verbose_name = "Пользователь форума"
        verbose_name_plural = "Пользователи форума"

    def __str__(self):
        return self.username
