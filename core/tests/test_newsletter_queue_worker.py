"""Regression checks for the operational newsletter submission agent."""

import io
import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.models import Agent
from core.newsletter_engine import process_submission
from core.newsletter_models import NewsletterSchedule, NewsletterStory, NewsletterSubmission


class NewsletterQueueWorkerTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="newsletter_queue_owner")

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
        self.assertTrue(Agent.objects.filter(code="content-director", active=True).exists())

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
