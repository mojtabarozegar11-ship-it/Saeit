"""Non-destructive by default: inquiry retention operator command."""
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from prop_firm.models import PropInformationInquiry, PropInterestHourlyBucket


class InquiryRetentionCommandTests(TestCase):
    def make(self, suffix="1", expired=True):
        return PropInformationInquiry.objects.create(
            email=f"client{suffix}@example.net",
            email_digest=(suffix[0] * 64),
            consent_version="moj-prop-interest-2026-11-15-v1",
            expires_at=timezone.now() + timedelta(days=-1 if expired else 30),
        )

    def test_dry_run_reports_but_never_deletes(self):
        self.make()
        out = StringIO()
        call_command("moj_prop_purge_expired_inquiries", stdout=out)
        self.assertIn("expired_inquiries=1", out.getvalue())
        self.assertEqual(PropInformationInquiry.objects.count(), 1)

    def test_commit_without_explicit_owner_authorization_rejected(self):
        self.make()
        with self.assertRaisesRegex(CommandError, "Explicit owner approval"):
            call_command("moj_prop_purge_expired_inquiries", "--commit")
        self.assertEqual(PropInformationInquiry.objects.count(), 1)

    def test_approved_retention_deletes_expired_not_current(self):
        self.make("1", expired=True)
        self.make("2", expired=False)
        out = StringIO()
        call_command("moj_prop_purge_expired_inquiries",
                     "--commit", "--owner-authorized", stdout=out)
        self.assertIn("expired_inquiries_deleted=1", out.getvalue())
        self.assertEqual(PropInformationInquiry.objects.count(), 1)
        self.assertTrue(PropInformationInquiry.objects.filter(email="client2@example.net").exists())
    def make_bucket(self, suffix="a", expired=True):
        return PropInterestHourlyBucket.objects.create(
            digest=suffix * 64, count=3,
            expires_at=timezone.now() + timedelta(days=-1 if expired else 1),
        )

    def test_dry_run_preserves_expired_buckets(self):
        self.make_bucket()
        out = StringIO()
        call_command("moj_prop_purge_expired_inquiries", stdout=out)
        self.assertIn("expired_buckets=1", out.getvalue())
        self.assertEqual(PropInterestHourlyBucket.objects.count(), 1)

    def test_commit_without_owner_approval_never_deletes_bucket(self):
        self.make_bucket()
        with self.assertRaisesRegex(CommandError, "Explicit owner approval"):
            call_command("moj_prop_purge_expired_inquiries", "--commit")
        self.assertEqual(PropInterestHourlyBucket.objects.count(), 1)

    def test_owner_approved_expiry_purges_only_old_buckets(self):
        self.make_bucket("a", True)
        self.make_bucket("b", False)
        out = StringIO()
        call_command("moj_prop_purge_expired_inquiries",
                     "--commit", "--owner-authorized", stdout=out)
        self.assertIn("expired_buckets_deleted=1", out.getvalue())
        self.assertEqual(PropInterestHourlyBucket.objects.count(), 1)
        self.assertTrue(PropInterestHourlyBucket.objects.filter(digest="b" * 64).exists())
