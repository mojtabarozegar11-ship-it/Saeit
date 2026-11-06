"""Regression coverage for the chat-to-cPanel authority and idempotency boundary."""
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .chat_runtime import MasterAgentChat
from .models import ApprovalRequest, AuditLog, ChatSession
from .operation_executor import execute_approved_chat_operation
from .operation_planner import approval_reason, plan_chat_operation


User = get_user_model()


class ChatOperationSecurityTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username="customer", password="safe-pass-123")
        self.staff = User.objects.create_user(username="staff", password="safe-pass-123", is_staff=True)
        self.owner = User.objects.create_superuser(username="superowner", password="safe-pass-123", email="owner@example.org")

    def _approval(self, user, status="approved"):
        operation = plan_chat_operation("deploy release now")
        return ApprovalRequest.objects.create(
            action_type="chat:" + operation.action,
            target_type="ChatOperation",
            target_id=operation.operation_id,
            reason=approval_reason(operation),
            risk="critical",
            status=status,
            requested_by=user,
        )

    def test_deploy_mention_is_not_a_command(self):
        for example in ("چطور انتشار سایت انجام می‌شود؟", "درباره انتشار سایت توضیح بده", "Why deploy release now?"):
            with self.subTest(text=example):
                self.assertIsNone(plan_chat_operation(example))
        self.assertEqual(plan_chat_operation("انتشار سایت را اجرا کن").action, "cpanel.deploy_release")
        self.assertIsNone(plan_chat_operation("انتشار سایت"))
        self.assertIsNone(plan_chat_operation("deploy release"))

    def test_normal_and_staff_chat_cannot_create_executable_approvals(self):
        for user in (self.customer, self.staff):
            with self.subTest(username=user.username):
                session = ChatSession.objects.create(user=user, title="access check")
                answer = MasterAgentChat().respond(session, "deploy release")
                self.assertIn("مجاز نیست", answer)
        self.assertFalse(ApprovalRequest.objects.filter(target_type="ChatOperation").exists())

    def test_self_approval_by_staff_is_forbidden(self):
        approval = self._approval(self.staff, status="pending")
        client = APIClient()
        client.force_authenticate(user=self.staff)
        response = client.post("/api/approvals/{}/decide/".format(approval.pk), {"approved": True}, format="json", secure=True)
        self.assertEqual(response.status_code, 403)
        approval.refresh_from_db()
        self.assertEqual(approval.status, "pending")

    def test_executor_rechecks_owner_even_for_preapproved_legacy_request(self):
        approval = self._approval(self.staff)
        with patch("core.operation_executor.subprocess.run") as runner:
            with self.assertRaises(PermissionError):
                execute_approved_chat_operation(approval)
        runner.assert_not_called()

    def test_same_approved_command_cannot_execute_twice(self):
        approval = self._approval(self.owner)
        with patch("core.operation_executor.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="ok", stderr="")) as runner:
            first = execute_approved_chat_operation(approval)
            second = execute_approved_chat_operation(approval)
        self.assertEqual(first["status"], "executed")
        self.assertEqual(second["status"], "already_executed")
        self.assertEqual(runner.call_count, 1)
        approval.refresh_from_db()
        self.assertEqual(approval.status, "executed")
        self.assertEqual(AuditLog.objects.filter(action="chat_operation_executed", target_id=str(approval.pk)).count(), 1)

    def test_failure_is_closed_to_automatic_replay(self):
        approval = self._approval(self.owner)
        with patch("core.operation_executor.subprocess.run", return_value=SimpleNamespace(returncode=1, stdout="", stderr="fail")) as runner:
            with self.assertRaises(RuntimeError):
                execute_approved_chat_operation(approval)
            retry = execute_approved_chat_operation(approval)
        self.assertEqual(retry["status"], "manual_reconciliation_required")
        self.assertEqual(runner.call_count, 1)
        approval.refresh_from_db()
        self.assertEqual(approval.status, "execution_failed")
