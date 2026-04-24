import datetime

from django.shortcuts import render

from .models import ClubMember, DonationPeriod, MemberDonation


def build_donor_table():
    periods = list(DonationPeriod.objects.filter(is_active=True).order_by("date"))
    if not periods:
        return None

    period_ids = [p.id for p in periods]

    donations = MemberDonation.objects.filter(
        period_id__in=period_ids
    ).select_related("member", "period")

    payment_map = {}
    for d in donations:
        payment_map.setdefault(d.member_id, {})[d.period_id] = d.is_paid

    members = list(
        ClubMember.objects.filter(id__in=payment_map.keys()).order_by("name")
    )

    today = datetime.date.today()
    past_or_current = [p for p in periods if p.date <= today]
    current_period = past_or_current[-1] if past_or_current else periods[0]
    current_period_id = current_period.id

    def row_sort_key(member):
        paid_current = payment_map[member.id].get(current_period_id, None)
        return (0 if paid_current else 1, member.name)

    members.sort(key=row_sort_key)

    rows = []
    for member in members:
        pmap = payment_map[member.id]
        cells = [pmap.get(pid) for pid in period_ids]
        rows.append(
            {
                "member": member,
                "cells": cells,
                "paid_current": pmap.get(current_period_id, None),
            }
        )

    return {
        "periods": periods,
        "current_period_index": periods.index(current_period),
        "rows": rows,
    }


def contributors_view(request):
    donor_table = build_donor_table()
    return render(request, "contributors/contributors.html", {"donor_table": donor_table})
