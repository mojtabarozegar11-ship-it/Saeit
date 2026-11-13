"""A staff dashboard read must not execute work or change audit history."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import CommandRequest, LedgerAuditEvent


class ManagementLedgerGetReadOnlyTests(TestCase):
    url = "/staff/command-center/api/integrated-ledger/"

    def setUp(self):
        self.viewer = get_user_model().objects.create_user(
            username="staff-readonly-test", password="test-password-only", is_staff=True
        )
        self.client.force_login(self.viewer)
        self.pending = CommandRequest.objects.create(
            domain="command", command="گزارش وضعیت سیستم",
            read_only=True, status="pending", requested_by=self.viewer
        )

    def test_get_does_not_complete_pending_command_or_create_audit_record(self):
        before = LedgerAuditEvent.objects.count()
        for _ in range(2):
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["commands"][0]["status"], "pending")
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, "pending")
        self.assertIsNone(self.pending.executed_at)
        self.assertEqual(self.pending.result, "")
        self.assertEqual(LedgerAuditEvent.objects.count(), before)
