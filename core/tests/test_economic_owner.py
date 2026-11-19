from django.test import TestCase
from core.models import Agent, AgentTask, AgentCapability, AuditLog
from core.economic_owner import (
    economic_owner_code, economic_queue, economic_history, LEGACY, CUTOVER, ECONOMIC_CODES,
)
from core.unified_bot_identity import BOT_CODE

class EconomicOwnerTests(TestCase):
    def setUp(self):
        self.old = Agent.objects.create(code=LEGACY,name="Legacy economic",mission="Existing",active=True)
        self.bot = Agent.objects.create(code=BOT_CODE,name="Canonical",mission="Single bot",active=True)

    def receipt(self):
        return AuditLog.objects.create(actor_type="system",actor_id=BOT_CODE,
            action=CUTOVER,target_type="Agent",target_id=str(self.old.pk),
            trace_id="economic-handoff",after_state={"legacy_code":LEGACY,
                 "canonical_code":BOT_CODE,"canonical_agent_id":self.bot.pk,
                 "legacy_schedulers_stopped":True})

    def ready(self):
        self.old.active = False
        self.old.save(update_fields=["active"])
        for code in ECONOMIC_CODES:
            cap, _ = AgentCapability.objects.get_or_create(code=code, defaults={"name":code,"active":True})
            self.bot.capabilities.add(cap)
        self.receipt()

    def test_existing_site_owner_does_not_take_economic_lane(self):
        self.assertEqual(economic_owner_code(), LEGACY)

    def test_inactive_legacy_without_transfer_does_not_enable_canonical(self):
        self.old.active=False
        self.old.save(update_fields=["active"])
        self.assertEqual(economic_owner_code(), LEGACY)

    def test_transfer_with_duplicate_active_owner_blocks(self):
        self.receipt()
        with self.assertRaisesRegex(RuntimeError, "RECONCILIATION"):
            economic_owner_code()

    def test_complete_cutover_preserves_terminal_history_and_scopes_queue(self):
        self.ready()
        historical = AgentTask.objects.create(agent=self.old,action_type="income_revenue_verify",
            capability_code="income_revenue_verify",status="completed")
        economic = AgentTask.objects.create(agent=self.bot,action_type="income_market_research",
            capability_code="income_market_research",status="queued")
        AgentTask.objects.create(agent=self.bot,action_type="factory_native_review",
            capability_code="factory_native_review",status="queued")
        self.assertEqual(economic_owner_code(), BOT_CODE)
        self.assertEqual(list(economic_queue().values_list("pk",flat=True)),[economic.pk])
        self.assertEqual(set(economic_history().values_list("pk",flat=True)),{historical.pk,economic.pk})
        historical.refresh_from_db()
        self.assertEqual(historical.agent_id,self.old.pk)

    def test_unknown_pending_predecessor_task_blocks_cutover(self):
        self.ready()
        AgentTask.objects.create(agent=self.old,action_type="unknown",status="queued")
        with self.assertRaisesRegex(RuntimeError, "RECONCILIATION"):
            economic_owner_code()

    def test_revoked_economic_capability_blocks_cutover(self):
        self.ready()
        self.bot.capabilities.remove(AgentCapability.objects.get(code="income_revenue_verify"))
        with self.assertRaisesRegex(RuntimeError, "RECONCILIATION"):
            economic_owner_code()
