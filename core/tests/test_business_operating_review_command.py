import json
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from core.models import AuditLog


class BusinessOperatingReviewTests(TestCase):
    def test_default_does_not_write_or_claim_revenue(self):
        out = StringIO()
        call_command("business_operating_review", stdout=out)
        report = json.loads(out.getvalue())
        self.assertEqual(report["metrics"]["verified_collected_cash"]["state"], "unknown")
        self.assertEqual(report["scope"].split(";")[0], "local_django_database_only")
        self.assertFalse(AuditLog.objects.filter(action="business_operating_review").exists())

    def test_record_only_adds_explicit_audit_receipt(self):
        out = StringIO()
        call_command("business_operating_review", "--record", stdout=out)
        report = json.loads(out.getvalue())
        self.assertTrue(AuditLog.objects.filter(pk=report["audit_id"], action="business_operating_review").exists())
