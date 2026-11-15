"""No silent deletion of open Moj Prop work; owner-only retention gate."""
from datetime import timedelta
from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone
from core.models import MojPropRequest


class MojPropC67ClosedLeadRetentionTests(TestCase):
    def make(self,n,status="closed",days=120):
        row=MojPropRequest.objects.create(
            request_id=f"MOJPROP-PRIVACY-{n}",name="Private Buyer",
            email=f"buyer{n}@example.org",route="brief",horizon="review",
            notes="This request asks for a scoped educational research brief.",
            status=status,consent=True,
        )
        MojPropRequest.objects.filter(pk=row.pk).update(
            created_at=timezone.now()-timedelta(days=days))
        return row

    def run_command(self,*args):
        out=StringIO()
        call_command("moj_prop_purge_closed_leads",*args,stdout=out)
        return out.getvalue()

    def test_default_dry_run_reports_only_eligible_counts(self):
        self.make(1)
        self.make(2,status="reviewing")
        s=self.run_command()
        self.assertIn("closed_old_mojprop_leads=1",s)
        self.assertEqual(MojPropRequest.objects.count(),2)

    def test_no_delete_without_case_specific_approval(self):
        self.make(1)
        with self.assertRaisesRegex(CommandError,"owner_approval_required"):
            self.run_command("--commit")
        self.assertEqual(MojPropRequest.objects.count(),1)

    def test_explicit_authorized_cleanup_closed_only(self):
        self.make(1,status="closed")
        self.make(2,status="spam")
        self.make(3,status="reviewing")
        s=self.run_command("--commit","--owner-authorized")
        self.assertIn("closed_old_mojprop_leads_deleted=2",s)
        self.assertTrue(MojPropRequest.objects.filter(
            request_id="MOJPROP-PRIVACY-3").exists())

    def test_no_delete_recent_closed_case(self):
        self.make(1,status="closed",days=10)
        self.run_command("--commit","--owner-authorized")
        self.assertEqual(MojPropRequest.objects.count(),1)

    def test_no_delete_unreviewed_new_case(self):
        self.make(1,status="new",days=200)
        self.run_command("--commit","--owner-authorized")
        self.assertEqual(MojPropRequest.objects.count(),1)

    def test_no_delete_delivered_paid_or_customer_engaged_case(self):
        self.make(1,status="delivered",days=200)
        self.make(2,status="offer_sent",days=200)
        self.run_command("--commit","--owner-authorized")
        self.assertEqual(MojPropRequest.objects.count(),2)

    def test_maximum_retention_horizon_validation(self):
        with self.assertRaisesRegex(CommandError,"retention_range_invalid"):
            self.run_command("--older-than-days","1000")

    def test_unacceptably_short_retention_denied(self):
        with self.assertRaisesRegex(CommandError,"retention_range_invalid"):
            self.run_command("--older-than-days","1")

    def test_private_customer_identifiers_not_logged(self):
        self.make(1)
        for args in [(),("--commit","--owner-authorized")]:
            output=self.run_command(*args)
            self.assertNotIn("buyer1@example.org",output)
            self.assertNotIn("Private Buyer",output)

    def test_owner_cleanup_is_never_part_of_public_checkout(self):
        self.make(1)
        s=self.run_command()
        self.assertIn("buyer_identity_redacted=true",s)
        self.assertEqual(MojPropRequest.objects.count(),1)
