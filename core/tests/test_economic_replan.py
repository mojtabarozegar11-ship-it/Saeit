"""Existing economic queue reconciliation; no live execution."""
from django.test import TestCase
from core.economic_replan import reconcile_economic_precondition
from core.economic_owner import LEGACY
from core.models import Agent, AgentTask, AgentCapability, AuditLog

ERROR = "No designed offer exists; run income_offer_design first."


class EconomicReplanTests(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(code=LEGACY, name="Legacy", mission="Existing lane", active=True)
        cap = AgentCapability.objects.create(code="income_offer_design", name="Offer", risk_level="low", active=True)
        self.agent.capabilities.add(cap)
        self.task = AgentTask.objects.create(agent=self.agent, action_type="income_mvp_build",
            capability_code="income_mvp_build", status="queued", attempt_count=1, max_attempts=3,
            output_data={"error":ERROR}, input_data={"historical":"preserve"})
        self.specs = {"income_offer_design":{"enabled":True,"risk":"medium"}}

    def reconcile(self, error=None):
        return reconcile_economic_precondition(task_id=self.task.pk, agent_id=self.agent.pk,
            previous_attempt_count=0, error=error if error is not None else ValueError(ERROR),
            tool_specs=self.specs)

    def test_known_pre_effect_failure_creates_one_replacement(self):
        self.assertEqual(self.reconcile(), "prerequisite_ready")
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "cancelled")
        self.assertEqual(self.task.input_data, {"historical":"preserve"})
        self.assertEqual(self.task.output_data["error"], ERROR)
        new = AgentTask.objects.get(pk=self.task.output_data["replacement_task_id"])
        self.assertEqual(new.risk_snapshot, "medium")
        self.assertEqual(new.status, "queued")
        self.assertEqual(new.capability_code, "income_offer_design")
        self.assertEqual(self.reconcile(), "review_task_state_changed_or_exhausted")
        self.assertEqual(AgentTask.objects.count(), 2)
        self.assertEqual(AuditLog.objects.filter(action="economic_precondition_reconciled").count(), 1)

    def test_existing_fresh_prerequisite_reused(self):
        other = AgentTask.objects.create(agent=self.agent, action_type="income_offer_design",
            capability_code="income_offer_design", risk_snapshot="medium", status="queued")
        self.assertEqual(self.reconcile(), "prerequisite_ready")
        self.task.refresh_from_db()
        self.assertEqual(self.task.output_data["replacement_task_id"], other.pk)
        self.assertFalse(self.task.output_data["replan_created"])
        self.assertEqual(AgentTask.objects.count(), 2)

    def test_blocked_prerequisite_does_not_cancel_original(self):
        AgentTask.objects.create(agent=self.agent, action_type="income_offer_design",
            capability_code="income_offer_design", risk_snapshot="medium", status="blocked")
        self.assertEqual(self.reconcile(), "review_other_pending_work")
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "queued")
        self.assertEqual(AgentTask.objects.count(), 2)

    def test_exhausted_task_unchanged(self):
        self.task.max_attempts = 1
        self.task.status = "failed"
        self.task.save(update_fields=["max_attempts","status"])
        self.assertEqual(self.reconcile(), "review_task_state_changed_or_exhausted")
        self.assertEqual(AgentTask.objects.count(), 1)

    def test_approval_boundary_and_unavailable_capability(self):
        self.specs["income_offer_design"]["risk"] = "high"
        self.assertEqual(self.reconcile(), "review_prerequisite_approval_required")
        self.specs.clear()
        self.assertEqual(self.reconcile(), "review_prerequisite_unavailable")
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "queued")
        self.assertEqual(AgentTask.objects.count(), 1)

    def test_unknown_error_does_not_replan(self):
        self.assertEqual(self.reconcile(RuntimeError(ERROR)), "review_unknown_error")
        self.assertEqual(self.reconcile(ValueError("prefix " + ERROR)), "review_unverified_precondition")
        self.assertEqual(AgentTask.objects.count(), 1)
