from django.test import TestCase
from core.models import Agent, AgentTask, AgentCapability, AuditLog
from core.canonical_agent_handoff import specialist_owner, BOT_CODE
from core.company_activity_agent import ensure_agent, AGENT_CODE

class SpecialistOwnershipTests(TestCase):
    def setUp(self):
        self.old = Agent.objects.create(code=AGENT_CODE,name="Legacy",mission="Reports",active=True)
        self.bot = Agent.objects.create(code=BOT_CODE,name="Canonical",mission="Single bot",active=True)
    def receipt(self, old=None, **overrides):
        old = old or self.old
        state = {"legacy_code":old.code,"canonical_bot_code":BOT_CODE,
            "canonical_successor_runtime_verified":True,"external_legacy_schedulers_stopped":True,
            "all_pending_tasks_reconciled":True,"historical_data_preserved":True,"rollback_ready":True,
            "live_inventory_receipt_id":"inventory","canonical_successor_receipt_id":"successor"}
        state.update(overrides)
        return AuditLog.objects.create(action="single_bot_live_handoff_verified",
            target_type="Agent",target_id=str(old.pk),actor_type="system",actor_id=BOT_CODE,
            trace_id="reviewed-handoff",after_state=state)
    def retire(self, old=None):
        old = old or self.old
        old.active=False
        old.save(update_fields=["active"])
    def test_existing_active_role_preserved_until_handoff(self):
        self.assertEqual(ensure_agent().pk,self.old.pk)
    def test_no_legacy_reactivation_after_canonical_exists(self):
        self.retire()
        with self.assertRaisesRegex(RuntimeError,"HANDOFF_REQUIRED"):
            ensure_agent()
        self.old.refresh_from_db()
        self.assertFalse(self.old.active)
    def test_no_new_legacy_identity_when_canonical_exists(self):
        with self.assertRaisesRegex(RuntimeError,"HANDOFF_REQUIRED"):
            specialist_owner("content-director",defaults={"name":"old","active":True})
        self.assertFalse(Agent.objects.filter(code="content-director").exists())
    def test_active_predecessor_cannot_route_to_canonical(self):
        self.receipt()
        with self.assertRaises(RuntimeError):
            ensure_agent()
    def test_exact_handoff_can_route_to_canonical_preserving_history(self):
        terminal=AgentTask.objects.create(agent=self.old,status="completed")
        self.retire()
        self.receipt()
        self.assertEqual(ensure_agent().pk,self.bot.pk)
        terminal.refresh_from_db()
        self.assertEqual(terminal.agent_id,self.old.pk)
    def test_pending_task_blocks_handoff(self):
        self.retire()
        self.receipt()
        AgentTask.objects.create(agent=self.old,status="blocked")
        with self.assertRaises(RuntimeError):
            ensure_agent()
    def test_invalid_receipt_blocks_routing(self):
        self.retire()
        self.receipt(rollback_ready=False)
        with self.assertRaisesRegex(RuntimeError,"RECEIPT_INVALID"):
            ensure_agent()
    def test_knowledge_requires_active_high_risk_capability(self):
        old=Agent.objects.create(code="knowledge-content-director",name="Knowledge",mission="Books",active=False)
        self.receipt(old)
        with self.assertRaisesRegex(RuntimeError,"KNOWLEDGE_CAPABILITY"):
            specialist_owner(old.code)
        cap=AgentCapability.objects.create(code="research-write-review",name="Knowledge",risk_level="high",active=True)
        self.bot.capabilities.add(cap)
        self.assertEqual(specialist_owner(old.code).pk,self.bot.pk)

    def test_blocked_company_handoff_does_not_create_plan(self):
        from django.core.management import call_command
        from core.company_activity_models import CompanyActivityAgentPlan
        self.retire()
        with self.assertRaises(RuntimeError):
            call_command("company_activity_agent_cycle")
        self.assertFalse(CompanyActivityAgentPlan.objects.exists())

    def test_weather_inconsistent_handoff_blocks_before_network(self):
        from unittest.mock import patch
        from core.weather_agent import run_daily_cycle
        old=Agent.objects.create(code="content-research",name="Weather",mission="Forecast",active=False)
        self.receipt(old,rollback_ready=False)
        with patch("core.weather_agent.province_forecast") as network:
            with self.assertRaisesRegex(RuntimeError,"RECEIPT_INVALID"):
                run_daily_cycle()
            network.assert_not_called()
