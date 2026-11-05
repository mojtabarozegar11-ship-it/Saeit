from datetime import timedelta
from io import StringIO

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

    def add_task(self, capability, created_at):
        task = AgentTask.objects.create(
            agent=self.agent,
            capability_code=capability,
            status="completed",
            output_data={"verified_effect": True},
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

        self.add_task("income_market_research", now - timedelta(hours=1))
        state = brain.observe()
        self.assertTrue(state["market_research_complete"])
        self.assertFalse(state["opportunity_scored"])

        self.add_task("income_opportunity_score", now)
        state = brain.observe()
        self.assertTrue(state["market_research_complete"])
        self.assertTrue(state["opportunity_scored"])

    def test_self_improvement_is_the_first_master_objective(self):
        brain = AutonomousBrain()
        state = brain.observe()
        self.assertFalse(state["self_improvement_complete"])
        self.assertEqual(brain.candidates(state)[0].action, "master_self_improvement")

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
