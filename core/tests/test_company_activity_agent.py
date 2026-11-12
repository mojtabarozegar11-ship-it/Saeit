from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError

from core.company_activity_agent import (
    AGENT_CODE, REPORT_TYPES, report_contract, build_report_content, ensure_agent,
)
from core.company_activity_models import CompanyActivityAgentPlan, CompanyActivityReport
from core.models import Agent, AgentTask
from core.unified_bot_identity import BOT_CODE


class CompanyActivityAgentTests(TestCase):
    def test_contract_is_daily_and_owner_gated(self):
        contract = report_contract()
        self.assertEqual(contract["agent"], "company-activity-intelligence")
        self.assertEqual(contract["owner_bot_code"], BOT_CODE)
        self.assertEqual(contract["owner_bot_id"], "mojtaba.bot.ai")
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

    def _canonical(self):
        return Agent.objects.create(
            code=BOT_CODE, name="Mojtaba.bot.ai", mission="Single bot",
            active=True,
        )

    def _legacy(self, *, active):
        return Agent.objects.create(
            code=AGENT_CODE, name="Old company agent",
            mission="Historical company activity work", active=active,
        )

    def test_company_module_uses_canonical_owner_without_creating_legacy_agent(self):
        canonical = self._canonical()
        resolved = ensure_agent()
        self.assertEqual(resolved.pk, canonical.pk)
        self.assertFalse(Agent.objects.filter(code=AGENT_CODE).exists())
        call_command("company_activity_agent_cycle")
        self.assertEqual(CompanyActivityAgentPlan.objects.count(), 1)
        self.assertFalse(Agent.objects.filter(code=AGENT_CODE).exists())

    def test_inactive_legacy_record_preserved_without_reactivation(self):
        canonical = self._canonical()
        historical = self._legacy(active=False)
        resolved = ensure_agent()
        self.assertEqual(resolved.pk, canonical.pk)
        call_command("company_activity_agent_cycle")
        historical.refresh_from_db()
        self.assertFalse(historical.active)
        self.assertEqual(historical.pk, Agent.objects.get(code=AGENT_CODE).pk)

    def test_active_legacy_blocks_before_any_plan_is_created(self):
        self._canonical()
        old = self._legacy(active=True)
        with self.assertRaisesRegex(CommandError, "COMPANY_ACTIVITY_LEGACY_HANDOFF_REQUIRED"):
            call_command("company_activity_agent_cycle")
        old.refresh_from_db()
        self.assertTrue(old.active)
        self.assertEqual(CompanyActivityAgentPlan.objects.count(), 0)
        self.assertEqual(CompanyActivityReport.objects.count(), 0)

    def test_pending_tasks_on_inactive_legacy_block_automatic_handoff(self):
        self._canonical()
        old = self._legacy(active=False)
        task = AgentTask.objects.create(
            agent=old, action_type="company_report_draft",
            capability_code="company_report_draft", status="queued",
        )
        with self.assertRaisesRegex(CommandError, "COMPANY_ACTIVITY_LEGACY_HANDOFF_REQUIRED"):
            call_command("company_activity_agent_cycle")
        task.refresh_from_db()
        self.assertEqual(task.agent_id, old.pk)
        self.assertEqual(task.status, "queued")
        self.assertEqual(CompanyActivityAgentPlan.objects.count(), 0)

    def test_missing_canonical_never_provisions_second_bot_or_plan(self):
        with self.assertRaisesRegex(CommandError, "MOJTABA_CANONICAL_AGENT_NOT_PROVISIONED"):
            call_command("company_activity_agent_cycle")
        self.assertEqual(Agent.objects.count(), 0)
        self.assertEqual(CompanyActivityAgentPlan.objects.count(), 0)
