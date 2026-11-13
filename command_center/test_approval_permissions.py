"""Regression tests: recording sensitive approvals is not available to ordinary staff."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from core.models import ApprovalRequest


class SensitiveApprovalPermissionTests(TestCase):
    url = "/staff/command-center/api/integrated-ledger/"

    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            username="staff-no-approval", password="unit-test-only", is_staff=True
        )
        self.owner_admin = User.objects.create_superuser(
            username="owner-approval-admin", password="unit-test-only",
            email="no-reply@example.invalid"
        )
        self.approval = ApprovalRequest.objects.create(
            action_type="deploy", target_type="site", target_id="site-1",
            reason="Testing guard only; not an actual permission",
            requested_by=self.staff, status="pending"
        )

    def decide(self, actor, action, note=""):
        self.client.force_login(actor)
        return self.client.post(
            self.url,
            data=json.dumps({"kind": "approval_request", "id": self.approval.pk,
                             "action": action, "note": note}),
            content_type="application/json"
        )

    def test_staff_cannot_approve_or_reject_sensitive_request(self):
        for action in ("approved", "rejected", "explanation"):
            with self.subTest(action=action):
                response = self.decide(self.staff, action, "not authorized")
                self.assertEqual(response.status_code, 403)
                self.approval.refresh_from_db()
                self.assertEqual(self.approval.status, "pending")

    def test_admin_cannot_approve_without_case_specific_note(self):
        response = self.decide(self.owner_admin, "approved")
        self.assertEqual(response.status_code, 400)
        self.approval.refresh_from_db()
        self.assertEqual(self.approval.status, "pending")

    def test_existing_decision_cannot_be_overwritten(self):
        first = self.decide(self.owner_admin, "approved", "Owner case consent must be independently verified.")
        self.assertEqual(first.status_code, 200)
        self.approval.refresh_from_db()
        self.assertEqual(self.approval.status, "approved")
        second = self.decide(self.owner_admin, "rejected", "overwrite")
        self.assertEqual(second.status_code, 409)
        self.approval.refresh_from_db()
        self.assertEqual(self.approval.status, "approved")
