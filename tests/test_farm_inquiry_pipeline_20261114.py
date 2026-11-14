"""Django DB quality gates for PII-free read-only farm commercial funnel."""
import io
import json

from django.core.management import call_command
from django.test import TestCase

from core.company_inquiry_models import CompanyInquiry


class FarmInquiryPipelineTests(TestCase):
    def insert(self, *, subject="ZM-FARM | درخواست تحلیل اقتصادی مزرعه", kind="commercial", status="new"):
        return CompanyInquiry.objects.create(
            kind=kind, name="Private Customer Name",
            email="confidential@example.org", phone="09120000000",
            subject=subject, message="confidential farmland numbers",
            status=status,
        )

    def run_report(self, days=30):
        out = io.StringIO()
        call_command("farm_inquiry_pipeline", days=days, stdout=out)
        line = out.getvalue()
        self.assertTrue(line.startswith("ZM_FARM_PIPELINE="))
        return json.loads(line.split("=", 1)[1]), line

    def test_real_crm_lead_is_counted_once(self):
        self.insert()
        report, _ = self.run_report()
        self.assertEqual(report["matched_inquiries"], 1)
        self.assertEqual(report["status_counts"]["new"], 1)

    def test_status_counts_are_reported_separately(self):
        self.insert(status="new")
        self.insert(status="reviewing")
        self.insert(status="approved")
        self.insert(status="closed")
        report, _ = self.run_report()
        self.assertEqual(report["status_counts"], {
            "new": 1, "reviewing": 1, "approved": 1, "closed": 1,
        })

    def test_nonfarm_requests_not_included(self):
        self.insert(subject="Nonfarm commercial lead")
        self.insert(subject="ZM-FARM | invalid source", kind="research")
        report, _ = self.run_report()
        self.assertEqual(report["matched_inquiries"], 0)

    def test_report_never_prints_pii(self):
        self.insert()
        _, text = self.run_report()
        for sensitive in (
            "Private Customer Name", "confidential@example.org",
            "09120000000", "confidential farmland numbers",
        ):
            self.assertNotIn(sensitive, text)

    def test_report_does_not_infer_revenue_from_stage(self):
        self.insert(status="approved")
        report, _ = self.run_report()
        self.assertIsNone(report["confirmed_collected_revenue"])
        self.assertFalse(report["financial_certification"])

    def test_lower_invalid_window_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_report(days=0)

    def test_upper_invalid_window_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_report(days=367)

    def test_observation_has_timestamp_and_real_db_source(self):
        report, _ = self.run_report()
        self.assertIn("observed_at", report)
        self.assertEqual(report["data_source"], "configured Django CompanyInquiry database")
