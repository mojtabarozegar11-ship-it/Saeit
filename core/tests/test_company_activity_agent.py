from django.test import TestCase
from core.company_activity_agent import REPORT_TYPES, report_contract, build_report_content, ensure_agent, build_report_inputs
from core.models import Agent
from core.company_activity_agent import AGENT_CODE
from core.company_activity_models import CompanyActivityAgentPlan, CompanyActivityReport


class CompanyActivityAgentTests(TestCase):
    def test_contract_is_daily_and_owner_gated(self):
        contract = report_contract()
        self.assertEqual(contract["agent"], "mojtaba-bot-ai")
        self.assertEqual(contract["capability"], AGENT_CODE)
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


    def test_legacy_report_agent_never_reactivated(self):
        legacy = Agent.objects.create(
            code=AGENT_CODE, name="Retired Reporter", mission="Old report", active=False,
        )
        with self.assertRaisesRegex(RuntimeError, "CANONICAL_CONTENT_OWNER_NOT_ACTIVE"):
            ensure_agent()
        legacy.refresh_from_db()
        self.assertFalse(legacy.active)
        self.assertFalse(Agent.objects.filter(code="mojtaba-bot-ai").exists())

    def test_reports_use_existing_canonical_agent_not_a_new_identity(self):
        canonical = Agent.objects.create(
            code="mojtaba-bot-ai", name="Mojtaba Bot", mission="central", active=True,
        )
        legacy = Agent.objects.create(
            code=AGENT_CODE, name="Retired Reporter", mission="Old report", active=False,
        )
        self.assertEqual(ensure_agent().pk, canonical.pk)
        legacy.refresh_from_db()
        self.assertFalse(legacy.active)
        self.assertEqual(Agent.objects.filter(active=True).count(), 1)
