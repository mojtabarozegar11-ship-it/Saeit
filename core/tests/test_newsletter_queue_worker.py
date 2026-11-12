"""Regression checks for the operational newsletter submission agent."""

import io
import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.models import Agent, AgentTask
from core.unified_bot_identity import BOT_CODE
from core.newsletter_engine import process_submission
from core.newsletter_models import NewsletterSchedule, NewsletterStory, NewsletterSubmission


class NewsletterQueueWorkerTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="newsletter_queue_owner")
        self.bot = Agent.objects.create(
            code=BOT_CODE, name="Mojtaba.bot.ai", mission="Canonical owner",
            active=True,
        )

    def submission(self, suffix):
        return NewsletterSubmission.objects.create(
            subject=f"مستندات فعالیت ثبت شده شرکت زمرد ملل - {suffix}",
            body=(f"شرح فعالیت ثبت شده و مستند {suffix}. " * 45),
            created_by=self.owner,
            requested_publish_at=timezone.now() + timedelta(days=1),
        )

    def run_queue(self, *args):
        out = io.StringIO()
        call_command("newsletter_process_queue", *args, stdout=out)
        return json.loads(out.getvalue())

    def test_processes_real_queued_submissions_without_publishing(self):
        a = self.submission("A")
        b = self.submission("B")
        receipt = self.run_queue("--limit", "2")

        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(receipt["result"]["drafted"], 2)
        self.assertEqual(receipt["result"]["inspected"], 2)
        self.assertEqual(receipt["remaining_queued"], 0)
        self.assertEqual(NewsletterStory.objects.count(), 2)
        self.assertEqual({a.status, b.status}, {"drafted"})
        self.assertEqual(NewsletterStory.objects.filter(status="draft").count(), 2)
        self.assertEqual(NewsletterStory.objects.filter(status="published").count(), 0)
        self.assertFalse(Agent.objects.filter(code="content-director").exists())
        self.assertEqual(set(NewsletterStory.objects.values_list("agent_id", flat=True)), {self.bot.pk})

    def test_batch_limit_never_claims_unselected_submissions(self):
        first = self.submission("first")
        second = self.submission("second")
        receipt = self.run_queue("--limit", "1")
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, "drafted")
        self.assertEqual(second.status, "queued")
        self.assertEqual(receipt["remaining_queued"], 1)

    def test_inflight_item_is_not_taken_over_and_drafted_item_is_idempotent(self):
        item = self.submission("inflight")
        item.status = "processing"
        item.save(update_fields=["status"])
        self.assertIsNone(process_submission(item))
        receipt = self.run_queue()
        self.assertEqual(receipt["result"]["inspected"], 0)
        self.assertEqual(receipt["preexisting_inflight"], 1)
        self.assertFalse(NewsletterStory.objects.exists())

        item.status = "queued"
        item.save(update_fields=["status"])
        story = process_submission(item)
        self.assertEqual(process_submission(item).pk, story.pk)
        self.assertEqual(NewsletterStory.objects.count(), 1)

    def test_disabled_successor_does_not_get_reactivated_or_lose_queue(self):
        agent = Agent.objects.create(
            code="content-director", name="Content Director", mission="Review", active=False
        )
        AgentTask.objects.create(agent=agent, action_type="legacy_draft", status="queued")
        item = self.submission("disabled")
        receipt = self.run_queue()
        agent.refresh_from_db()
        item.refresh_from_db()
        self.assertFalse(agent.active)
        self.assertEqual(item.status, "queued")
        self.assertEqual(receipt["result"]["held"], 1)
        self.assertFalse(NewsletterStory.objects.exists())

    def test_failed_drafting_rolls_back_claim_for_recovery(self):
        item = self.submission("retry")
        with patch("core.newsletter_engine.create_draft", side_effect=RuntimeError("internal")):
            receipt = self.run_queue()
        item.refresh_from_db()
        self.assertEqual(item.status, "queued")
        self.assertEqual(receipt["result"]["errors"], 1)
        self.assertEqual(receipt["error_types"], {"RuntimeError": 1})
        self.assertFalse(NewsletterStory.objects.exists())

    def test_inactive_legacy_without_pending_work_is_not_resurrected(self):
        old = Agent.objects.create(
            code="content-director", name="Old Content Director",
            mission="Historical story evidence", active=False,
        )
        item = self.submission("historical")
        receipt = self.run_queue("--limit", "1")
        old.refresh_from_db()
        item.refresh_from_db()
        self.assertFalse(old.active)
        self.assertEqual(item.status, "drafted")
        self.assertEqual(receipt["result"]["drafted"], 1)
        self.assertEqual(item.generated_story.agent_id, self.bot.pk)

    def test_active_legacy_holds_submission_for_verified_handoff(self):
        old = Agent.objects.create(
            code="content-director", name="Legacy worker",
            mission="Still active", active=True,
        )
        item = self.submission("active-legacy")
        receipt = self.run_queue("--limit", "1")
        item.refresh_from_db()
        old.refresh_from_db()
        self.assertTrue(old.active)
        self.assertEqual(item.status, "queued")
        self.assertEqual(receipt["result"]["held"], 1)
        self.assertEqual(NewsletterStory.objects.count(), 0)

    def test_inactive_legacy_with_unpublished_draft_requires_handoff(self):
        old = Agent.objects.create(
            code="content-director", name="Old Content Director",
            mission="Review owned draft", active=False,
        )
        historical_story = NewsletterStory.objects.create(
            agent=old, story_type="company", title="Unfinished draft",
            slug="historical-unfinished-draft", summary="Previously drafted",
            body="Preserve historical text", fingerprint="historical-undelivered",
            status="draft",
        )
        item = self.submission("unpublished-legacy")
        receipt = self.run_queue("--limit", "1")
        item.refresh_from_db()
        historical_story.refresh_from_db()
        self.assertEqual(item.status, "queued")
        self.assertEqual(receipt["result"]["held"], 1)
        self.assertEqual(historical_story.agent_id, old.pk)
        self.assertEqual(NewsletterStory.objects.count(), 1)

    def test_missing_canonical_holds_owner_submission(self):
        self.bot.active = False
        self.bot.save(update_fields=["active"])
        item = self.submission("missing-owner")
        receipt = self.run_queue("--limit", "1")
        item.refresh_from_db()
        self.assertEqual(item.status, "queued")
        self.assertEqual(receipt["result"]["held"], 1)
        self.assertFalse(NewsletterStory.objects.exists())


