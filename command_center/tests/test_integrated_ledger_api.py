"""Regressions for the owner-only, evidence-backed integrated management desk."""
import json
from io import StringIO
from html.parser import HTMLParser
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounting.models import Account, JournalEntry, JournalLine
from core.models import ApprovalRequest
from command_center.models import ApprovalDecision, CommandRequest, LedgerAuditEvent, WorkItem, CycleIssue


class _TabNestingParser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.tabs = []
        self.nested = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        label = attributes.get("id", "")
        if tag == "section" and label.startswith("tab-"):
            self.tabs.append(label)
            if any(name.startswith("section#tab-") for name in self.stack):
                self.nested.append(label)
        if tag not in self.VOID:
            self.stack.append(tag + ("#" + label if label else ""))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index].split("#", 1)[0] == tag:
                self.stack = self.stack[:index]
                return


class IntegratedLedgerSafetyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_superuser(username="desk_owner", password="test-only")
        cls.staff = User.objects.create_user(username="desk_staff", password="test-only", is_staff=True)
        cls.other = User.objects.create_user(username="desk_other", password="test-only", is_staff=True)

    def api(self, payload):
        return self.client.post(
            reverse("command_center_integrated_ledger_api"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_read_only_get_never_executes_queued_commands(self):
        command = CommandRequest.objects.create(
            domain="command", command="پایش وضعیت سامانه", read_only=True,
            status="pending", requested_by=self.staff,
        )
        self.client.force_login(self.staff)
        for _ in range(2):
            response = self.client.get(reverse("command_center_integrated_ledger_api"))
            self.assertEqual(response.status_code, 200)
        command.refresh_from_db()
        self.assertEqual(command.status, "pending")
        self.assertIsNone(command.executed_at)
        self.assertFalse(LedgerAuditEvent.objects.filter(entity="command").exists())

    def test_only_exact_bounded_monitor_is_executed(self):
        self.client.force_login(self.staff)
        safe = self.api({"kind": "command", "command": "monitor:systems"})
        self.assertEqual(safe.status_code, 201)
        self.assertEqual(safe.json()["command"]["status"], "executed")
        unsafe = self.api({"kind": "command", "command": "پایش وضعیت سامانه و حذف سوابق"})
        self.assertEqual(unsafe.status_code, 201)
        self.assertEqual(unsafe.json()["command"]["status"], "pending")
        self.assertFalse(unsafe.json()["command"]["read_only"])

    def test_staff_cannot_approve_another_owners_request(self):
        approval = ApprovalRequest.objects.create(
            action_type="system_change", target_type="agent", target_id="7",
            reason="Needs owner", requested_by=self.owner, status="pending",
        )
        self.client.force_login(self.staff)
        response = self.api({"kind": "approval_request", "id": approval.pk, "action": "approved"})
        self.assertEqual(response.status_code, 403)
        approval.refresh_from_db()
        self.assertEqual(approval.status, "pending")

        self.client.force_login(self.owner)
        response = self.api({"kind": "approval_request", "id": approval.pk,
                             "action": "approved", "note": "Explicit owner review"})
        self.assertEqual(response.status_code, 200)
        approval.refresh_from_db()
        self.assertEqual(approval.status, "approved")
        self.assertEqual(self.api({"kind": "approval_request", "id": approval.pk,
                                   "action": "rejected"}).status_code, 409)

    def test_pending_approvals_are_visible_and_ledger_integrity_is_real(self):
        approval = ApprovalRequest.objects.create(
            action_type="system_change", target_type="agent", target_id="8",
            reason="Pending", requested_by=self.owner, status="pending",
        )
        cash = Account.objects.create(code="101", name="Cash", kind=Account.Kind.ASSET)
        revenue = Account.objects.create(code="401", name="Sales", kind=Account.Kind.REVENUE)
        entry = JournalEntry.objects.create(reference="J1", occurred_on=date(2026, 11, 7),
                                            memo="Verified ledger data", status=JournalEntry.Status.POSTED)
        JournalLine.objects.create(entry=entry, account=cash, debit=Decimal("25"))
        JournalLine.objects.create(entry=entry, account=revenue, credit=Decimal("25"))
        self.client.force_login(self.owner)
        response = self.client.get(reverse("command_center_integrated_ledger_api"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(approval.pk, [item["id"] for item in response.json()["pending_approvals"]])
        self.assertTrue(response.json()["finance_integrity"]["balanced_posted_entries"])
        JournalLine.objects.filter(entry=entry, account=revenue).update(credit=Decimal("24"))
        response = self.client.get(reverse("command_center_integrated_ledger_api"))
        self.assertFalse(response.json()["finance_integrity"]["balanced_posted_entries"])

    def test_lightweight_approval_poll_exposes_only_owners_queue(self):
        approval = ApprovalRequest.objects.create(
            action_type="system_change", target_type="agent", target_id="88",
            reason="Owner only", requested_by=self.owner, status="pending",
        )
        url = reverse("command_center_integrated_ledger_api") + "?view=approvals"
        self.client.force_login(self.staff)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response.json()["pending_count"], 0)
        self.assertNotIn("finance", response.json())
        self.assertNotIn("reports", response.json())
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.json()["pending_count"], 1)
        self.assertEqual(response.json()["pending_approvals"][0]["id"], approval.pk)

    def test_sensitive_decision_record_cannot_impersonate_approver(self):
        payload = {"kind": "approval", "approval_kind": "cost", "status": "approved",
                   "approver": "a different person", "evidence": "Owner reviewed"}
        self.client.force_login(self.staff)
        self.assertEqual(self.api(payload).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.api(payload).status_code, 201)
        row = ApprovalDecision.objects.get()
        self.assertEqual(row.approver, self.owner.get_username())

    def test_not_logged_in_cannot_read_ledger(self):
        self.assertNotEqual(self.client.get(reverse("command_center_integrated_ledger_api")).status_code, 200)

    def test_all_management_tabs_are_siblings(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("command_center_integrated_dashboard"))
        self.assertEqual(response.status_code, 200)
        parser = _TabNestingParser()
        parser.feed(response.content.decode())
        self.assertEqual(len(parser.tabs), 7)
        self.assertEqual(parser.nested, [])

    def test_issue_requires_verification_before_final_resolution(self):
        issue = CycleIssue.objects.create(
            cycle="C01", project_key="management", title="Provisional issue",
            owner="management", observed_on=date(2026, 11, 7),
            next_action="Verify the source", created_by=self.staff,
        )
        self.client.force_login(self.staff)
        payload = {"kind": "issue_update", "id": issue.pk, "action": "resolve", "evidence": "Claimed fix"}
        self.assertEqual(self.api(payload).status_code, 409)
        self.assertEqual(self.api({**payload, "action": "verify", "evidence": "Inspection receipt"}).status_code, 200)
        self.assertEqual(self.api({**payload, "action": "verify", "evidence": "Inspection receipt"}).status_code, 409)
        self.assertEqual(self.api(payload).status_code, 200)
        self.assertEqual(self.api(payload).status_code, 409)
        issue.refresh_from_db()
        self.assertEqual(issue.status, "resolved")
        self.assertEqual(issue.resolution_evidence, "Claimed fix")

    def test_headless_watchdog_is_read_only_and_never_invents_completion(self):
        WorkItem.objects.create(title="Claimed done without receipt", status="done", created_by=self.staff)
        output = StringIO()
        call_command("audit_management_cycles", stdout=output)
        data = json.loads(output.getvalue())
        self.assertEqual(data["mode"], "read_only")
        self.assertIsNone(data["cycle_health"]["verified_completions"])
        self.assertTrue(all(row["cycles_with_reports"] == 0 for row in data["cycle_health"]["coverage"]))
        self.assertEqual(data["cycle_health"]["done_without_evidence"], 1)
        self.assertIn("COMPLETION_WITHOUT_EVIDENCE", data["alerts"])
        self.assertEqual(CommandRequest.objects.count(), 0)
        self.assertEqual(LedgerAuditEvent.objects.count(), 0)
