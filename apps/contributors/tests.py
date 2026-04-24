import datetime

from django.db import IntegrityError
from django.test import TestCase

from .models import ClubMember, DonationPeriod, MemberDonation


class ClubMemberModelTests(TestCase):
    def test_create(self):
        member = ClubMember.objects.create(external_id=1, name="Алексей", label="Горная школа")
        self.assertEqual(member.name, "Алексей")
        self.assertEqual(member.label, "Горная школа")

    def test_external_id_unique(self):
        ClubMember.objects.create(external_id=1, name="Алексей")
        with self.assertRaises(IntegrityError):
            ClubMember.objects.create(external_id=1, name="Другой")

    def test_label_blank_by_default(self):
        member = ClubMember.objects.create(external_id=2, name="Борис")
        self.assertEqual(member.label, "")


class DonationPeriodModelTests(TestCase):
    def test_create(self):
        period = DonationPeriod.objects.create(
            external_id=1, name="весна 2024", date=datetime.date(2024, 3, 1), is_active=True
        )
        self.assertEqual(period.name, "весна 2024")
        self.assertTrue(period.is_active)

    def test_external_id_unique(self):
        DonationPeriod.objects.create(
            external_id=1, name="весна 2024", date=datetime.date(2024, 3, 1)
        )
        with self.assertRaises(IntegrityError):
            DonationPeriod.objects.create(
                external_id=1, name="осень 2024", date=datetime.date(2024, 9, 1)
            )


class MemberDonationModelTests(TestCase):
    def setUp(self):
        self.member = ClubMember.objects.create(external_id=1, name="Алексей")
        self.period = DonationPeriod.objects.create(
            external_id=1, name="весна 2024", date=datetime.date(2024, 3, 1)
        )

    def test_create(self):
        donation = MemberDonation.objects.create(
            member=self.member,
            period=self.period,
            is_paid=True,
            amount="1500.00",
            paid_date=datetime.date(2024, 4, 10),
            recipient="sbp",
        )
        self.assertTrue(donation.is_paid)
        self.assertEqual(str(donation.amount), "1500.00")

    def test_unique_together(self):
        MemberDonation.objects.create(member=self.member, period=self.period)
        with self.assertRaises(IntegrityError):
            MemberDonation.objects.create(member=self.member, period=self.period)

    def test_optional_fields(self):
        donation = MemberDonation.objects.create(member=self.member, period=self.period)
        self.assertFalse(donation.is_paid)
        self.assertIsNone(donation.amount)
        self.assertIsNone(donation.paid_date)
        self.assertEqual(donation.recipient, "")
        self.assertEqual(donation.note, "")
