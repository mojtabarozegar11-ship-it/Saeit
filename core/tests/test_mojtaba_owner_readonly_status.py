"""Owner-facing status is factual SELECT-only; never a paid AI/action path."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.chat_runtime import MasterAgentChat
from core.models import Agent, AgentTask, ApprovalRequest, AuditLog, ChatMessage, ChatSession
from core.mojtaba_readonly_status import (
    is_status_command, owner_runtime_snapshot, render_owner_status,
)


User = get_user_model()


class MojtabaOwnerReadOnlyStatusTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(
            username="canonical_status_owner", email="owner-test@example.org",
            password="not-a-real-credential",
        )
        self.customer = User.objects.create_user(
            username="canonical_status_customer",
            password="not-a-real-credential",
        )
        self.staff = User.objects.create_user(
            username="canonical_status_staff",
            password="not-a-real-credential", is_staff=True,
        )
        self.agent = Agent.objects.create(
            code="status-review-factory-agent", name="Internal review role",
            mission="No migration or activation", active=True,
        )
        AgentTask.objects.create(
            agent=self.agent, action_type="product_research",
            capability_code="product_research", status="queued",
        )
        AgentTask.objects.create(
            agent=self.agent, action_type="product_research",
            capability_code="product_research", status="blocked",
        )

    def test_command_is_exact_and_not_implicit_authority(self):
        for text in (
            "bot status", "Bot Status!", "MOJTABA STATUS", "وضعیت ربات؟",
            "گزارش وضعیت ربات", "mojtaba.bot.ai status",
        ):
            with self.subTest(text=text):
                self.assertTrue(is_status_command(text))
        for text in (
            "status", "گزارش", "deploy release now", "Why bot status?",
            "please bot status on production", "موفقیت ربات؟", "",
        ):
            with self.subTest(text=text):
                self.assertFalse(is_status_command(text))

    @patch("core.mojtaba_readonly_status._isolated_prop_counts")
    @patch("openai.OpenAI")
    @patch("core.operation_executor.subprocess.run")
    def test_owner_gets_live_counts_without_model_or_execution(
        self, executor, model, isolated,
    ):
        isolated.return_value = {"invoices": 0, "payments": 0, "accounts": 0}
        session = ChatSession.objects.create(user=self.owner, title="Owner status")
        agents_before = Agent.objects.count()
        tasks_before = AgentTask.objects.count()
        approvals_before = ApprovalRequest.objects.count()
        audits_before = AuditLog.objects.count()
        answer = MasterAgentChat().respond(session, "وضعیت ربات")
        self.assertIn("گزارش فقط‌خواندنی ربات مرکزی", answer)
        self.assertIn("وظایف غیرنهایی:", answer)
        self.assertIn("فاکتور،", answer)
        self.assertIn("هیچ عملیات اجرایی انجام نشد", answer)
        response = ChatMessage.objects.get(session=session, role="assistant")
        self.assertEqual(response.metadata["execution"], "read_only_status")
        self.assertIs(response.metadata["llm_called"], False)
        self.assertEqual(ChatMessage.objects.filter(session=session).count(), 2)
        self.assertEqual(Agent.objects.count(), agents_before)
        self.assertEqual(AgentTask.objects.count(), tasks_before)
        self.assertEqual(ApprovalRequest.objects.count(), approvals_before)
        self.assertEqual(AuditLog.objects.count(), audits_before)
        isolated.assert_called_once()
        model.assert_not_called()
        executor.assert_not_called()

    @patch("core.mojtaba_readonly_status.owner_runtime_snapshot")
    @patch("openai.OpenAI")
    def test_customer_and_staff_never_obtain_private_metrics(self, model, snapshot):
        for user in (self.customer, self.staff):
            with self.subTest(user=user.username):
                session = ChatSession.objects.create(user=user)
                answer = MasterAgentChat().respond(session, "bot status")
                self.assertIn("مجاز نیست", answer)
                self.assertNotIn("هویت‌های ثبت‌شده", answer)
                msg = ChatMessage.objects.get(session=session, role="assistant")
                self.assertEqual(msg.metadata["execution"], "forbidden")
                self.assertIs(msg.metadata["llm_called"], False)
        snapshot.assert_not_called()
        model.assert_not_called()
        self.assertFalse(ApprovalRequest.objects.exists())

    @patch("core.mojtaba_readonly_status._isolated_prop_counts", return_value=None)
    def test_isolated_prop_failure_is_unknown_not_zero_income(self, isolated):
        data = owner_runtime_snapshot(self.owner)
        text = render_owner_status(data)
        self.assertIn("آمار بانک مستقل مج‌پراپ: نامشخص", text)
        self.assertNotIn("۰ پرداخت", text)
        self.assertFalse("وصول درآمد تأیید شد" in text)
        isolated.assert_called_once()

    def test_non_owner_direct_snapshot_fails_closed(self):
        for user in (self.customer, self.staff):
            with self.subTest(user=user.username):
                with self.assertRaises(PermissionError):
                    owner_runtime_snapshot(user)
