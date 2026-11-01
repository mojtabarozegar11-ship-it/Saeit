"""Offline and adversarial tests for the opt-in GitHub issue report importer."""
import io
import json
import os
from datetime import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase

from enterprise_portal.github_chatgpt_reports import extract_receipt
from enterprise_portal.models import BusinessUnit, ChatGPTActionReport

HEADER = "## گزارش ۰۵-۰۰۰۱ | 2026-11-01 16:04 UTC | ZM-CTRL-20261101-PR1779-CI41324363802"
BODY = HEADER + "\n\n1. اصلاح کد و آزمون؛ بدون ادعای انتشار زنده.\n"
OWNER = "mojtabarozegar11-ship-it"


def comment(cid=101, body=BODY, author=OWNER):
    return {"id": cid, "body": body, "user": {"login": author}}


class ReportSourceParsingTests(TestCase):
    def test_normalizes_persian_digits_and_records_immutable_source(self):
        row = extract_receipt(comment())
        self.assertEqual(row["report_code"], "05-0001")
        self.assertEqual(row["cycle_code"], "05")
        self.assertEqual(row["run_reference"], "ZM-CTRL-20261101-PR1779-CI41324363802")
        self.assertEqual(row["occurred_at"].isoformat(), "2026-11-01T16:04:00+00:00")
        self.assertTrue(row["evidence_url"].endswith("#issuecomment-101"))

    def test_rejects_spoofs_malformed_and_oversize(self):
        self.assertIsNone(extract_receipt(comment(author="anyone-else")))
        self.assertIsNone(extract_receipt(comment(cid=-9)))
        self.assertIsNone(extract_receipt(comment(body="## Report 05-0001")))
        self.assertIsNone(extract_receipt(comment(body=BODY + "X"*8001)))
        self.assertIsNone(extract_receipt(comment(body=HEADER.replace("16:04", "90:00") + "\nReport")))


