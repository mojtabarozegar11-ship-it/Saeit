"""Regression coverage for bounded factory staging scheduling."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core.management.commands.factory_staging_tick import Command
from core.models import Agent, AgentTask, FactoryRun


@override_settings(SAEIT_ENV="staging")
class FactoryStagingTickSchedulingTests(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(code="tick-test-agent", name="Tick test agent", mission="test")

    def run_record(self, suffix):
        return FactoryRun.objects.create(
            run_id="tick-test-" + suffix, goal="Test scheduling",
            constraints={"source_stage": "opportunity_discovery"},
        )

    def tick(self):
        with patch("core.management.commands.factory_staging_tick.call_command") as call, patch(
            "core.management.commands.factory_staging_tick.RecoveryScheduler"
        ) as scheduler:
            scheduler.return_value.recover.return_value = SimpleNamespace(recovered=0, failed=0)
            Command().handle(max_runs=1, max_steps=1)
        return [c.kwargs["run_id"] for c in call.call_args_list if c.args and c.args[0] == "autonomous_master_loop"]

    def test_delayed_queued_run_does_not_starve_due_run(self):
        waiting = self.run_record("waiting")
        ready = self.run_record("ready")
        AgentTask.objects.create(
            agent=self.agent, factory_run=waiting, action_type="product_research",
            status="queued", next_retry_at=timezone.now() + timedelta(hours=2),
        )
        AgentTask.objects.create(
            agent=self.agent, factory_run=ready, action_type="product_research",
            status="queued", next_retry_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertEqual(self.tick(), [ready.run_id])

    def test_waiting_run_becomes_eligible_when_due(self):
        waiting = self.run_record("later")
        task = AgentTask.objects.create(
            agent=self.agent, factory_run=waiting, action_type="product_research",
            status="queued", next_retry_at=timezone.now() + timedelta(hours=2),
        )
        self.assertEqual(self.tick(), [])
        task.next_retry_at = timezone.now() - timedelta(seconds=1)
        task.save(update_fields=["next_retry_at"])
        self.assertEqual(self.tick(), [waiting.run_id])

    def test_selected_runs_rotate(self):
        first = self.run_record("first")
        second = self.run_record("second")
        self.assertEqual(self.tick(), [first.run_id])
        self.assertEqual(self.tick(), [second.run_id])
