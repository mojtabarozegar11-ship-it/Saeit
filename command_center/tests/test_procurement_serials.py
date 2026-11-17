"""Public procurement serials: continuation, uniqueness, idempotence, and publication gating."""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from command_center.models import PrivateAuction, PublicProcurementNumber


class ProcurementSerialRegistrationTests(TestCase):
    EVIDENCE = "Checked legacy advertisement register and recorded its highest serial"

    def register(self, last=100, apply=False):
        out = StringIO()
        cli = ["--last-existing-number", str(last), "--evidence", self.EVIDENCE]
        if apply:
            cli.append("--apply")
        call_command("register_direct_procurement_notices", *cli, stdout=out)
        return out.getvalue()

    def test_dry_run_does_not_claim_numbers(self):
        msg = self.register(last=100)
        self.assertIn("101..172", msg)
        self.assertIn("DRY RUN", msg)
        self.assertEqual(PublicProcurementNumber.objects.count(), 0)

    def test_reserves_36_plus_36_after_highest_registered(self):
        user = get_user_model().objects.create_user("ad-number-check", password="nottestpassword")
        old_ad = PrivateAuction.objects.create(title="Existing internal tender", created_by=user)
        PublicProcurementNumber.objects.create(
            notice_key="OLDER-EXISTING-REGISTER",
            serial_number=180,
            baseline_evidence=self.EVIDENCE,
        )
        self.register(last=200, apply=True)
        rows = list(PublicProcurementNumber.objects.exclude(notice_key="OLDER-EXISTING-REGISTER").order_by("serial_number"))
        self.assertEqual(len(rows), 72)
        self.assertEqual([r.serial_number for r in rows], list(range(201, 273)))
        self.assertEqual([r.notice_key for r in rows[:36]], [f"ZM-SUP-{i:03d}" for i in range(1, 37)])
        self.assertEqual([r.notice_key for r in rows[36:]], [f"ZM-EQP-{i:03d}" for i in range(1, 37)])
        self.assertGreater(rows[0].serial_number, old_ad.pk)

    def test_private_auction_primary_key_is_not_public_ad_serial(self):
        user = get_user_model().objects.create_user("old-auction-number", password="nottestpassword")
        for i in range(3):
            PrivateAuction.objects.create(title=f"Internal auction {i}", created_by=user)
        self.register(last=0, apply=True)
        first = PublicProcurementNumber.objects.get(notice_key="ZM-SUP-001")
        self.assertEqual(first.serial_number, 1)

    def test_real_live_public_baseline_349_gives_350_through_421(self):
        output = self.register(last=349)
        self.assertIn("350..421", output)
        self.assertEqual(PublicProcurementNumber.objects.count(), 0)
        self.register(last=349, apply=True)
        grouped = list(PublicProcurementNumber.objects.order_by("serial_number"))
        self.assertEqual(grouped[0].serial_number, 350)
        self.assertEqual(grouped[35].serial_number, 385)
        self.assertEqual(grouped[36].serial_number, 386)
        self.assertEqual(grouped[-1].serial_number, 421)
        self.assertEqual(grouped[-1].notice_key, "ZM-EQP-036")

    def test_second_registration_does_not_reassign_or_duplicate_numbers(self):
        self.register(last=500, apply=True)
        original = list(PublicProcurementNumber.objects.values_list("notice_key", "serial_number"))
        msg = self.register(last=500, apply=True)
        self.assertIn("Already reserved", msg)
        self.assertEqual(original, list(PublicProcurementNumber.objects.values_list("notice_key", "serial_number")))
        self.assertEqual(len(original), 72)

    def test_rejects_historical_claim_that_conflicts_with_reserved_numbers(self):
        self.register(last=75, apply=True)
        with self.assertRaises(CommandError):
            self.register(last=80, apply=True)
        self.assertEqual(PublicProcurementNumber.objects.count(), 72)

    def test_public_page_fails_closed_before_numbers_exist_then_shows_reserved(self):
        before = self.client.get("/auctions/")
        self.assertEqual(before.status_code, 200)
        self.assertContains(before, "شماره‌گذاری نهایی آگهی‌ها در انتظار")
        self.assertNotContains(before, "شماره آگهی 1")
        self.register(last=912, apply=True)
        after = self.client.get("/auctions/")
        self.assertEqual(after.status_code, 200)
        self.assertContains(after, "شماره آگهی 913")
        self.assertContains(after, "شماره آگهی 984")
        self.assertContains(after, "ZM-SUP-001")
        self.assertContains(after, "ZM-EQP-036")
        self.assertNotContains(after, "شماره‌گذاری نهایی آگهی‌ها در انتظار")

    def test_partial_registry_never_publishes_partial_ad_numbers(self):
        PublicProcurementNumber.objects.create(
            notice_key="ZM-SUP-001",
            serial_number=450,
            baseline_evidence=self.EVIDENCE,
        )
        response = self.client.get("/auctions/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "شماره‌گذاری نهایی آگهی‌ها در انتظار")
        self.assertNotContains(response, "شماره آگهی 450")

    def test_out_of_order_registry_fails_closed(self):
        self.register(last=800, apply=True)
        first = PublicProcurementNumber.objects.get(notice_key="ZM-SUP-001")
        first.serial_number = 950
        first.save(update_fields=["serial_number"])
        response = self.client.get("/auctions/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "شماره‌گذاری نهایی آگهی‌ها در انتظار")
        self.assertNotContains(response, "شماره آگهی 950")
