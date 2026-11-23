"""Read-only operational status regression tests; no network or publication."""
import io
import json
from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.management.commands.mojtaba_capability_status import capability_snapshot
from core.models import Agent, AgentTask
from core.newsletter_models import NewsletterStory, NewsletterSubmission
from core.knowledge_agent_models import KnowledgeAgentRun


class CanonicalCapabilityStatusTests(TestCase):
    def test_snapshot_does_not_create_agents_tasks_or_content(self):
        before = (
            Agent.objects.count(),
            AgentTask.objects.count(),
            NewsletterStory.objects.count(),
            NewsletterSubmission.objects.count(),
            KnowledgeAgentRun.objects.count(),
        )
        output = io.StringIO()
        call_command("mojtaba_capability_status", stdout=output)
        data = json.loads(output.getvalue())
        after = (
            Agent.objects.count(),
            AgentTask.objects.count(),
            NewsletterStory.objects.count(),
            NewsletterSubmission.objects.count(),
            KnowledgeAgentRun.objects.count(),
        )
        self.assertEqual(before, after)
        self.assertEqual(data["scope"], "DJANGO_DATABASE_READ_ONLY")
        self.assertFalse(data["publication_live_verified"])
        self.assertFalse(data["host_cron_verified"])
        self.assertFalse(data["payment_and_revenue_verified"])
        self.assertIn("blockers", data)

    def test_stale_agent_work_is_reported_without_mutating_task(self):
        central, _ = Agent.objects.get_or_create(
            code="mojtaba-bot-ai",
            defaults={"name": "Central", "mission": "central", "active": True},
        )
        task = AgentTask.objects.create(
            agent=central, action_type="monitoring", status="running",
        )
        stale_time = timezone.now() - timedelta(hours=2)
        AgentTask.objects.filter(pk=task.pk).update(updated_at=stale_time)
        snapshot = capability_snapshot()
        task.refresh_from_db()
        self.assertEqual(task.status, "running")
        self.assertEqual(task.updated_at, stale_time)
        self.assertGreaterEqual(snapshot["runtime_tasks"]["stale_running_over_15_minutes"], 1)
        self.assertIn("STALE_RUNNING_AGENT_TASKS", snapshot["blockers"])
        self.assertFalse(snapshot["publication_live_verified"])

    def test_failed_tasks_are_visible_but_not_claimed(self):
        central, _ = Agent.objects.get_or_create(
            code="mojtaba-bot-ai",
            defaults={"name": "Central", "mission": "central", "active": True},
        )
        task = AgentTask.objects.create(agent=central, status="failed", action_type="review")
        snapshot = capability_snapshot()
        task.refresh_from_db()
        self.assertEqual(task.status, "failed")
        self.assertGreaterEqual(snapshot["runtime_tasks"]["failed"], 1)
        self.assertIn("FAILED_AGENT_TASKS_REQUIRE_REVIEW", snapshot["blockers"])

    def test_task_health_is_an_explicit_bounded_sample_not_full_census(self):
        central, _ = Agent.objects.get_or_create(
            code="mojtaba-bot-ai",
            defaults={"name": "Central", "mission": "central", "active": True},
        )
        # This older failure falls outside the most recent 128 rows, which
        # means an observed sample of zero failures is NOT proof of zero.
        old_failure = AgentTask.objects.create(
            agent=central, status="failed", action_type="legacy-review",
        )
        AgentTask.objects.bulk_create([
            AgentTask(agent=central, status="completed", action_type="recent")
            for _ in range(130)
        ])
        with patch("core.observability.RuntimeObservability.snapshot",
                   side_effect=AssertionError("full historical census called")) as full_scan:
            report = capability_snapshot()
        full_scan.assert_not_called()
        health = report["runtime_tasks"]
        self.assertEqual(health["sampled_task_rows"], 128)
        self.assertEqual(health["sample_limit"], 128)
        self.assertFalse(health["complete_population_verified"])
        self.assertEqual(health["failed"], 0)
        self.assertIn("AGENT_TASK_FULL_CENSUS_UNVERIFIED", report["blockers"])
        old_failure.refresh_from_db()
        self.assertEqual(old_failure.status, "failed")

    def test_command_is_readonly_and_reports_sample_scope(self):
        central, _ = Agent.objects.get_or_create(
            code="mojtaba-bot-ai",
            defaults={"name": "Central", "mission": "central", "active": True},
        )
        AgentTask.objects.create(agent=central, status="queued", action_type="review")
        with patch("core.observability.RuntimeObservability.snapshot",
                   side_effect=AssertionError("full status aggregation")):
            report = capability_snapshot()
        self.assertEqual(report["runtime_tasks"]["queued"], 1)
        self.assertEqual(
            report["runtime_tasks"]["metric_scope"],
            "LATEST_PRIMARY_KEY_SAMPLE_NOT_FULL_TASK_COUNTS",
        )
        self.assertFalse(report["runtime_tasks"]["complete_population_verified"])

    def test_missing_owner_is_a_blocker_not_an_implicit_provision(self):
        Agent.objects.filter(code="mojtaba-bot-ai").update(active=False)
        report = capability_snapshot()
        self.assertFalse(report["canonical_owner_active"])
        self.assertIn("CANONICAL_OWNER_INACTIVE", report["blockers"])
        self.assertFalse(Agent.objects.filter(code="mojtaba-bot-ai", active=True).exists())

    def test_active_legacy_and_legacy_weather_are_reported_not_revived(self):
        legacy, _ = Agent.objects.get_or_create(
            code="content-director",
            defaults={"name": "Legacy Content", "mission": "retired"},
        )
        legacy.active = True
        legacy.save(update_fields=["active"])
        now = timezone.localdate().isoformat()
        NewsletterStory.objects.create(
            agent=legacy, story_type="report", title="Prior weather report",
            slug="weather-prior-legacy", summary="Prior source summary",
            body="Prior weather content", fingerprint=f"weather-iran-{now}",
            status="draft",
        )
        report = capability_snapshot()
        self.assertIn("content-director", report["active_legacy_content_codes"])
        self.assertIn("LEGACY_CONTENT_AGENT_ACTIVE", report["blockers"])
        self.assertIn("WEATHER_OWNED_BY_LEGACY_AGENT", report["blockers"])
        legacy.refresh_from_db()
        self.assertTrue(legacy.active)

    def test_unreconciled_legacy_tasks_are_counted_without_claiming_them(self):
        legacy, _ = Agent.objects.get_or_create(
            code="knowledge-content-director",
            defaults={"name": "Knowledge Legacy", "mission": "read-only"},
        )
        task = AgentTask.objects.create(
            agent=legacy, status="blocked", action_type="knowledge_content_generation",
        )
        report = capability_snapshot()
        self.assertGreaterEqual(report["nonterminal_legacy_content_tasks"], 1)
        self.assertIn("UNRECONCILED_LEGACY_CONTENT_TASKS", report["blockers"])
        task.refresh_from_db()
        self.assertEqual(task.status, "blocked")
