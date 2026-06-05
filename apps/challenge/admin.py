from django.contrib import admin

from .models import Athlete, Group, Report, SourceMessage, Workout


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["name", "order"]
    list_editable = ["order"]


@admin.register(Athlete)
class AthleteAdmin(admin.ModelAdmin):
    list_display = ["telegram_id", "name", "group"]
    list_filter = ["group"]
    list_select_related = ["group"]


@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    list_display = [
        "athlete",
        "date",
        "activity",
        "distance_km",
        "base_points",
        "streak_bonus",
        "total_points",
        "msg_id",
    ]
    list_filter = ["activity", "date"]


@admin.register(SourceMessage)
class SourceMessageAdmin(admin.ModelAdmin):
    list_display = ["msg_id", "from_name", "date"]
    list_filter = ["date"]


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["message", "athlete", "short_text", "created_at", "resolved"]
    list_filter = ["resolved", "created_at"]
    list_editable = ["resolved"]
    list_select_related = ["message", "athlete"]

    @admin.display(description="Текст")
    def short_text(self, obj):
        if len(obj.text) > 60:
            return obj.text[:60] + "…"
        return obj.text
