"""DB-backed approval-grant replay and escalation tests for mojtaba.bot.ai.

Uses Django's isolated test DB. No real transaction, message, payment, broker,
production scheduler or external connector is touched.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from core.economic_trade_email import queue_trade_email
from core.trade_outbox_scope import message_digest
from django.utils import timezone

from core.approval import ApprovalService
from core.models import Agent, AgentTask, ApprovalGrant, ApprovalRequest, AuditLog


class GrantBindingDatabaseTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser(
            username="owner-grant-test", password="offline-password",
            email="offline@example.invalid",
        )
        self.service = ApprovalService()
        self.approval = ApprovalRequest.objects.create(
            action_type="publish", target_type="KnowledgeArticle",
            target_id="7", reason="One named article only", risk="high",
            status="approved", requested_by=self.owner,
        )
        self.scope = {"action": "publish", "target": "knowledge:7"}

    def issue(self, *, approval=None, scope=None, actor_id=None, ttl_seconds=300):
        return self.service.issue_grant(
            (approval or self.approval).pk,
            self.owner.pk if actor_id is None else actor_id,
            self.scope if scope is None else scope,
            ttl_seconds=ttl_seconds,
        )

    def test_01_exact_issue_and_consume(self):
        grant = self.issue()
        result = self.service.authorize_grant(grant.pk, self.scope)
        self.assertIsNotNone(result.used_at)
        self.assertEqual(AuditLog.objects.filter(action="approval_grant_consumed").count(), 1)

    def test_02_duplicate_grant_denied(self):
        self.issue()
        with self.assertRaisesRegex(ValueError, "ALREADY_ISSUED"):
            self.issue()
        self.assertEqual(ApprovalGrant.objects.count(), 1)

    def test_03_used_grant_cannot_replay(self):
        g = self.issue()
        self.service.authorize_grant(g.pk, self.scope)
        with self.assertRaisesRegex(ValueError, "already been used"):
            self.service.authorize_grant(g.pk, self.scope)

    def test_04_wrong_resource_rejected_at_issue(self):
        with self.assertRaises(ValueError):
            self.issue(scope={"action": "publish", "target": "knowledge:8"})
        self.assertFalse(ApprovalGrant.objects.exists())

    def test_05_payment_action_escalation_rejected_at_issue(self):
        with self.assertRaises(ValueError):
            self.issue(scope={"action": "payment", "target": "order:7"})

    def test_06_extra_field_rejected_at_issue(self):
        with self.assertRaises(ValueError):
            self.issue(scope={**self.scope, "override": True})

    def test_07_non_superuser_cannot_issue(self):
        self.owner.is_superuser = False
        self.owner.save(update_fields=["is_superuser"])
        with self.assertRaises(ValueError):
            self.issue()

    def test_08_inactive_owner_cannot_issue(self):
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        with self.assertRaises(ValueError):
            self.issue()

    def test_09_different_actor_id_cannot_issue(self):
        with self.assertRaises(ValueError):
            self.issue(actor_id=self.owner.pk + 1)

    def test_10_bool_actor_id_cannot_issue(self):
        with self.assertRaises(ValueError):
            self.issue(actor_id=True)

    def test_11_pending_approval_cannot_issue(self):
        self.approval.status = "pending"
        self.approval.save(update_fields=["status"])
        with self.assertRaises(ValueError):
            self.issue()

    def test_12_ttl_below_minimum_rejected(self):
        with self.assertRaises(ValueError):
            self.issue(ttl_seconds=29)

    def test_13_ttl_above_maximum_rejected(self):
        with self.assertRaises(ValueError):
            self.issue(ttl_seconds=901)

    def test_14_boolean_ttl_rejected(self):
        with self.assertRaises(ValueError):
            self.issue(ttl_seconds=True)

    def test_15_string_ttl_rejected(self):
        with self.assertRaises(ValueError):
            self.issue(ttl_seconds="300")

    def test_16_ttl_bound_30_allowed(self):
        self.assertIsNotNone(self.issue(ttl_seconds=30).pk)

    def test_17_ttl_bound_900_allowed(self):
        self.assertIsNotNone(self.issue(ttl_seconds=900).pk)

    def test_18_required_scope_cannot_be_subset(self):
        grant = self.issue()
        with self.assertRaises(ValueError):
            self.service.authorize_grant(grant.pk, {"action": "publish"})
        grant.refresh_from_db()
        self.assertIsNone(grant.used_at)

    def test_19_required_scope_cannot_have_extra(self):
        grant = self.issue()
        with self.assertRaises(ValueError):
            self.service.authorize_grant(grant.pk, {**self.scope, "cross_app": True})

    def test_20_required_scope_cannot_be_missing(self):
        grant = self.issue()
        with self.assertRaises(ValueError):
            self.service.authorize_grant(grant.pk)

    def test_21_revoked_approval_blocks_consumption(self):
        grant = self.issue()
        self.approval.status = "rejected"
        self.approval.save(update_fields=["status"])
        with self.assertRaises(ValueError):
            self.service.authorize_grant(grant.pk, self.scope)

    def test_22_owner_deactivation_blocks_consumption(self):
        grant = self.issue()
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        with self.assertRaises(ValueError):
            self.service.authorize_grant(grant.pk, self.scope)

    def test_23_owner_demotion_blocks_consumption(self):
        grant = self.issue()
        self.owner.is_superuser = False
        self.owner.save(update_fields=["is_superuser"])
        with self.assertRaises(ValueError):
            self.service.authorize_grant(grant.pk, self.scope)

    def test_24_approval_actor_mismatch_blocks_consumption(self):
        other = get_user_model().objects.create_superuser(
            username="other-grant-owner", email="other@example.invalid",
            password="offline-password",
        )
        grant = self.issue()
        self.approval.requested_by = other
        self.approval.save(update_fields=["requested_by"])
        with self.assertRaises(ValueError):
            self.service.authorize_grant(grant.pk, self.scope)

    def test_25_tampered_persisted_scope_blocks_consumption(self):
        grant = self.issue()
        grant.scope = {"action": "payment", "target": "order:7"}
        grant.save(update_fields=["scope"])
        with self.assertRaises(ValueError):
            self.service.authorize_grant(grant.pk, grant.scope)

    def test_26_expired_grant_blocks_consumption(self):
        grant = self.issue()
        grant.expires_at = timezone.now() - timedelta(minutes=1)
        grant.save(update_fields=["expires_at"])
        with self.assertRaisesRegex(ValueError, "expired"):
            self.service.authorize_grant(grant.pk, self.scope)

    def test_27_mailbox_action_bound(self):
        with override_settings(COMPANY_TRADE_EMAIL="trade@example.invalid"):
            outbox = queue_trade_email(
                recipient="buyer@example.invalid", subject="Requested quote",
                body="Here is the scope requested by the buyer.",
                trade_context={
                    "contact_basis": "requested_quote",
                    "basis_evidence_sha256": "a" * 64,
                },
            )
        outbox.mailbox.active = True
        outbox.mailbox.allow_outbound = True
        outbox.mailbox.save(update_fields=["active", "allow_outbound"])
        approval = ApprovalRequest.objects.create(
            action_type="external_write", target_type="TradeEmailOutbox",
            target_id=str(outbox.pk), reason="One exact queued B2B message",
            risk="high", status="approved", requested_by=self.owner,
        )
        scope = {
            "action": "external_write", "outbox_id": outbox.pk,
            "message_digest": message_digest(outbox),
        }
        grant = self.issue(approval=approval, scope=scope)
        self.assertEqual(self.service.authorize_grant(grant.pk, scope).scope, scope)

    def test_28_payment_order_bound(self):
        approval = ApprovalRequest.objects.create(
            action_type="payment", target_type="Order", target_id="9",
            reason="One order, no provider settlement claim",
            risk="critical", status="approved", requested_by=self.owner,
        )
        scope = {"action": "payment", "target": "order:9"}
        grant = self.issue(approval=approval, scope=scope)
        self.assertEqual(self.service.authorize_grant(grant.pk, scope).scope, scope)

    def test_29_paid_model_run_matches_task(self):
        bot = Agent.objects.create(
            code="mojtaba-bot-ai", name="Canonical bot",
            mission="One approved research action", active=True,
        )
        task = AgentTask.objects.create(
            agent=bot, action_type="knowledge_content_generation",
            input_data={"run_id": 11}, status="queued",
        )
        approval = ApprovalRequest.objects.create(
            action_type="knowledge_content_generation", target_type="AgentTask",
            target_id=str(task.pk), reason="One paid draft",
            risk="high", status="approved", requested_by=self.owner,
        )
        scope = {"action": "knowledge_content_generation", "run_id": 11, "paid_model": True}
        grant = self.issue(approval=approval, scope=scope)
        self.assertIsNotNone(self.service.authorize_grant(grant.pk, scope).used_at)

    def test_30_paid_model_cross_run_blocked_at_issue(self):
        bot = Agent.objects.create(
            code="mojtaba-bot-ai", name="Canonical bot",
            mission="One approved research action", active=True,
        )
        task = AgentTask.objects.create(
            agent=bot, action_type="knowledge_content_generation",
            input_data={"run_id": 11}, status="queued",
        )
        approval = ApprovalRequest.objects.create(
            action_type="knowledge_content_generation", target_type="AgentTask",
            target_id=str(task.pk), reason="One paid draft",
            risk="high", status="approved", requested_by=self.owner,
        )
        scope = {"action": "knowledge_content_generation", "run_id": 12, "paid_model": True}
        with self.assertRaisesRegex(ValueError, "TASK_RUN_MISMATCH"):
            self.issue(approval=approval, scope=scope)


