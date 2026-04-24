from django.contrib import admin

from .models import ClubMember, DonationPeriod, MemberDonation


@admin.register(ClubMember)
class ClubMemberAdmin(admin.ModelAdmin):
    list_display = ("name", "label", "external_id")
    search_fields = ("name", "label")


@admin.register(DonationPeriod)
class DonationPeriodAdmin(admin.ModelAdmin):
    list_display = ("name", "date", "is_active", "external_id")
    list_filter = ("is_active",)


@admin.register(MemberDonation)
class MemberDonationAdmin(admin.ModelAdmin):
    list_display = ("member", "period", "is_paid", "amount", "paid_date", "recipient")
    list_filter = ("is_paid", "period")
    search_fields = ("member__name",)
