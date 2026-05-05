import datetime
import json
from io import StringIO
from unittest.mock import MagicMock, patch

from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from .models import ClubMember, DonationPeriod, MemberDonation


class ClubMemberModelTests(TestCase):
    def test_create(self):
        member = ClubMember.objects.create(
            external_id=1, name="Алексей", label="Горная школа"
        )
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
            external_id=1,
            name="весна 2024",
            date=datetime.date(2024, 3, 1),
            is_active=True,
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


SAMPLE_API_RESPONSE = {
    "periods": [
        {"id": 1, "name": "весна 2024", "date": "2024-03-01", "is_active": True}
    ],
    "members": [{"id": 5, "name": "Алексей Костров", "label": "Горная школа"}],
    "donations": [
        {
            "member_id": 5,
            "period_id": 1,
            "is_paid": True,
            "amount": "1500.00",
            "paid_date": "2024-04-10",
            "recipient": "sbp",
            "note": "",
        }
    ],
}


def _make_mock_urlopen(data):
    response_bytes = json.dumps(data).encode()
    mock_response = MagicMock()
    mock_response.read.return_value = response_bytes
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=mock_response)


SYNC_ENV = {
    "KOLCO24_API_URL": "http://fake.example/api",
    "KOLCO24_API_TOKEN": "test-secret-token",
}


class SyncContributorsCommandTests(TestCase):
    @patch.dict("os.environ", SYNC_ENV)
    @patch("urllib.request.urlopen")
    def test_creates_objects_from_api(self, mock_urlopen):
        mock_urlopen.side_effect = _make_mock_urlopen(SAMPLE_API_RESPONSE)

        from django.core.management import call_command

        call_command("sync_contributors", stdout=StringIO())

        self.assertEqual(DonationPeriod.objects.count(), 1)
        self.assertEqual(ClubMember.objects.count(), 1)
        self.assertEqual(MemberDonation.objects.count(), 1)

        member = ClubMember.objects.get(external_id=5)
        self.assertEqual(member.name, "Алексей Костров")
        self.assertEqual(member.label, "Горная школа")

        period = DonationPeriod.objects.get(external_id=1)
        self.assertEqual(period.name, "весна 2024")
        self.assertTrue(period.is_active)

        donation = MemberDonation.objects.get(member=member, period=period)
        self.assertTrue(donation.is_paid)
        self.assertEqual(str(donation.amount), "1500.00")
        self.assertEqual(donation.recipient, "sbp")

    @patch.dict("os.environ", SYNC_ENV)
    @patch("urllib.request.urlopen")
    def test_sends_bearer_token(self, mock_urlopen):
        mock_urlopen.side_effect = _make_mock_urlopen(SAMPLE_API_RESPONSE)

        from django.core.management import call_command

        call_command("sync_contributors", stdout=StringIO())

        called_request = mock_urlopen.call_args[0][0]
        self.assertEqual(
            called_request.get_header("Authorization"),
            "Bearer test-secret-token",
        )

    @patch.dict("os.environ", {"KOLCO24_API_URL": "http://fake.example/api"}, clear=False)
    def test_missing_token_raises_error(self):
        import os

        from django.core.management import call_command
        from django.core.management.base import CommandError

        os.environ.pop("KOLCO24_API_TOKEN", None)
        with self.assertRaises(CommandError):
            call_command("sync_contributors", stdout=StringIO())

    @patch.dict("os.environ", SYNC_ENV)
    @patch("urllib.request.urlopen")
    def test_idempotent(self, mock_urlopen):
        mock_urlopen.side_effect = _make_mock_urlopen(SAMPLE_API_RESPONSE)

        from django.core.management import call_command

        call_command("sync_contributors", stdout=StringIO())

        mock_urlopen.side_effect = _make_mock_urlopen(SAMPLE_API_RESPONSE)
        call_command("sync_contributors", stdout=StringIO())

        self.assertEqual(DonationPeriod.objects.count(), 1)
        self.assertEqual(ClubMember.objects.count(), 1)
        self.assertEqual(MemberDonation.objects.count(), 1)


class ContributorsViewTests(TestCase):
    def test_get_returns_200(self):
        response = self.client.get(reverse("contributors"))
        self.assertEqual(response.status_code, 200)

    def test_uses_correct_template(self):
        response = self.client.get(reverse("contributors"))
        self.assertTemplateUsed(response, "contributors/contributors.html")

    def test_empty_db_renders_without_error(self):
        response = self.client.get(reverse("contributors"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["donor_table"])

    def test_context_contains_donor_table_with_data(self):
        member = ClubMember.objects.create(
            external_id=1, name="Алексей", label="Горная школа"
        )
        period = DonationPeriod.objects.create(
            external_id=1,
            name="весна 2024",
            date=datetime.date(2024, 3, 1),
            is_active=True,
        )
        MemberDonation.objects.create(member=member, period=period, is_paid=True)

        response = self.client.get(reverse("contributors"))
        self.assertEqual(response.status_code, 200)

        donor_table = response.context["donor_table"]
        self.assertIsNotNone(donor_table)
        self.assertEqual(len(donor_table["periods"]), 1)
        self.assertEqual(len(donor_table["rows"]), 1)

        row = donor_table["rows"][0]
        self.assertEqual(row["member"], member)
        self.assertEqual(row["cells"], [True])
        self.assertTrue(row["paid_current"])

    def test_sorting_paid_first(self):
        period = DonationPeriod.objects.create(
            external_id=1,
            name="весна 2024",
            date=datetime.date(2024, 3, 1),
            is_active=True,
        )
        member_a = ClubMember.objects.create(external_id=1, name="Аня")
        member_b = ClubMember.objects.create(external_id=2, name="Борис")
        MemberDonation.objects.create(member=member_a, period=period, is_paid=False)
        MemberDonation.objects.create(member=member_b, period=period, is_paid=True)

        response = self.client.get(reverse("contributors"))
        rows = response.context["donor_table"]["rows"]
        self.assertEqual(rows[0]["member"], member_b)
        self.assertEqual(rows[1]["member"], member_a)
