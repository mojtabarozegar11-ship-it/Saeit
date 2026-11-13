"""Issue update actions must be explicit and cannot reopen resolved issues."""
import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import CycleIssue, LedgerAuditEvent


class IssueUpdateTransitionTests(TestCase):
    url = "/staff/command-center/api/integrated-ledger/"

    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="issue-editor-fixture", password="test-password-only", is_staff=True
        )
        self.client.force_login(self.staff)
        self.issue = CycleIssue.objects.create(
            domain="command", cycle="C05", project_key="management",
            title="test blocker", owner="test fixture", observed_on=date(2026, 11, 13),
            certainty="unverified", next_action="collect evidence",
            created_by=self.staff
        )

    def update_issue(self, action, evidence="example reference for test only"):
        return self.client.post(
            self.url,
            data=json.dumps({"kind": "issue_update", "id": self.issue.pk,
                             "action": action, "evidence": evidence}),
            content_type="application/json"
        )

    def test_unknown_action_cannot_mark_unverified_issue_verified(self):
        count = LedgerAuditEvent.objects.count()
        for action in ("", "review", "approve", "verified"):
            with self.subTest(action=action):
                self.assertEqual(self.update_issue(action).status_code, 400)
                self.issue.refresh_from_db()
                self.assertEqual(self.issue.status, "open")
                self.assertEqual(self.issue.certainty, "unverified")
        self.assertEqual(LedgerAuditEvent.objects.count(), count)

    def test_resolved_issue_cannot_be_changed_or_resolved_twice(self):
        self.assertEqual(self.update_issue("resolve").status_code, 200)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, "resolved")
        original_evidence = self.issue.resolution_evidence
        for action in ("verify", "resolve"):
            self.assertEqual(self.update_issue(action, "altered").status_code, 409)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.resolution_evidence, original_evidence)

    def test_explicit_verification_requires_nonempty_evidence(self):
        self.assertEqual(self.update_issue("verify", "").status_code, 400)
        self.assertEqual(self.update_issue("verify", "test-only trace").status_code, 200)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.certainty, "verified")
        self.assertEqual(self.issue.status, "open")
