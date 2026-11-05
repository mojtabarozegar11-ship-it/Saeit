import os
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

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

    def test_scheduled_cycle_never_spends_just_because_an_api_key_exists(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "configured-key", "MOJ_PAID_LLM_ENABLED": "1",
                                  "MOJ_LLM_DAILY_CALL_BUDGET": "10", "MOJ_LLM_MAX_COST_MINOR": "100"}), patch(
            "core.management.commands.knowledge_agent_generate.OpenAI"
        ) as factory:
            call_command("knowledge_agent_generate", stdout=StringIO())
        factory.assert_not_called()
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, "blocked")

    def test_cli_flag_without_scoped_owner_approval_still_blocks(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "configured-key", "MOJ_PAID_LLM_ENABLED": "1",
                                  "MOJ_LLM_DAILY_CALL_BUDGET": "10", "MOJ_LLM_MAX_COST_MINOR": "100"}), patch(
            "core.management.commands.knowledge_agent_generate.OpenAI"
        ) as factory:
            call_command("knowledge_agent_generate", "--approved-paid-execution", stdout=StringIO())
        factory.assert_not_called()
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, "blocked")

    def test_model_output_is_saved_as_a_draft_and_closes_the_task(self):
        owner = get_user_model().objects.create_user(username="knowledge-owner", is_staff=True)
        ApprovalRequest.objects.create(
            action_type="knowledge_paid_model_generation",
            target_type="KnowledgeAgentRun",
            target_id=str(self.run.pk),
            reason="Explicit authorization for exactly this queued section",
            risk="high", status="approved", requested_by=owner,
        )
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="پیش‌نویس آموزشی با محدودیت‌های روشن."))]
        )
        client = Mock()
        client.chat.completions.create.return_value = response
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "MOJ_PAID_LLM_ENABLED": "1",
                                  "MOJ_LLM_DAILY_CALL_BUDGET": "1", "MOJ_LLM_MAX_COST_MINOR": "100"}), patch(
            "core.management.commands.knowledge_agent_generate.OpenAI", return_value=client
        ):
            call_command("knowledge_agent_generate", "--approved-paid-execution", stdout=StringIO())

        self.run.refresh_from_db()
        self.task.refresh_from_db()
        self.book.refresh_from_db()
        self.assertEqual(self.run.status, "completed")
        self.assertEqual(self.task.status, "completed")
        self.assertEqual(self.book.status, "review")
        self.assertEqual(self.book.generated_sections, 1)
        self.assertIn("پیش‌نویس آموزشی", self.book.content)
        self.assertTrue(self.task.output_data["approval_required"])
