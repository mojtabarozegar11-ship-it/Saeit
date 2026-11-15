"""Operator-authorized retention of quota, never buyer inquiries."""
from datetime import timedelta
from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone
from core.models import MojPropRateBucket, MojPropRequest


class MojPropQuotaRetentionTests(TestCase):
    def bucket(self, char, expires):
        return MojPropRateBucket.objects.create(
            digest=char*64,
            count=3,
            expires_at=timezone.now()+timedelta(minutes=expires),
        )

    def test_dry_run_reports_without_deletion(self):
        self.bucket("a",-1)
        out=StringIO()
        call_command("moj_prop_purge_rate_buckets",stdout=out)
        self.assertIn("moj_prop_expired_quota_rows=1; dry_run=true",out.getvalue())
        self.assertEqual(MojPropRateBucket.objects.count(),1)

    def test_commit_requires_case_specific_owner_authorization(self):
        self.bucket("a",-1)
        with self.assertRaisesRegex(CommandError,"Explicit owner approval"):
            call_command("moj_prop_purge_rate_buckets","--commit")
        self.assertEqual(MojPropRateBucket.objects.count(),1)

    def test_authorized_cleanup_only_removes_expired_quota(self):
        self.bucket("a",-1)
        self.bucket("b",1)
        out=StringIO()
        call_command("moj_prop_purge_rate_buckets","--commit",
                     "--owner-authorized",stdout=out)
        self.assertIn("moj_prop_expired_quota_rows_deleted=1",out.getvalue())
        self.assertTrue(MojPropRateBucket.objects.filter(digest="b"*64).exists())

    def test_retention_command_cannot_delete_customer_lead(self):
        MojPropRequest.objects.create(
            request_id="MOJPROP-RETENTION-ONE",name="Buyer",
            email="buyer@example.org",route="audit",
            horizon="week",notes="Please advise on your private service.",
            consent=True,
        )
        self.bucket("a",-1)
        call_command("moj_prop_purge_rate_buckets","--commit",
                     "--owner-authorized",stdout=StringIO())
        self.assertEqual(MojPropRequest.objects.count(),1)

    def test_zero_expired_does_not_touch_current_quota(self):
        self.bucket("b",10)
        out=StringIO()
        call_command("moj_prop_purge_rate_buckets","--commit",
                     "--owner-authorized",stdout=out)
        self.assertIn("moj_prop_expired_quota_rows_deleted=0",out.getvalue())
