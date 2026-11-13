"""Regression tests: recording sensitive approvals is not available to ordinary staff."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from core.models import ApprovalRequest
from .models import ApprovalDecision


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

    def test_legacy_approval_staff_cannot_impersonate_the_owner(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            self.url,
            data=json.dumps({"kind": "approval", "status": "approved",
                             "approver": self.owner_admin.get_username(),
                             "evidence": "forged example only"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(ApprovalDecision.objects.count(), 0)

    def test_legacy_approval_requires_actual_actor_and_evidence(self):
        self.client.force_login(self.owner_admin)
        for approver, evidence in (("someone-else", "claim"), (self.owner_admin.get_username(), "")):
            with self.subTest(approver=approver, evidence=evidence):
                response = self.client.post(
                    self.url,
                    data=json.dumps({"kind": "approval", "status": "approved",
                                     "approver": approver, "evidence": evidence}),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)
        self.assertFalse(ApprovalDecision.objects.exists())

    def test_legacy_decision_is_attributed_to_signed_in_admin(self):
        self.client.force_login(self.owner_admin)
        response = self.client.post(
            self.url,
            data=json.dumps({"kind": "approval", "status": "rejected",
                             "approver": self.owner_admin.get_username(),
                             "evidence": "fixture only: owner consent not asserted"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        entry = ApprovalDecision.objects.get()
        self.assertEqual(entry.created_by_id, self.owner_admin.pk)
        self.assertEqual(entry.approver, self.owner_admin.get_username())
