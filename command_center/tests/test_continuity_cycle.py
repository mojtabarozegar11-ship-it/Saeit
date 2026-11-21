"""Safety and idempotency checks for the unattended internal worker."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounting.models import JournalEntry, JournalLine, Account
from command_center.continuity import AUTO_SOURCE, run_continuity_cycle
from command_center.models import CommandRequest, CycleReport, LedgerAuditEvent, WorkItem
from core.models import ApprovalRequest


class ContinuityCycleTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(
            username="continuity_service", password="test-only", is_staff=True,
        )

    def _run(self):
        return run_continuity_cycle(actor=self.actor, apply=True)

    def test_read_only_has_no_database_side_effects(self):
        result = run_continuity_cycle()
        self.assertEqual(result["open_conditions"], 5)
        self.assertEqual(result["mode"], "read_only")
        self.assertFalse(WorkItem.objects.exists())
        self.assertFalse(LedgerAuditEvent.objects.exists())

    def test_worker_is_idempotent_and_does_not_touch_money(self):
        self.assertEqual(self._run()["work_items_created"], 5)
        self.assertEqual(self._run()["work_items_created"], 0)
        self.assertEqual(WorkItem.objects.filter(source_type=AUTO_SOURCE).count(), 5)
        self.assertEqual(LedgerAuditEvent.objects.count(), 5)
        self.assertEqual(JournalEntry.objects.count(), 0)

    def test_recent_evidence_resolves_only_matching_stream(self):
        self._run()
        CycleReport.objects.create(
            cycle="C01", project_key="books", project_name="کتاب",
            action="ویرایش مستند فصل", action_key="unique-books-1",
            result="فصل اصلاح شد", measure="۱ فصل", evidence="file:chapter-1",
            next_action="بازبینی", owner="editor", action_date=timezone.localdate(),
            created_by=self.actor,
        )
        result = self._run()
        self.assertEqual(result["work_items_resolved"], 1)
        ticket = WorkItem.objects.get(source_type=AUTO_SOURCE, source_id="stream:A")
        self.assertEqual(ticket.status, "done")
        self.assertTrue(ticket.resolution_reference)
        self.assertEqual(WorkItem.objects.filter(source_type=AUTO_SOURCE, status="open").count(), 4)

    def test_overdue_task_escalates_once_and_recovers(self):
        original = WorkItem.objects.create(
            title="قدیمی", created_by=self.actor,
            status="in_progress", due_at=timezone.now() - timedelta(hours=2),
        )
        self.assertEqual(self._run()["work_items_created"], 6)
        self.assertEqual(self._run()["work_items_created"], 0)
        original.status = "done"
        original.save(update_fields=["status"])
        self._run()
        escalation = WorkItem.objects.get(source_type=AUTO_SOURCE, source_id=f"overdue:{original.pk}")
        self.assertEqual(escalation.status, "done")
        self.assertEqual(original.status, "done")

    def test_unbalanced_posted_journal_is_not_modified(self):
        account = Account.objects.create(code="1010", name="cash", kind=Account.Kind.ASSET)
        entry = JournalEntry.objects.create(
            reference="CHECK-01", occurred_on=timezone.localdate(), memo="read-only check",
            status=JournalEntry.Status.POSTED,
        )
        JournalLine.objects.create(entry=entry, account=account, debit="10.00", credit="0.00")
        result = self._run()
        self.assertEqual(result["unbalanced_posted_journals_checked"], 1)
        self.assertEqual(WorkItem.objects.filter(source_id=f"journal:{entry.pk}").count(), 1)
        entry.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.Status.POSTED)
        self.assertEqual(entry.lines.count(), 1)

    def test_apply_requires_active_staff(self):
        regular = get_user_model().objects.create_user(username="viewer", password="test-only")
        with self.assertRaises(ValueError):
            run_continuity_cycle(actor=regular, apply=True)
        with self.assertRaisesMessage(Exception, "--actor"):
            call_command("continuity_cycle", apply=True)

    def test_staff_only_status_endpoint_never_writes(self):
        self.client.force_login(self.actor)
        response = self.client.get("/staff/command-center/api/continuity/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["open_conditions"], 5)
        self.assertFalse(WorkItem.objects.exists())

    def test_integrated_ledger_get_never_executes_command(self):
        queued = CommandRequest.objects.create(
            domain="command", command="گزارش", status="pending", read_only=True,
            requested_by=self.actor,
        )
        self.client.force_login(self.actor)
        response = self.client.get("/staff/command-center/api/integrated-ledger/")
        self.assertEqual(response.status_code, 200)
        queued.refresh_from_db()
        self.assertEqual(queued.status, "pending")
        self.assertFalse(LedgerAuditEvent.objects.exists())

        self._run()
        queued.refresh_from_db()
        self.assertEqual(queued.status, "executed")
        self.assertIn("خواندن واقعی", queued.result)

    def test_unknown_and_sensitive_queue_commands_stay_pending(self):
        unsafe = CommandRequest.objects.create(
            domain="command", command="ارسال ایمیل", status="pending", read_only=True,
            requested_by=self.actor,
        )
        unknown = CommandRequest.objects.create(
            domain="command", command="خودکار اجرا کن", status="pending", read_only=True,
            requested_by=self.actor,
        )
        self._run()
        unsafe.refresh_from_db()
        unknown.refresh_from_db()
        self.assertEqual(unsafe.status, "pending")
        self.assertEqual(unknown.status, "pending")

    def test_staff_cannot_approve_sensitive_operations(self):
        pending = ApprovalRequest.objects.create(
            action_type="deployment", target_type="site", target_id="test",
            reason="approval regression", status="pending", requested_by=self.actor,
        )
        self.client.force_login(self.actor)
        response = self.client.post(
            "/staff/command-center/api/integrated-ledger/",
            data='{"kind":"approval_request","id":%s,"action":"approved"}' % pending.pk,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        pending.refresh_from_db()
        self.assertEqual(pending.status, "pending")
