from django.contrib import admin

from .models import Athlete, SourceMessage, Workout


@admin.register(Athlete)
class AthleteAdmin(admin.ModelAdmin):
    list_display = ["telegram_id", "name"]


@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    list_display = [
        "athlete", "date", "activity", "distance_km",
        "base_points", "streak_bonus", "total_points", "msg_id",
    ]
    list_filter = ["activity", "date"]


@admin.register(SourceMessage)
class SourceMessageAdmin(admin.ModelAdmin):
    list_display = ["msg_id", "from_name", "date"]
    list_filter = ["date"]
