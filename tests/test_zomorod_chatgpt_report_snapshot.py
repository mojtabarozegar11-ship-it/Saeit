"""Only synthetic fixtures: no production cPanel, financial DB or GitHub token."""
import json
import os
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
import tempfile
import unittest

from scripts.zomorod_chatgpt_report_snapshot import (build_snapshot, install, archive_sync, archive_since,
    extract_public_cycle_receipt, PUBLIC_CYCLES_SOURCE, PUBLIC_CYCLES_ARCHIVE_NAME)

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

    def test_only_exact_report_0010_may_backfill_between_immutable_receipts(self):
        first = row(900, HEADER.replace("۰۰۰۱", "۰۰۰۹") + "\nنوبت قبل تأیید شد.\n")
        later = row(911, HEADER.replace("۰۰۰۱", "۰۰۱۱") + "\nگزارش جدید بعد از ۰۰۱۰.\n")
        recovered_title = "## گزارش ۰۵-۰۰۱۰ | 2026-11-02 01:12 UTC | شناسه اجرا: ZM-CTRL-20261102-PR1795-CI41371103477"
        middle = row(6566708686, recovered_title + "\nفقط بازیابی گزارش واقعی جاافتاده.\n")
        with tempfile.TemporaryDirectory() as tmp:
            private = Path(tmp) / "private"
            private.mkdir(mode=0o700)
            target = private / "chatgpt_reports_snapshot.json"
            previous, payload = build_snapshot([first, later])
            self.assertEqual(previous["count"], 2)
            install(previous, payload, target)
            updated, packed = build_snapshot([first, middle, later])
            self.assertEqual(install(updated, packed, target), "UPDATED")
            self.assertEqual(
                [x["report_code"] for x in json.loads(target.read_text())["items"]],
                ["05-0009", "05-0010", "05-0011"]
            )
            # Mutation of an existing receipt can never masquerade as recovery.
            corrupted = dict(later, body=later["body"] + "changed")
            tampered, bad_payload = build_snapshot([first, middle, corrupted])
            with self.assertRaisesRegex(ValueError, "NON_APPEND_ONLY"):
                install(tampered, bad_payload, target)

        # The same slot under a different ID never passes the recovery exception.
        with tempfile.TemporaryDirectory() as tmp:
            private = Path(tmp) / "private"
            private.mkdir(mode=0o700)
            target = private / "chatgpt_reports_snapshot.json"
            old, old_payload = build_snapshot([first, later])
            install(old, old_payload, target)
            forged, forged_payload = build_snapshot([
                first, row(800000, middle["body"]), later
            ])
            with self.assertRaisesRegex(ValueError, "NON_APPEND_ONLY"):
                install(forged, forged_payload, target)

    def test_public_issue_1514_01_02_04_real_format_only_and_no_forgery(self):
        heading = "G-01 | گزارش ۰۴-۰۰۱۴ | ۲ نوامبر ۲۰۲۶، ۰۸:۲۳ تهران | شناسه G01-20261102T081757p0330"
        item = {"id": 12341, "body": heading + "\n۶ اصلاح واقعی آزمایشی بدون ادعای فروش.", "created_at": "2026-11-02T04:53:00Z", "user": {"login": "mojtabarozegar11-ship-it"}}
        receipt = extract_public_cycle_receipt(item)
        self.assertEqual(receipt["report_code"], "04-0014")
        self.assertIn("issues/1514#issuecomment-12341", receipt["evidence_url"])
        self.assertIsNone(extract_public_cycle_receipt(dict(item, user={"login": "forgery"})))
        self.assertIsNone(extract_public_cycle_receipt(dict(item, body=item["body"].replace("۰۴", "۰۳"))))
        self.assertIsNone(extract_public_cycle_receipt(dict(item, created_at="invalid")))
        self.assertIsNone(extract_public_cycle_receipt(dict(item, body="گزارش ۰۴-۰۰۱۴ و گزارش ۰۲-۰۰۱۴\n" + item["body"])))

    def test_public_cycle_archive_is_separate_from_financial_and_05_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "private"
            root.mkdir(mode=0o700)
            target = root / PUBLIC_CYCLES_ARCHIVE_NAME
            def item(number, cycle, cid):
                return {
                    "id": cid,
                    "body": f"**گزارش {cycle}-{number:04d} | ۲ نوامبر ۲۰۲۶، ساعت ۰۸:۰۰ تهران | شناسه واحد**\n"
                            "گزارش فارسی فقط برای آزمایش است؛ بدون رویداد واقعی.",
                    "created_at": "2026-11-02T04:30:00Z",
                    "user": {"login": "mojtabarozegar11-ship-it"},
                }
            cycle_items = [item(2, "۰۱", 10001), item(13, "۰۲", 10002), item(14, "۰۴", 10003)]
            kwargs = {"source": PUBLIC_CYCLES_SOURCE, "archive_name": PUBLIC_CYCLES_ARCHIVE_NAME,
                      "extractor": extract_public_cycle_receipt}
            total, added, _ = archive_sync(cycle_items, target, **kwargs)
            self.assertEqual((total, added), (3, 3))
            self.assertEqual(target.stat().st_mode & 0o077, 0)
            self.assertIsNotNone(archive_since(target, source=PUBLIC_CYCLES_SOURCE, archive_name=PUBLIC_CYCLES_ARCHIVE_NAME))
            with sqlite3.connect("file:" + str(target) + "?mode=ro", uri=True) as db:
                self.assertEqual([r[0] for r in db.execute("SELECT report_code FROM reports ORDER BY seq")],
                                 ["01-0002", "02-0013", "04-0014"])
            total, added, _ = archive_sync(cycle_items[-1:], target, **kwargs)
            self.assertEqual((total, added), (3, 0))
            forged = dict(cycle_items[-1], body=cycle_items[-1]["body"] + "altered")
            with self.assertRaisesRegex(ValueError, "IMMUTABLE_REPORT_ARCHIVE_CONFLICT"):
                archive_sync([forged], target, **kwargs)
            with self.assertRaisesRegex(ValueError, "INVALID_REPORT_ARCHIVE_METADATA"):
                archive_since(target, source="wrong", archive_name=PUBLIC_CYCLES_ARCHIVE_NAME)

    def test_nonfinancial_private_archive_grows_past_100_without_truncating_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "private"
            folder.mkdir(mode=0o700)
            archive = folder / "chatgpt_reports_archive.sqlite3"
            first = [row(i + 1, HEADER.replace("۰۰۰۱", f"{i + 1:04d}") + "\nگزارش فارسی آزمایشی.\n") for i in range(120)]
            total, added, window = archive_sync(first, archive)
            self.assertEqual((total, added, len(window)), (120, 120, 100))
            self.assertEqual(archive.stat().st_mode & 0o077, 0)
            self.assertEqual(window[0]["report_code"], "05-0001")
            self.assertEqual(window[-1]["report_code"], "05-0100")
            self.assertIsNotNone(archive_since(archive))
            total, added, window2 = archive_sync(first[-3:], archive)
            self.assertEqual((total, added, window2), (120, 0, window))
            extra = row(121, HEADER.replace("۰۰۰۱", "۰۱۲۱") + "\nگزارش فارسی جدید.\n")
            total, added, _ = archive_sync([first[-1], extra], archive)
            self.assertEqual((total, added), (121, 1))
            with sqlite3.connect("file:" + str(archive) + "?mode=ro", uri=True) as db:
                self.assertEqual(db.execute("PRAGMA quick_check").fetchone()[0], "ok")
                self.assertEqual(db.execute("SELECT COUNT(DISTINCT report_code) FROM reports").fetchone()[0], 121)
                self.assertEqual(db.execute("SELECT report_code FROM reports ORDER BY seq DESC LIMIT 1").fetchone()[0], "05-0121")
            forged = dict(extra, body=extra["body"] + "changed")
            with self.assertRaisesRegex(ValueError, "IMMUTABLE_REPORT_ARCHIVE_CONFLICT"):
                archive_sync([forged], archive)
            with self.assertRaisesRegex(ValueError, "HISTORICAL_INSERT_REJECTED"):
                archive_sync([row(105, HEADER.replace("۰۰۰۱", "۰۹۹۹") + "\nرسید دیرهنگام نامعتبر.\n")], archive)

    def test_archive_rejects_symlink_and_public_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "private"
            folder.mkdir(mode=0o700)
            archive = folder / "chatgpt_reports_archive.sqlite3"
            secret = Path(tmp) / "unrelated"
            secret.write_text("untouched")
            archive.symlink_to(secret)
            with self.assertRaisesRegex(ValueError, "INVALID_REPORT_ARCHIVE_TARGET"):
                archive_sync([row()], archive)
            archive.unlink()
            folder.chmod(0o755)
            with self.assertRaisesRegex(ValueError, "REPORT_ARCHIVE_DIRECTORY_MUST_BE_PRIVATE"):
                archive_sync([row()], archive)
            self.assertEqual(secret.read_text(), "untouched")

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


    def test_exact_legacy_management_receipts_recovered_with_immutable_fields(self):
        # All identifiers and title shapes match the four actual issue comments.
        real = [
            (6594492539, "0041", "ZM-APP-GUARDED-RECONCILIATION"),
            (6594657783, "0042", "ZM-RECOVERABLE-APP-PROMOTION"),
            (6594791099, "0043", "ZM-ISOLATED-REAL-DATA-ACCEPTANCE"),
            (6594862748, "0044", "ZM-RELEASE-DEPENDENCY-GATE"),
        ]
        def receipt(cid, heading):
            return {"id": cid, "body": heading + "\nاقدامات واقعی ثبت شده با شواهد و بدون تغییر داده مالی.\n",
                    "created_at": "2026-11-03T03:50:00Z",
                    "user": {"login": "mojtabarozegar11-ship-it"}}
        early = receipt(6593992560, "## گزارش 05-0040 | 2026-11-03 02:35 UTC | ZM-LIVE-APP-RECONCILIATION-20261103")
        late = receipt(6595877483, "## گزارش ۰۵-۰۰۴۵ | 2026-11-03 05:01 UTC | ZM-CTRL-20261103-0CB48E650B3D")
        recovered = [
            receipt(cid, f"## گزارش اجرایی ۰۵-{number} — ۳ نوامبر ۲۰۲۶ | {run}")
            for cid, number, run in real
        ]
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "private"
            parent.mkdir(mode=0o700)
            archive = parent / "chatgpt_reports_archive.sqlite3"
            snapshot_file = parent / "chatgpt_reports_snapshot.json"
            original, initial_payload = build_snapshot([early, late])
            self.assertEqual(install(original, initial_payload, snapshot_file), "UPDATED")
            self.assertEqual(archive_sync([early, late], archive)[:2], (2, 2))
            with sqlite3.connect(str(archive)) as db:
                old_fields = db.execute(
                    "SELECT report_code,comment_id,occurred_at,body,evidence_url FROM reports WHERE report_code='05-0045'"
                ).fetchone()
            all_comments = [early, *recovered, late]
            total, added, window = archive_sync(all_comments, archive)
            self.assertEqual((total, added), (6, 4))
            self.assertEqual([r["report_code"] for r in window],
                             [f"05-{n:04d}" for n in range(40, 46)])
            with sqlite3.connect(str(archive)) as db:
                new_fields = db.execute(
                    "SELECT report_code,comment_id,occurred_at,body,evidence_url FROM reports WHERE report_code='05-0045'"
                ).fetchone()
                self.assertEqual(old_fields, new_fields)
                self.assertEqual(db.execute("PRAGMA quick_check").fetchone()[0], "ok")
            updated, payload = build_snapshot(all_comments)
            self.assertEqual(install(updated, payload, snapshot_file), "UPDATED")
            self.assertEqual(install(updated, payload, snapshot_file), "UNCHANGED")
            self.assertEqual(json.loads(snapshot_file.read_text())["count"], 6)
            tampered = dict(recovered[1], body=recovered[1]["body"] + "changed")
            with self.assertRaisesRegex(ValueError, "IMMUTABLE_REPORT_ARCHIVE_CONFLICT"):
                archive_sync([tampered], archive)
            unauthorized = receipt(6594000000, "## گزارش 05-0046 | 2026-11-03 02:36 UTC | ZM-UNAPPROVED-HISTORY")
            with self.assertRaisesRegex(ValueError, "HISTORICAL_INSERT_REJECTED"):
                archive_sync([unauthorized], archive)

    def test_legacy_backfill_has_exact_owner_id_run_and_timestamp_gate(self):
        valid = {"id": 6594492539,
                 "body": "## گزارش اجرایی ۰۵-۰۰۴۱ — ۳ نوامبر ۲۰۲۶ | ZM-APP-GUARDED-RECONCILIATION\nمتن واقعی و مستند گزارش مدیریت.\n",
                 "created_at": "2026-11-03T03:02:00Z",
                 "user": {"login": "mojtabarozegar11-ship-it"}}
        self.assertEqual(build_snapshot([valid])[0]["items"][0]["report_code"], "05-0041")
        for altered in [
            dict(valid, id=123),
            dict(valid, user={"login": "attacker"}),
            dict(valid, created_at="invalid"),
            dict(valid, body=valid["body"].replace("RECONCILIATION", "FORGERY")),
            dict(valid, body=valid["body"].replace("۳ نوامبر", "۴ نوامبر")),
        ]:
            self.assertEqual(build_snapshot([altered])[0]["count"], 0)


if __name__ == "__main__":
    unittest.main()
