from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from core.approval import ApprovalService
from core.models import Agent, AgentCapability, AgentTask, AuditLog, ApprovalRequest
from core.economic_owner import BOT_CODE, LEGACY, ECONOMIC_CODES, economic_owner_code
from core.management.commands.mojtaba_transfer_economic_lane import transfer, HANDOFF, REQUIRED

class TransferEconomicLaneTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser(username="cutover-owner",password="unused")
        self.old = Agent.objects.create(code=LEGACY,name="Legacy",mission="Economy",active=True)
        self.bot = Agent.objects.create(code=BOT_CODE,name="Canonical",mission="Single",active=True)
        for code in ECONOMIC_CODES:
            cap,_ = AgentCapability.objects.get_or_create(code=code,defaults={"name":code,"active":True})
            self.old.capabilities.add(cap)
        self.receipt = AuditLog.objects.create(actor_type="owner",actor_id=str(self.owner.pk),
            action=HANDOFF,target_type="Agent",target_id=str(self.old.pk),trace_id="handoff-evidence",
            after_state={"legacy_code":LEGACY,"canonical_bot_code":BOT_CODE,
                "live_inventory_receipt_id":"inventory-receipt","canonical_successor_receipt_id":"successor-receipt",
                **{k:True for k in REQUIRED}})
        approval = ApprovalRequest.objects.create(action_type="merge_legacy_executor",target_type="Agent",
            target_id=str(self.old.pk),reason="exact transfer",requested_by=self.owner,status="approved")
        self.grant = ApprovalService().issue_grant(approval.pk,self.owner.pk,scope={
            "action":"merge_legacy_executor","agent_code":LEGACY,"canonical_bot_code":BOT_CODE,
            "live_handoff_receipt":self.receipt.trace_id})

    def test_atomic_transfer_preserves_history_and_enables_canonical(self):
        task = AgentTask.objects.create(agent=self.old,action_type="income_revenue_verify",status="completed")
        result = transfer(self.grant.pk,self.receipt.pk)
        self.old.refresh_from_db()
        task.refresh_from_db()
        self.grant.refresh_from_db()
        self.assertFalse(self.old.active)
        self.assertEqual(task.agent_id,self.old.pk)
        self.assertIsNotNone(self.grant.used_at)
        self.assertEqual(economic_owner_code(),BOT_CODE)
        self.assertEqual(result["tasks_deleted"],0)

    def test_pending_work_blocks_without_consuming_grant(self):
        AgentTask.objects.create(agent=self.old,action_type="income_market_research",status="queued")
        with self.assertRaisesRegex(CommandError,"PENDING_TASKS"):
            transfer(self.grant.pk,self.receipt.pk)
        self.old.refresh_from_db()
        self.grant.refresh_from_db()
        self.assertTrue(self.old.active)
        self.assertIsNone(self.grant.used_at)

    def test_wrong_receipt_blocks(self):
        with self.assertRaisesRegex(CommandError,"LIVE_EVIDENCE"):
            transfer(self.grant.pk,0)
        self.grant.refresh_from_db()
        self.assertIsNone(self.grant.used_at)
