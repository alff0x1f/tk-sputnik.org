from django.db import models


class ForumCategory(models.Model):
    phpbb_id = models.IntegerField("ID в phpBB", unique=True, null=True, blank=True)
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
    phpbb_id = models.IntegerField("ID в phpBB", unique=True, null=True, blank=True)
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
    is_private = models.BooleanField("Приватный", default=False)
    allowed_group = models.ForeignKey(
        "auth.Group",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Группа доступа",
        related_name="private_subforums",
    )

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Подфорум"
        verbose_name_plural = "Подфорумы"

    def __str__(self):
        return self.name


class ForumUser(models.Model):
    phpbb_id = models.IntegerField("ID в phpBB", unique=True, null=True, blank=True)
    username = models.CharField("Имя пользователя", max_length=255)
    email = models.EmailField("Email", blank=True)
    avatar = models.CharField("Аватар", max_length=500, blank=True)
    registered_at = models.DateTimeField("Дата регистрации", null=True, blank=True)
    post_count = models.IntegerField("Количество сообщений", default=0)

    @property
    def avatar_url(self):
        if not self.avatar:
            return ""
        if self.avatar.startswith(("http://", "https://")):
            return self.avatar
        import re

        from django.conf import settings

        # phpBB stored "5_1316512958.jpg" in DB but renamed file on disk to "5.jpg"
        filename = re.sub(r"^(\d+)_\d+(\.\w+)$", r"\1\2", self.avatar)
        return f"{settings.MEDIA_URL}forum/avatars/{filename}"

    class Meta:
        verbose_name = "Пользователь форума"
        verbose_name_plural = "Пользователи форума"

    def __str__(self):
        return self.username


class Topic(models.Model):
    phpbb_id = models.IntegerField("ID в phpBB", unique=True, null=True, blank=True)
    subforum = models.ForeignKey(
        SubForum,
        on_delete=models.CASCADE,
        related_name="topics",
        verbose_name="Подфорум",
    )
    title = models.CharField("Заголовок", max_length=255)
    created_at = models.DateTimeField("Дата создания", null=True, blank=True)
    views = models.IntegerField("Просмотры", default=0)
    post_count = models.IntegerField("Количество сообщений", default=0)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Тема"
        verbose_name_plural = "Темы"

    def __str__(self):
        return self.title


class Post(models.Model):
    phpbb_id = models.IntegerField("ID в phpBB", unique=True, null=True, blank=True)
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name="posts",
        verbose_name="Тема",
    )
    author = models.ForeignKey(
        ForumUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
        verbose_name="Автор",
    )
    author_username = models.CharField("Имя автора", max_length=255, blank=True)
    text_bbcode = models.TextField("Текст (BBCode)")
    text_html = models.TextField("Текст (HTML)")
    bbcode_uid = models.CharField("phpBB BBCode UID", max_length=20, blank=True)
    created_at = models.DateTimeField("Дата создания", null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"

    def __str__(self):
        return f"Post #{self.phpbb_id} in {self.topic}"


class PostAttachment(models.Model):
    phpbb_id = models.IntegerField("ID в phpBB", unique=True)
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="Сообщение",
    )
    physical_filename = models.CharField("Физическое имя файла", max_length=255)
    real_filename = models.CharField("Оригинальное имя файла", max_length=255)
    mimetype = models.CharField("MIME-тип", max_length=100, blank=True)
    filesize = models.IntegerField("Размер файла", default=0)
    download_count = models.IntegerField("Количество скачиваний", default=0)
    attach_comment = models.TextField("Комментарий", blank=True)

    @property
    def url(self):
        return f"/forum/a/{self.pk}/"

    @property
    def is_image(self):
        return self.mimetype.startswith("image/")

    class Meta:
        ordering = ["phpbb_id"]
        verbose_name = "Вложение"
        verbose_name_plural = "Вложения"

    def __str__(self):
        return self.real_filename
