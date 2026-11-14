import os
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.approval import ApprovalService
from core.knowledge_agent_models import KnowledgeAgentPlan, KnowledgeAgentRun, KnowledgeBook
from core.models import Agent, AgentTask, ApprovalRequest


class KnowledgeAgentGenerateTests(TestCase):
    def setUp(self):
        self.plan = KnowledgeAgentPlan.objects.create(
            code="knowledge-content-director",
            title="Test content director",
            mission="Generate controlled drafts",
            goal="Create reviewable knowledge",
            active=True,
            require_owner_approval=True,
        )
        self.book = KnowledgeBook.objects.create(
            plan=self.plan,
            code="test-agriculture",
            title="کشاورزی",
            domain="کشاورزی",
            objective="تولید پیش‌نویس قابل بررسی",
            outline=["تعریف", "منابع"],
        )
        self.run = KnowledgeAgentRun.objects.create(
            plan=self.plan,
            book=self.book,
            objective="Generate one section",
            approval_required=True,
        )
        agent, _ = Agent.objects.get_or_create(
            code="knowledge-content-director",
            defaults={"name":"Knowledge Content Director","mission":"Controlled drafts","risk_level":"low","active":True},
        )
        self.task = AgentTask.objects.create(
            agent=agent,
            action_type="knowledge_content_generation",
            capability_code="research-write-review",
            input_data={"run_id": self.run.pk, "book_id": self.book.pk},
            status="queued",
        )

    def _approved_paid_grant(self, target_task=None, action="knowledge_content_generation"):
        owner = get_user_model().objects.create_superuser(
            username=f"knowledge-owner-{ApprovalRequest.objects.count()}",
            password="test-pass", email="owner@example.invalid",
        )
        task = target_task or self.task
        approval = ApprovalRequest.objects.create(
            action_type=action,
            target_type="AgentTask",
            target_id=str(task.pk),
            reason="Specific paid draft generation approved for this run",
            risk="high",
            status="approved",
            requested_by=owner,
        )
        return ApprovalService().issue_grant(
            approval.pk, owner.pk,
            {"action": "knowledge_content_generation", "run_id": self.run.pk, "paid_model": True},
        )

    def test_missing_model_key_blocks_and_closes_the_task(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            call_command("knowledge_agent_generate", stdout=StringIO())

        self.run.refresh_from_db()
        self.task.refresh_from_db()
        self.book.refresh_from_db()
        self.assertEqual(self.run.status, "blocked")
        self.assertEqual(self.task.status, "blocked")
        self.assertEqual(self.book.generated_sections, 0)
        self.assertTrue(self.task.output_data["approval_required"])

    def test_model_output_is_saved_as_a_draft_and_closes_the_task(self):
        grant = self._approved_paid_grant()
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="پیش‌نویس آموزشی با محدودیت‌های روشن."))]
        )
        client = Mock()
        client.chat.completions.create.return_value = response
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "core.management.commands.knowledge_agent_generate.OpenAI", return_value=client
        ):
            call_command("knowledge_agent_generate", approval_grant_id=grant.pk, stdout=StringIO())

        self.run.refresh_from_db()
        self.task.refresh_from_db()
        self.book.refresh_from_db()
        self.assertEqual(self.run.status, "completed")
        self.assertEqual(self.task.status, "completed")
        self.assertEqual(self.book.status, "review")
        self.assertEqual(self.book.generated_sections, 1)
        self.assertIn("پیش‌نویس آموزشی", self.book.content)
        self.assertTrue(self.task.output_data["approval_required"])
        grant.refresh_from_db()
        self.assertIsNotNone(grant.used_at)

    def test_api_key_never_authorizes_cost_without_scoped_owner_grant(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "configured-key"}), patch(
            "core.management.commands.knowledge_agent_generate.OpenAI"
        ) as openai:
            call_command("knowledge_agent_generate", stdout=StringIO())

        openai.assert_not_called()
        self.run.refresh_from_db()
        self.task.refresh_from_db()
        self.assertEqual(self.run.status, "queued")
        self.assertEqual(self.task.status, "blocked")
        self.assertTrue(self.task.output_data["approval_required"])

    def test_approval_for_different_task_does_not_authorize_paid_call(self):
        unrelated_task = AgentTask.objects.create(
            agent=self.task.agent,
            action_type="knowledge_content_generation",
            input_data={"run_id": 99999},
            status="queued",
        )
        # The stricter grant issuer now refuses a mismatched run before a
        # reusable authorization token can even be created.
        with self.assertRaises(ValueError):
            self._approved_paid_grant(target_task=unrelated_task)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "configured-key"}), patch(
            "core.management.commands.knowledge_agent_generate.OpenAI"
        ) as openai:
            call_command("knowledge_agent_generate", stdout=StringIO())

        openai.assert_not_called()
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, "queued")

    def test_completed_run_cannot_incur_second_charge(self):
        grant = self._approved_paid_grant()
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="یک بخش مستند."))]
        )
        client = Mock()
        client.chat.completions.create.return_value = response
        with patch.dict(os.environ, {"OPENAI_API_KEY": "configured-key"}), patch(
            "core.management.commands.knowledge_agent_generate.OpenAI", return_value=client
        ):
            call_command("knowledge_agent_generate", approval_grant_id=grant.pk, stdout=StringIO())
            call_command("knowledge_agent_generate", approval_grant_id=grant.pk, stdout=StringIO())

        self.assertEqual(client.chat.completions.create.call_count, 1)