class NewsletterDefaultDenyPublicationTests(TestCase):
    def setUp(self):
        agent = Agent.objects.create(
            code="publication-test-worker", name="Publisher", mission="Readiness", active=True
        )
        self.story = NewsletterStory.objects.create(
            agent=agent, story_type="world", title="Verified pending news",
            slug="verified-pending-news", summary="Source-based pending report",
            body="No publication until approved", fingerprint="publication-policy-check",
            status="scheduled", published_at=timezone.now() - timedelta(minutes=1),
        )

    def test_missing_schedule_never_publishes_due_story(self):
        call_command("publish_scheduled_news", stdout=io.StringIO())
        self.story.refresh_from_db()
        self.assertEqual(self.story.status, "scheduled")

    def test_approval_schedule_does_not_publish_unapproved_story(self):
        NewsletterSchedule.objects.create(active=True, publication_requires_approval=True)
        call_command("publish_scheduled_news", stdout=io.StringIO())
        self.story.refresh_from_db()
        self.assertEqual(self.story.status, "scheduled")

    def test_approved_story_can_publish_under_approval_schedule(self):
        NewsletterSchedule.objects.create(active=True, publication_requires_approval=True)
        self.story.status = "approved"
        self.story.save(update_fields=["status"])
        call_command("publish_scheduled_news", stdout=io.StringIO())
        self.story.refresh_from_db()
        self.assertEqual(self.story.status, "published")
