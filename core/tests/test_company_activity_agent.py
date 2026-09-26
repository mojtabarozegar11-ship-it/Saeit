from django.test import TestCase
from core.company_activity_agent import REPORT_TYPES, report_contract, build_report_content
from core.company_activity_models import CompanyActivityAgentPlan, CompanyActivityReport


class CompanyActivityAgentTests(TestCase):
    def test_contract_is_daily_and_owner_gated(self):
        contract = report_contract()
        self.assertEqual(contract["agent"], "company-activity-intelligence")
        self.assertEqual(len(contract["report_types"]), 6)
        self.assertTrue(contract["fabrication_forbidden"])
        self.assertTrue(contract["publication_requires_owner_approval"])

    def test_report_type_catalog_is_complete(self):
        self.assertEqual(REPORT_TYPES, ("DAILY_DIGEST", "ACTIVITY_ANALYSIS", "TREND_ANALYSIS", "UNIT_ANALYSIS", "PROJECT_ANALYSIS", "EXECUTIVE_BRIEF"))

    def test_empty_source_is_never_presented_as_company_activity(self):
        text = build_report_content("DAILY_DIGEST", [], {})
        self.assertIn("منبع واقعی برای این گزارش ثبت نشده است", text)
        self.assertIn("انتشار مسدود است", text)

    def test_daily_report_constraint_exists(self):
        self.assertTrue(any(c.name == "unique_company_activity_daily_report" for c in CompanyActivityReport._meta.constraints))
