from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.autonomous_brain import AutonomousBrain
from core.models import Agent, AgentTask


def test_market_research_and_scoring_are_verified_before_offer_design():
    brain = AutonomousBrain()
    state = {
        "unfinished_tasks": 0,
        "failed_tasks": 0,
        "market_research_complete": False,
        "opportunity_scored": False,
        "active_products": 0,
        "offer_designed": 0,
        "mvp_built": 0,
        "growth_ready": 0,
        "orders": 0,
        "paid_orders": 0,
        "self_improvement_complete": True,
    }

    assert brain.candidates(state)[0].action == "income_market_research"

    # A successful internal inventory is not proof that external buyers exist.
    state["market_inventory_measured"] = True
    assert brain.candidates(state)[0].action == "await_external_market_evidence"

    state["market_research_complete"] = True
    assert brain.candidates(state)[0].action == "income_opportunity_score"

    state["opportunity_scored"] = True
    assert brain.candidates(state)[0].action == "income_offer_design"



class VerifiedEconomicCycleTests(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(
            code="economic-master-agent",
            name="Economic Master Agent",
            mission="Test-only economic cycle",
            active=True,
        )

    def add_task(self, capability, created_at, *, market_validation=False, inventory=False):
        output = {"verified_effect": True}
        if market_validation:
            output["market_validation"] = {
                "status": "independently_verified",
                "source_type": "external_customer_demand",
                "validated_by": "independent_market_evidence_adapter",
                "source_id": "customer-signal-123",
            }
        if inventory:
            output["evidence"] = {"kind": "database_measurement"}
        task = AgentTask.objects.create(
            agent=self.agent,
            capability_code=capability,
            status="completed",
            output_data=output,
        )
        AgentTask.objects.filter(pk=task.pk).update(created_at=created_at)
        return task

    def test_prerequisite_evidence_must_follow_latest_offer_and_be_ordered(self):
        now = timezone.now()
        self.add_task("master_self_improvement", now - timedelta(days=4))
        self.add_task("income_market_research", now - timedelta(days=3))
        self.add_task("income_opportunity_score", now - timedelta(days=2))
        self.add_task("income_offer_design", now - timedelta(days=1))

        brain = AutonomousBrain()
        state = brain.observe()
        self.assertFalse(state["market_research_complete"])
        self.assertTrue(state["self_improvement_complete"])
        self.assertFalse(state["opportunity_scored"])

        self.add_task("income_opportunity_score", now - timedelta(hours=2))
        state = brain.observe()
        self.assertFalse(state["market_research_complete"])
        self.assertFalse(state["opportunity_scored"])

        self.add_task("income_market_research", now - timedelta(hours=1), inventory=True)
        state = brain.observe()
        self.assertTrue(state["market_inventory_measured"])
        self.assertFalse(state["market_research_complete"])
        self.assertFalse(state["opportunity_scored"])

        self.add_task("income_market_research", now - timedelta(minutes=30), market_validation=True)
        state = brain.observe()
        self.assertTrue(state["market_research_complete"])

        self.add_task("income_opportunity_score", now)
        state = brain.observe()
        self.assertTrue(state["market_research_complete"])
        self.assertTrue(state["opportunity_scored"])

    def test_self_improvement_is_the_first_master_objective(self):
        brain = AutonomousBrain()
        state = brain.observe()
        self.assertFalse(state["self_improvement_complete"])
        self.assertEqual(brain.candidates(state)[0].action, "master_self_improvement")

    def test_unverified_self_improvement_does_not_requeue_same_work(self):
        AgentTask.objects.create(
            agent=self.agent, action_type="master_self_improvement",
            capability_code="master_self_improvement", status="completed",
            output_data={"verified_effect": False},
        )
        state = AutonomousBrain().observe()
        self.assertTrue(state["self_improvement_unverified"])
        self.assertEqual(
            AutonomousBrain().candidates(state)[0].action,
            "await_external_self_improvement_review",
        )
        output = StringIO()
        call_command("online_income_cycle", stdout=output)
        self.assertEqual(AgentTask.objects.filter(agent=self.agent).count(), 1)
        self.assertIn("BRAIN_EXTERNAL_BOUNDARY", output.getvalue())

    def test_master_loop_stops_after_unverified_execution(self):
        task = AgentTask.objects.create(
            agent=self.agent, action_type="master_self_improvement",
            capability_code="master_self_improvement", status="queued",
        )
        unverified = SimpleNamespace(
            pk=task.pk, action_type="master_self_improvement",
            output_data={"verified_effect": False}, refresh_from_db=lambda: None,
        )
        output = StringIO()
        with patch("core.management.commands.autonomous_master_loop.WorkerRunner") as worker:
            worker.return_value.run.return_value = unverified
            gateway = SimpleNamespace(describe=lambda: {"master_self_improvement": {"enabled": True}})
            with patch("core.management.commands.autonomous_master_loop.build_economic_gateway", return_value=gateway):
                call_command("autonomous_master_loop", "--max-steps", "20", stdout=output)
            self.assertEqual(worker.return_value.run.call_count, 1)
        self.assertIn("AUTO_UNVERIFIED_STOP", output.getvalue())

    def test_master_loop_never_dispatches_queued_task_for_inactive_agent(self):
        self.agent.active = False
        self.agent.save(update_fields=["active"])
        task = AgentTask.objects.create(
            agent=self.agent, action_type="income_market_research",
            capability_code="income_market_research", status="queued",
        )
        output = StringIO()
        with patch("core.management.commands.autonomous_master_loop.WorkerRunner") as worker:
            call_command("autonomous_master_loop", "--max-steps", "1", stdout=output)
            worker.assert_not_called()
        task.refresh_from_db()
        self.assertEqual(task.status, "queued")
        self.assertIn("AUTO_BLOCKED_NO_ACTIVE_CANONICAL_BOT", output.getvalue())

    def test_master_loop_reports_unregistered_queued_capability_without_dispatch(self):
        task = AgentTask.objects.create(
            agent=self.agent, action_type="external_unreviewed_tool",
            capability_code="external_unreviewed_tool", status="queued",
        )
        output = StringIO()
        with patch("core.management.commands.autonomous_master_loop.WorkerRunner") as worker:
            call_command("autonomous_master_loop", "--max-steps", "1", stdout=output)
            worker.assert_not_called()
        task.refresh_from_db()
        self.assertEqual(task.status, "queued")
        self.assertIn("AUTO_BLOCKED_UNSUPPORTED_TASK", output.getvalue())

    def test_master_loop_never_claims_unknown_income_prefixed_tool(self):
        task = AgentTask.objects.create(
            agent=self.agent, action_type="income_unregistered_external_post",
            capability_code="income_unregistered_external_post", status="queued",
        )
        output = StringIO()
        with patch("core.management.commands.autonomous_master_loop.WorkerRunner") as worker:
            call_command("autonomous_master_loop", "--max-steps", "1", stdout=output)
            worker.return_value.run.assert_not_called()
        task.refresh_from_db()
        self.assertEqual(task.status, "queued")
        self.assertEqual(task.attempt_count, 0)
        self.assertIn("AUTO_BLOCKED_UNSUPPORTED_TASK", output.getvalue())

    def test_master_loop_skips_mismatched_action_snapshot(self):
        task = AgentTask.objects.create(
            agent=self.agent, action_type="income_profit_optimize",
            capability_code="income_market_research", status="queued",
        )
        output = StringIO()
        with patch("core.management.commands.autonomous_master_loop.WorkerRunner") as worker:
            call_command("autonomous_master_loop", "--max-steps", "1", stdout=output)
            worker.return_value.run.assert_not_called()
        task.refresh_from_db()
        self.assertEqual(task.status, "queued")
        self.assertEqual(task.attempt_count, 0)
        self.assertIn("AUTO_BLOCKED_UNSUPPORTED_TASK", output.getvalue())

    def test_stale_running_task_is_recovered_without_duplicate_task(self):
        task = AgentTask.objects.create(
            agent=self.agent, action_type="income_market_research",
            capability_code="income_market_research", status="running",
            attempt_count=1, max_attempts=3, execution_id="obsolete-worker",
        )
        AgentTask.objects.filter(pk=task.pk).update(
            updated_at=timezone.now() - timedelta(minutes=20)
        )
        output = StringIO()
        call_command("online_income_cycle", stdout=output)
        task.refresh_from_db()
        self.assertEqual(task.status, "queued")
        self.assertEqual(task.execution_id, "")
        self.assertEqual(AgentTask.objects.filter(agent=self.agent).count(), 1)
        self.assertIn("BRAIN_RECOVERED", output.getvalue())

    def test_blocked_task_requires_review_without_spawning_replacement(self):
        task = AgentTask.objects.create(
            agent=self.agent, action_type="income_growth_experiment",
            capability_code="income_growth_experiment", status="blocked",
        )
        output = StringIO()
        call_command("online_income_cycle", stdout=output)
        self.assertIn(f"BRAIN_BLOCKED task={task.pk}", output.getvalue())
        self.assertEqual(AgentTask.objects.filter(agent=self.agent).count(), 1)

    def test_dry_run_does_not_recover_stale_running_task(self):
        task = AgentTask.objects.create(
            agent=self.agent, action_type="income_market_research",
            capability_code="income_market_research", status="running",
            attempt_count=1, execution_id="old-worker",
        )
        AgentTask.objects.filter(pk=task.pk).update(
            updated_at=timezone.now() - timedelta(minutes=25)
        )
        call_command("online_income_cycle", "--dry-run", stdout=StringIO())
        task.refresh_from_db()
        self.assertEqual(task.status, "running")
        self.assertEqual(task.execution_id, "old-worker")

    def test_idle_dry_run_does_not_lock_master_agent(self):
        # Preview must remain safe even while live dispatch is taking place.
        with patch("django.db.models.query.QuerySet.select_for_update",
                   side_effect=AssertionError("dry-run must not lock database rows")):
            output, errors = StringIO(), StringIO()
            call_command("online_income_cycle", "--dry-run",
                         stdout=output, stderr=errors)
        self.assertEqual(AgentTask.objects.filter(agent=self.agent).count(), 0)
        self.assertIn("BRAIN_", output.getvalue() + errors.getvalue())

    def test_exhausted_stale_task_fails_without_infinite_retry(self):
        task = AgentTask.objects.create(
            agent=self.agent, action_type="income_market_research",
            capability_code="income_market_research", status="running",
            attempt_count=3, max_attempts=3, execution_id="expired-worker",
        )
        AgentTask.objects.filter(pk=task.pk).update(
            updated_at=timezone.now() - timedelta(minutes=30)
        )
        output = StringIO()
        call_command("online_income_cycle", stdout=output)
        task.refresh_from_db()
        self.assertEqual(task.status, "failed")
        self.assertEqual(AgentTask.objects.filter(agent=self.agent).count(), 1)
        self.assertIn("status=failed", output.getvalue())

    def test_recent_running_task_is_not_reclaimed(self):
        task = AgentTask.objects.create(
            agent=self.agent, action_type="income_market_research",
            capability_code="income_market_research", status="running",
            attempt_count=1, execution_id="live-worker",
        )
        output = StringIO()
        call_command("online_income_cycle", stdout=output)
        task.refresh_from_db()
        self.assertEqual(task.status, "running")
        self.assertEqual(task.execution_id, "live-worker")
        self.assertIn("awaiting_heartbeat_or_recovery", output.getvalue())


def test_failed_self_improvement_does_not_block_commercial_pipeline():
    brain = AutonomousBrain()
    state = {
        "unfinished_tasks": 0,
        "failed_tasks": 3,
        "market_research_complete": False,
        "opportunity_scored": False,
        "active_products": 0,
        "offer_designed": 0,
        "mvp_built": 0,
        "growth_ready": 0,
        "orders": 0,
        "paid_orders": 0,
        "self_improvement_complete": False,
        "self_improvement_failed": True,
    }

    assert brain.candidates(state)[0].action == "income_market_research"


def test_existing_catalog_without_real_customer_channel_stops_noop_loop():
    state = {
        "unfinished_tasks": 0, "market_research_complete": True,
        "opportunity_scored": True, "self_improvement_complete": True,
        "active_products": 4, "offer_designed": 0, "mvp_built": 0,
        "growth_ready": 0, "orders": 0, "paid_orders": 0,
        "financial_event_needs_reconcile": False,
    }
    action = AutonomousBrain().candidates(state)[0].action
    assert action == "await_external_acquisition"


def test_growth_ready_without_new_money_evidence_does_not_repeat_profit_review():
    state = {
        "unfinished_tasks": 0, "market_research_complete": True,
        "opportunity_scored": True, "self_improvement_complete": True,
        "active_products": 0, "offer_designed": 0, "mvp_built": 0,
        "growth_ready": 1, "orders": 0, "paid_orders": 0,
        "financial_event_needs_reconcile": False,
    }
    brain = AutonomousBrain()
    assert brain.candidates(state)[0].action == "await_external_acquisition"
    state["financial_event_needs_reconcile"] = True
    assert brain.candidates(state)[0].action == "income_revenue_verify"


def test_new_payment_evidence_takes_priority_over_internal_research():
    state = {
        "unfinished_tasks": 0, "market_research_complete": False,
        "opportunity_scored": False, "self_improvement_complete": False,
        "active_products": 0, "offer_designed": 0, "mvp_built": 0,
        "growth_ready": 0, "orders": 1, "paid_orders": 1,
        "financial_event_needs_reconcile": True,
    }
    assert AutonomousBrain().candidates(state)[0].action == "income_revenue_verify"


class CanonicalBrainHandoffTests(TestCase):
    """Read old receipts, but only the active master owns executable work."""

    def setUp(self):
        from core.canonical_bot_identity import RUNTIME_CODES
        Agent.objects.filter(code__in=RUNTIME_CODES).delete()

    def test_new_canonical_master_is_not_hidden_by_legacy_filter(self):
        master = Agent.objects.create(
            code="mojtaba-bot-ai", name="Mojtaba.bot.ai", mission="Single", active=True,
        )
        AgentTask.objects.create(
            agent=master, capability_code="master_self_improvement", status="completed",
            output_data={"verified_effect": True},
        )
        AgentTask.objects.create(
            agent=master, capability_code="income_market_research", status="completed",
            output_data={"verified_effect": True,
                         "evidence": {"kind": "database_measurement"}},
        )
        state = AutonomousBrain().observe()
        self.assertTrue(state["self_improvement_complete"])
        self.assertTrue(state["market_inventory_measured"])
        self.assertFalse(state["market_research_complete"])
        self.assertEqual(AutonomousBrain().candidates(state)[0].action,
                         "await_external_market_evidence")

    def test_completed_legacy_evidence_is_preserved_without_requeuing_work(self):
        old = Agent.objects.create(
            code="economic-master-agent", name="Legacy", mission="History", active=False,
        )
        current = Agent.objects.create(
            code="mojtaba-bot-ai", name="Mojtaba.bot.ai", mission="Single", active=True,
        )
        AgentTask.objects.create(
            agent=old, capability_code="master_self_improvement", status="completed",
            output_data={"verified_effect": True},
        )
        AgentTask.objects.create(
            agent=old, capability_code="income_market_research", status="completed",
            output_data={"verified_effect": True,
                         "evidence": {"kind": "database_measurement"}},
        )
        old_queued = AgentTask.objects.create(
            agent=old, action_type="income_opportunity_score", status="queued",
        )
        state = AutonomousBrain().observe()
        self.assertTrue(state["self_improvement_complete"])
        self.assertTrue(state["market_inventory_measured"])
        self.assertEqual(state["unfinished_tasks"], 0)
        self.assertEqual(AutonomousBrain().candidates(state)[0].action,
                         "await_external_market_evidence")
        old_queued.refresh_from_db()
        self.assertEqual(old_queued.status, "queued")
        self.assertTrue(current.active)

    def test_only_active_runtime_pending_or_failed_tasks_count(self):
        old = Agent.objects.create(
            code="economic-master-agent", name="Legacy", mission="Old", active=False,
        )
        current = Agent.objects.create(
            code="mojtaba-bot-ai", name="Mojtaba.bot.ai", mission="Current", active=True,
        )
        AgentTask.objects.create(
            agent=old, action_type="master_self_improvement", status="failed",
            capability_code="master_self_improvement",
        )
        AgentTask.objects.create(agent=old, action_type="income_market_research",
                                 status="running")
        active = AgentTask.objects.create(
            agent=current, action_type="income_market_research", status="queued",
        )
        state = AutonomousBrain().observe()
        self.assertEqual(state["unfinished_tasks"], 1)
        self.assertEqual(state["failed_tasks"], 0)
        self.assertFalse(state["self_improvement_failed"])
        self.assertEqual(AutonomousBrain().candidates(state)[0].action,
                         "continue_existing_work")
        active.status = "completed"
        active.save(update_fields=["status"])
        state = AutonomousBrain().observe()
        self.assertEqual(state["unfinished_tasks"], 0)

    def test_completed_unverified_legacy_research_cannot_unlock_sales(self):
        old = Agent.objects.create(
            code="economic-master-agent", name="Legacy", mission="Historical", active=False,
        )
        Agent.objects.create(
            code="mojtaba-bot-ai", name="Mojtaba.bot.ai", mission="Current", active=True,
        )
        AgentTask.objects.create(
            agent=old, capability_code="income_market_research", status="completed",
            output_data={"verified_effect": False,
                         "market_validation": {
                             "status": "independently_verified",
                             "source_type": "external_customer_demand",
                             "validated_by": "independent_market_evidence_adapter",
                             "source_id": "unverified",
                         }},
        )
        state = AutonomousBrain().observe()
        self.assertFalse(state["market_research_complete"])
        self.assertFalse(state["opportunity_scored"])

    def test_no_active_master_abstains_from_economic_decisions(self):
        from django.core.exceptions import ImproperlyConfigured
        with self.assertRaisesRegex(ImproperlyConfigured, "MASTER_BRAIN_NO_ACTIVE_RUNTIME"):
            AutonomousBrain().observe()

    def test_parallel_active_runtime_rows_fail_closed(self):
        from django.core.exceptions import ImproperlyConfigured
        Agent.objects.create(code="economic-master-agent", name="Legacy",
                             mission="Old", active=True)
        Agent.objects.create(code="mojtaba-bot-ai", name="Canonical",
                             mission="Current", active=True)
        with self.assertRaisesRegex(ImproperlyConfigured, "CANONICAL_BOT_MULTIPLE_ACTIVE"):
            AutonomousBrain().observe()
