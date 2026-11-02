"""Only synthetic fixtures: no production cPanel, financial DB or GitHub token."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from scripts.zomorod_chatgpt_report_snapshot import build_snapshot, install

HEADER = "## گزارش ۰۵-۰۰۰۱ | 2026-11-01 16:04 UTC | ZM-CTRL-20261101-PR1779-CI41324363802"


def row(comment_id=123, body=HEADER + "\nگزارش ثبت شد؛ نه فروش قطعی.\n"):
    return {"id": comment_id, "body": body, "user": {"login": "mojtabarozegar11-ship-it"}}


class SnapshotSafetyTests(unittest.TestCase):
    def test_build_numbers_and_excludes_untrusted_author(self):
        d, p = build_snapshot([row(), row(author="other") if False else {
            "id": 199, "body": HEADER, "user": {"login": "other"}}])
        self.assertEqual(d["count"], 1)
        self.assertEqual(d["items"][0]["report_code"], "05-0001")
        self.assertIn(b"issuecomment-123", p)
        self.assertNotIn(b"issuecomment-199", p)

    def test_explicit_run_id_prefix_is_imported_without_rewriting_source(self):
        original = HEADER.replace(" | ZM-CTRL-", " | run_id ZM-CTRL-", 1) + "\nثبت امن نسخه گزارش فارسی.\n"
        result, payload = build_snapshot([row(900, original)])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["items"][0]["report_code"], "05-0001")
        self.assertEqual(result["items"][0]["body"], original)
        self.assertIn("run_id ZM-CTRL", payload.decode("utf-8"))

    def test_persian_execution_label_header_does_not_drop_real_report(self):
        header = "## گزارش ۰۵-۰۰۱۰ | 2026-11-02 01:12 UTC | شناسه اجرا: ZM-CTRL-20261102-PR1795-CI41371103477"
        original = header + "\nاقدام واقعی مستند برای سامانه کسب‌وکار.\n"
        result, _ = build_snapshot([row(6566708686, original)])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["items"][0]["report_code"], "05-0010")
        self.assertEqual(result["items"][0]["comment_id"], 6566708686)
        self.assertEqual(result["items"][0]["body"], original)

    def test_conflicting_same_number_and_overflow_fail(self):
        with self.assertRaisesRegex(ValueError, "CONFLICTING_REPORT"):
            build_snapshot([row(123), row(124)])
        rows = [row(i+1, HEADER.replace("۰۰۰۱", f"{i+1:04d}")) for i in range(101)]
        with self.assertRaisesRegex(ValueError, "REPORT_VIEW_CAP"):
            build_snapshot(rows)

    def test_create_append_reject_edit_or_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "private"
            parent.mkdir(mode=0o700)
            target = parent / "chatgpt_reports_snapshot.json"
            d1, p1 = build_snapshot([row(123)])
            install(d1, p1, target)
            self.assertEqual(target.stat().st_mode & 0o077, 0)
            self.assertEqual(install(d1, p1, target), "UNCHANGED")
            d2, p2 = build_snapshot([row(123), row(125, HEADER.replace("۰۰۰۱", "۰۰۰۲") + "\nsecond")])
            self.assertEqual(install(d2, p2, target), "UPDATED")
            before = target.read_bytes()
            altered, altered_payload = build_snapshot([row(123, HEADER + "\nchanged"), row(125, HEADER.replace("۰۰۰۱", "۰۰۰۲") + "\nsecond")])
            with self.assertRaisesRegex(ValueError, "NON_APPEND_ONLY"):
                install(altered, altered_payload, target)
            with self.assertRaisesRegex(ValueError, "NON_APPEND_ONLY"):
                install(d1, p1, target)
            self.assertEqual(target.read_bytes(), before)
            self.assertEqual(json.loads(before)["count"], 2)

    def test_never_follow_symlinks_or_public_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "private"
            parent.mkdir(mode=0o700)
            target = parent / "chatgpt_reports_snapshot.json"
            secret = Path(tmp) / "secret"
            secret.write_text("no access")
            target.symlink_to(secret)
            d, p = build_snapshot([row()])
            with self.assertRaisesRegex(ValueError, "INVALID_TARGET"):
                install(d, p, target)
            target.unlink()
            parent.chmod(0o755)
            with self.assertRaisesRegex(ValueError, "TARGET_DIRECTORY_MUST_BE_PRIVATE"):
                install(d, p, target)
            self.assertEqual(secret.read_text(), "no access")


if __name__ == "__main__":
    unittest.main()
