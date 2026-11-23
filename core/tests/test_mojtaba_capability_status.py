"""Read-only operational status regression tests; no network or publication."""
import io
import json

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
