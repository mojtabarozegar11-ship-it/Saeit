"""Site-local content agent regression tests; never perform external AI requests."""
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from core.knowledge_agent_models import (
    KnowledgeAgentPlan, KnowledgeBook, KnowledgeAgentRun,
)


class KnowledgeAgentSafeQueueTests(TestCase):
    def setUp(self):
        self.plan = KnowledgeAgentPlan.objects.create(
            code="safe-queue-test", title="Safe queue", mission="Test",
            goal="Generate drafts only",
        )
        self.book = KnowledgeBook.objects.create(
            plan=self.plan, code="safe-queue-book", title="آموزش کشاورزی",
            domain="کشاورزی", objective="پژوهش آموزشی", content="متن قبلی",
        )
        self.run = KnowledgeAgentRun.objects.create(
            plan=self.plan, book=self.book, status="queued", objective="Test a draft",
        )

    def test_dry_run_does_not_claim_or_modify_content(self):
        output = StringIO()
        call_command("knowledge_agent_generate", dry_run=True, stdout=output)
        self.run.refresh_from_db()
        self.book.refresh_from_db()
        self.assertEqual(self.run.status, "queued")
        self.assertEqual(self.book.content, "متن قبلی")
        self.assertIn("dry-run queued=1", output.getvalue())

    def test_missing_key_blocks_one_run_only_and_does_not_retry(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            call_command("knowledge_agent_generate", stdout=StringIO())
            self.run.refresh_from_db()
            self.assertEqual(self.run.status, "blocked")
            output = StringIO()
            call_command("knowledge_agent_generate", stdout=output)
        self.assertIn("no unclaimed queued run", output.getvalue())
        self.book.refresh_from_db()
        self.assertEqual(self.book.generated_sections, 0)
        self.assertEqual(self.book.content, "متن قبلی")

    def test_success_creates_one_review_draft_and_cannot_repeat_run(self):
        reply = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="یک بخش علمی آزمایشی"))]
        )
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"}):
            with patch("openai.OpenAI") as mock_openai:
                mock_openai.return_value.chat.completions.create.return_value = reply
                call_command("knowledge_agent_generate", stdout=StringIO())
                call_command("knowledge_agent_generate", stdout=StringIO())
                self.assertEqual(mock_openai.return_value.chat.completions.create.call_count, 1)
        self.run.refresh_from_db()
        self.book.refresh_from_db()
        self.assertEqual(self.run.status, "completed")
        self.assertEqual(self.book.status, "review")
        self.assertEqual(self.book.generated_sections, 1)
        self.assertIn("متن قبلی", self.book.content)
        self.assertIn("یک بخش علمی آزمایشی", self.book.content)

    def test_bookless_run_is_blocked_without_external_generation(self):
        self.run.book = None
        self.run.save(update_fields=["book"])
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"}):
            with patch("openai.OpenAI") as mock_openai:
                call_command("knowledge_agent_generate", stdout=StringIO())
                mock_openai.assert_not_called()
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, "blocked")

    def test_existing_running_run_is_not_claimed_again(self):
        self.run.status = "running"
        self.run.save(update_fields=["status"])
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            output = StringIO()
            call_command("knowledge_agent_generate", stdout=output)
        self.assertIn("no unclaimed queued run", output.getvalue())
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, "running")