class ReportSyncCommandTests(TestCase):
    def setUp(self):
        self.unit = BusinessUnit.objects.create(code="zm-sync", name="مدیریت")
        self.owner = get_user_model().objects.create_superuser(
            username="sync-owner", email="owner@example.org", password="not-used",
        )

    @patch("enterprise_portal.management.commands.sync_chatgpt_action_reports.fetch_issue_comments")
    def test_preview_fetches_but_does_not_write(self, fetch):
        fetch.return_value = [comment(), comment(cid=102, body="unrelated status")]
        out = io.StringIO()
        call_command("sync_chatgpt_action_reports", stdout=out)
        result = json.loads(out.getvalue().split("ZM_REPORT_SYNC_JSON=")[1])
        self.assertEqual(result["eligible"], 1)
        self.assertEqual(result["created"], 0)
        self.assertEqual(result["mode"], "preview")
        self.assertEqual(ChatGPTActionReport.objects.count(), 0)

    @patch("enterprise_portal.management.commands.sync_chatgpt_action_reports.fetch_issue_comments")
    def test_commit_fails_closed_without_environment_gates(self, fetch):
        fetch.return_value = [comment()]
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesMessage(CommandError, "REPORT_IMPORT_RELEASE_GATE_BLOCKED"):
                call_command("sync_chatgpt_action_reports", "--commit",
                             "--unit-code=zm-sync", "--recorder-id=" + str(self.owner.pk))
        fetch.assert_not_called()
        self.assertFalse(ChatGPTActionReport.objects.exists())

    @patch("enterprise_portal.management.commands.sync_chatgpt_action_reports.fetch_issue_comments")
    def test_commit_imports_once_and_never_claims_automated_completion(self, fetch):
        fetch.return_value = [comment()]
        with patch.dict(os.environ, {
            "ZM_CHATGPT_REPORT_SYNC_ENABLED": "1",
            "ZM_CHATGPT_REPORT_DB_ATTESTED": "1",
        }):
            for iteration in range(2):
                out = io.StringIO()
                call_command("sync_chatgpt_action_reports", "--commit",
                             "--unit-code=zm-sync", "--recorder-id=" + str(self.owner.pk),
                             stdout=out)
                result = json.loads(out.getvalue().split("ZM_REPORT_SYNC_JSON=")[1])
                self.assertEqual(result["created"], 1 if iteration == 0 else 0)
        self.assertEqual(ChatGPTActionReport.objects.count(), 1)
        row = ChatGPTActionReport.objects.get()
        self.assertEqual(row.outcome, "partial")
        self.assertFalse(row.evidence_reviewed)
        self.assertIn("بدون ادعای انتشار", row.body)

    @patch("enterprise_portal.management.commands.sync_chatgpt_action_reports.fetch_issue_comments")
    def test_conflicting_sources_fail_closed_without_overwrite(self, fetch):
        fetch.return_value = [comment(101), comment(999)]
        with patch.dict(os.environ, {
            "ZM_CHATGPT_REPORT_SYNC_ENABLED": "1", "ZM_CHATGPT_REPORT_DB_ATTESTED": "1"
        }):
            with self.assertRaisesMessage(CommandError, "REPORT_NUMBER_SOURCE_CONFLICT"):
                call_command("sync_chatgpt_action_reports", "--commit",
                             "--unit-code=zm-sync", "--recorder-id=" + str(self.owner.pk))
        # Conflict in a later item must roll back the *entire* batch.
        self.assertFalse(ChatGPTActionReport.objects.exists())

    @patch("enterprise_portal.management.commands.sync_chatgpt_action_reports.fetch_issue_comments")
    def test_late_source_failure_never_leaves_partial_import(self, fetch):
        def broken_page_stream():
            yield comment(101)
            raise CommandError("GITHUB_REPORT_SOURCE_UNAVAILABLE")

        fetch.side_effect = lambda **kwargs: broken_page_stream()
        with patch.dict(os.environ, {
            "ZM_CHATGPT_REPORT_SYNC_ENABLED": "1",
            "ZM_CHATGPT_REPORT_DB_ATTESTED": "1",
        }):
            with self.assertRaisesMessage(CommandError, "GITHUB_REPORT_SOURCE_UNAVAILABLE"):
                call_command("sync_chatgpt_action_reports", "--commit",
                             "--unit-code=zm-sync", "--recorder-id=" + str(self.owner.pk))
        self.assertFalse(ChatGPTActionReport.objects.exists())

    @patch("enterprise_portal.management.commands.sync_chatgpt_action_reports.fetch_issue_comments")
    def test_existing_number_conflict_rolls_back_other_new_receipts(self, fetch):
        fetch.return_value = [comment(101)]
        gates = {
            "ZM_CHATGPT_REPORT_SYNC_ENABLED": "1",
            "ZM_CHATGPT_REPORT_DB_ATTESTED": "1",
        }
        with patch.dict(os.environ, gates):
            call_command("sync_chatgpt_action_reports", "--commit",
                         "--unit-code=zm-sync", "--recorder-id=" + str(self.owner.pk),
                         stdout=io.StringIO())
            new_body = BODY.replace("۰۵-۰۰۰۱", "۰۵-۰۰۰۲")
            fetch.return_value = [comment(102, body=new_body), comment(999)]
            with self.assertRaisesMessage(CommandError, "REPORT_NUMBER_SOURCE_CONFLICT"):
                call_command("sync_chatgpt_action_reports", "--commit",
                             "--unit-code=zm-sync", "--recorder-id=" + str(self.owner.pk))
        self.assertEqual(list(ChatGPTActionReport.objects.values_list("report_code", flat=True)),
                         ["05-0001"])

    def test_page_limits_cannot_be_bypassed(self):
        with self.assertRaisesMessage(CommandError, "PAGES_OUT_OF_RANGE"):
            call_command("sync_chatgpt_action_reports", "--pages=100")
