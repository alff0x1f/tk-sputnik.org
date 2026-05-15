from django.db import models


class Athlete(models.Model):
    telegram_id = models.CharField("Telegram ID", max_length=64, primary_key=True)
    name = models.CharField("Имя", max_length=255)

    class Meta:
        verbose_name = "Участник"
        verbose_name_plural = "Участники"

    def __str__(self):
        return self.name


class Workout(models.Model):
    ACTIVITY_CHOICES = [
        ("running", "Бег"),
        ("skiing", "Лыжи"),
        ("cycling", "Велосипед"),
        ("swimming", "Плавание"),
        ("hiking", "Пеший поход"),
    ]

    athlete = models.ForeignKey(
        Athlete,
        on_delete=models.CASCADE,
        related_name="workouts",
        verbose_name="Участник",
    )
    date = models.DateField("Дата")
    activity = models.CharField("Активность", max_length=32, choices=ACTIVITY_CHOICES)
    distance_km = models.FloatField("Расстояние (км)", null=True, blank=True)
    pace_min_per_km = models.FloatField("Темп (мин/км)", null=True, blank=True)
    base_points = models.IntegerField("Базовые очки", default=0)
    streak_bonus = models.IntegerField("Бонус серии", default=0)
    total_points = models.IntegerField("Итого очков", default=0)
    msg_id = models.IntegerField("ID сообщения", null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "Тренировка"
        verbose_name_plural = "Тренировки"
        ordering = ["athlete", "date"]

    def __str__(self):
        return f"{self.athlete} — {self.activity} {self.date}"


class SourceMessage(models.Model):
    msg_id = models.IntegerField("ID сообщения", primary_key=True)
    from_name = models.CharField("Отправитель", max_length=255)
    date = models.DateField("Дата")
    text = models.TextField("Текст", blank=True)
    photos = models.JSONField("Фото", default=list)

    class Meta:
        verbose_name = "Исходное сообщение"
        verbose_name_plural = "Исходные сообщения"
        ordering = ["date", "msg_id"]

    def __str__(self):
        return f"Сообщение #{self.msg_id} от {self.from_name} ({self.date})"
