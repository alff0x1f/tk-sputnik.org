from django.db import models


class ClubMember(models.Model):
    external_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=120)
    label = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class DonationPeriod(models.Model):
    external_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=120)
    date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("date",)

    def __str__(self):
        return self.name


class MemberDonation(models.Model):
    member = models.ForeignKey(
        ClubMember,
        on_delete=models.CASCADE,
        related_name="donations",
    )
    period = models.ForeignKey(
        DonationPeriod,
        on_delete=models.CASCADE,
        related_name="member_donations",
    )
    is_paid = models.BooleanField(default=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    paid_date = models.DateField(null=True, blank=True)
    recipient = models.CharField(max_length=20, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ("member", "period")

    def __str__(self):
        status = "оплатил" if self.is_paid else "не оплатил"
        return f"{self.member} — {self.period} ({status})"
