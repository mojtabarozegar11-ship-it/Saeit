"""Synthetic nonfinancial action-index safety tests. No production credentials."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.zm_chatgpt_action_index import SOURCE, rebuild, parse_block

REPO = "https://github.com/mojtabarozegar11-ship-it/Saeit"
SHA = "a" * 40


def receipt(code, aid, *, status="completed", url=f"{REPO}/commit/{SHA}"):
    block = {"version": 1, "report_code": code, "actions": [
        {"id": aid, "title_fa": "اصلاح فنی و کاربردی زنده",
         "status": status, "evidence_url": url,
         "impact_fa": "بهبود محدود با شاهد اولیه"}
    ]}
    return ("گزارش فارسی واقعی با شاهد معتبر؛ فروش و پرداخت احراز نشده‌اند.\n"
            "ZM_ACTIONS_V1_START\n"
            + json.dumps(block, ensure_ascii=False, separators=(",", ":"))
            + "\nZM_ACTIONS_V1_END")


class ActionIndexSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = self.root / "chatgpt_reports_archive.sqlite3"
        self.index = self.root / "chatgpt_actions_index.sqlite3"
        with sqlite3.connect(self.archive) as db:
            db.execute("CREATE TABLE reports (seq INTEGER PRIMARY KEY, report_code TEXT UNIQUE, "
                       "comment_id INTEGER UNIQUE,occurred_at TEXT,body TEXT,evidence_url TEXT)")
            db.execute("CREATE TABLE metadata (name TEXT PRIMARY KEY,value TEXT NOT NULL)")
            db.execute("INSERT INTO metadata VALUES ('source',?)", (SOURCE,))
            db.execute("PRAGMA user_version=1")
        self.archive.chmod(0o600)

    def add(self, seq, body, *, code=None):
        code = code or f"05-{seq:04d}"
        cid = 920000 + seq
        url = f"{REPO}/issues/1725#issuecomment-{cid}"
        with sqlite3.connect(self.archive) as db:
            db.execute("INSERT INTO reports(report_code,comment_id,occurred_at,body,evidence_url) "
                       "VALUES(?,?,?,?,?)",
                       (code, cid, "2026-11-02T08:00:00+00:00", body, url))
        self.archive.chmod(0o600)

    def test_append_index_and_keep_original_source_readonly(self):
        first = receipt("05-0001", "ZM05-0001-A01")
        self.add(1, first)
        before = self.archive.read_bytes()
        self.assertEqual(rebuild(self.archive, self.index), (1, 0, 1))
        self.assertEqual(self.archive.read_bytes(), before)
        self.assertEqual(self.index.stat().st_mode & 0o777, 0o600)
        with sqlite3.connect(self.index) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone(), (1,))
            self.assertEqual(db.execute("SELECT value FROM metadata WHERE name='verification'").fetchone(), ("not_checked",))
            self.assertEqual(db.execute("SELECT action_id,action_status FROM actions").fetchall(),
                             [("ZM05-0001-A01", "completed")])
        self.add(2, receipt("05-0002", "ZM05-0002-A01"))
        self.assertEqual(rebuild(self.archive, self.index), (2, 0, 2))
        self.assertEqual(rebuild(self.archive, self.index), (2, 0, 2))
        with sqlite3.connect(self.index) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM actions").fetchone(), (2,))

    def test_replay_is_rejected_and_not_counted_twice(self):
        self.add(1, receipt("05-0001", "ZM05-SHARED-A01"))
        self.add(2, receipt("05-0002", "ZM05-SHARED-A01"))
        self.assertEqual(rebuild(self.archive, self.index), (1, 1, 2))
        with sqlite3.connect(self.index) as db:
            self.assertEqual(db.execute("SELECT report_code,reason FROM rejected").fetchall(),
                             [("05-0002", "replayed_action_id")])

    def test_new_numbered_receipts_reject_foreign_or_date_based_action_ids(self):
        # Do not retroactively invalidate legacy reports 05-0001..05-0017.
        legacy = receipt("05-0017", "ZM05-20261102-A01")
        self.assertEqual(parse_block(legacy, "05-0017")[0], "valid")
        valid = receipt("05-0018", "ZM05-0018-A20")
        self.assertEqual(parse_block(valid, "05-0018")[0], "valid")
        for wrong in ("ZM05-20261102-A01", "ZM05-0017-A01",
                      "ZM05-0018-A00", "ZM05-0018-A21"):
            with self.subTest(action_id=wrong):
                self.assertEqual(
                    parse_block(receipt("05-0018", wrong), "05-0018"),
                    ("invalid_contract", []),
                )
        self.add(18, receipt("05-0018", "ZM05-20261102-A01"))
        self.assertEqual(rebuild(self.archive, self.index), (0, 1, 1))
        with sqlite3.connect(self.index) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM actions").fetchone(), (0,))

    def test_bad_url_and_duplicate_inside_same_report_fail_closed(self):
        invalid = receipt("05-0001", "ZM05-0001-A01", url="javascript:alert(1)")
        self.assertEqual(parse_block(invalid, "05-0001"), ("invalid_contract", []))
        self.add(1, invalid)
        self.assertEqual(rebuild(self.archive, self.index), (0, 1, 1))
        with sqlite3.connect(self.index) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM actions").fetchone(), (0,))

    def test_unhashable_status_quarantined_without_crashing_hourly_index(self):
        # JSON lists and objects are valid syntax, but invalid status types.
        # The prior set-membership check raised TypeError and stopped the cron.
        for bad in ('[]', '{"unexpected":"completed"}'):
            with self.subTest(status=bad):
                body = receipt("05-0020", "ZM05-0020-A01")
                body = body.replace('"status":"completed"', '"status":' + bad)
                self.assertEqual(parse_block(body, "05-0020"),
                                 ("invalid_contract", []))
        self.add(20, receipt("05-0020", "ZM05-0020-A01").replace(
            '"status":"completed"', '"status": []'))
        self.assertEqual(rebuild(self.archive, self.index), (0, 1, 1))
        with sqlite3.connect(self.index) as db:
            self.assertEqual(db.execute("SELECT reason FROM rejected").fetchone(),
                             ("invalid_contract",))

    def test_duplicate_json_keys_are_not_silently_accepted(self):
        body = receipt("05-0020", "ZM05-0020-A01")
        body = body.replace('"version":1', '"version":1,"version":1')
        self.assertEqual(parse_block(body, "05-0020"),
                         ("invalid_contract", []))
        nested = receipt("05-0020", "ZM05-0020-A01").replace(
            '"status":"completed"',
            '"status":"blocked","status":"completed"')
        self.assertEqual(parse_block(nested, "05-0020"),
                         ("invalid_contract", []))

    def test_extra_unclosed_receipt_marker_is_rejected(self):
        valid = receipt("05-0020", "ZM05-0020-A01")
        for injected in (valid + "\\nZM_ACTIONS_V1_START",
                         "ZM_ACTIONS_V1_END\\n" + valid):
            with self.subTest(marker=injected[:24]):
                self.assertEqual(parse_block(injected, "05-0020"),
                                 ("invalid_contract", []))

    def test_noncompleted_actions_cannot_carry_completed_evidence(self):
        # A blocked/partial/not-started item must not display a GitHub
        # evidence link as though the underlying work were complete.
        for state in ("partial", "blocked", "not_started"):
            with self.subTest(status=state):
                invalid = receipt("05-0021", "ZM05-0021-A01", status=state)
                self.assertEqual(parse_block(invalid, "05-0021"),
                                 ("invalid_contract", []))
                valid = receipt("05-0021", "ZM05-0021-A01",
                                status=state, url="")
                self.assertEqual(parse_block(valid, "05-0021")[0], "valid")
        self.add(21, receipt("05-0021", "ZM05-0021-A01", status="blocked"))
        self.assertEqual(rebuild(self.archive, self.index), (0, 1, 1))

    def test_persian_action_fields_required_in_structured_receipt(self):
        valid = receipt("05-0021", "ZM05-0021-A01")
        for altered in (
            valid.replace("اصلاح فنی و کاربردی زنده", "English only action"),
            valid.replace("بهبود محدود با شاهد اولیه", "English only impact"),
            valid.replace("بهبود محدود با شاهد اولیه", ""),
        ):
            with self.subTest(receipt=altered[-75:]):
                self.assertEqual(parse_block(altered, "05-0021"),
                                 ("invalid_contract", []))
        self.assertEqual(parse_block(valid, "05-0021")[0], "valid")

    def test_legacy_report_without_action_block_is_append_only(self):
        # Reports without structured actions were previously unprotected:
        # rewriting their prose did not change the indexed action rows.
        original = "گزارش مدیریتی قدیمی؛ فقط متن بدون رسید ساختاریافته"
        self.add(1, original)
        self.assertEqual(rebuild(self.archive, self.index), (0, 0, 1))
        with sqlite3.connect(self.index) as db:
            fingerprint = db.execute(
                "SELECT value FROM metadata WHERE name='archive_prefix_sha256'"
            ).fetchone()[0]
            self.assertEqual(len(fingerprint), 64)
        before = self.index.read_bytes()
        with sqlite3.connect(self.archive) as db:
            db.execute("UPDATE reports SET body=? WHERE report_code='05-0001'",
                       ("گزارش مدیریتی ویرایش شده؛ بدون رسید ساختاریافته",))
        self.archive.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_REPORT_HISTORY_CHANGED"):
            rebuild(self.archive, self.index)
        self.assertEqual(self.index.read_bytes(), before)

    def test_new_report_appends_without_changing_older_report_fingerprint(self):
        self.add(1, "گزارش مدیریتی قدیمی؛ بدون اقدام ساختاریافته")
        rebuild(self.archive, self.index)
        self.add(2, receipt("05-0002", "ZM05-0002-A01"))
        self.assertEqual(rebuild(self.archive, self.index), (1, 0, 2))
        self.assertEqual(rebuild(self.archive, self.index), (1, 0, 2))

    def test_mutated_source_history_fails_without_overwriting_old_index(self):
        self.add(1, receipt("05-0001", "ZM05-0001-A01"))
        rebuild(self.archive, self.index)
        before = self.index.read_bytes()
        with sqlite3.connect(self.archive) as db:
            db.execute("UPDATE reports SET body=? WHERE report_code='05-0001'",
                       (receipt("05-0001", "ZM05-0001-A02"),))
        self.archive.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_ACTION_HISTORY_CHANGED"):
            rebuild(self.archive, self.index)
        self.assertEqual(self.index.read_bytes(), before)

    def test_symlink_target_and_public_permissions_rejected(self):
        self.add(1, receipt("05-0001", "ZM05-0001-A01"))
        alias = self.root / "outside.sqlite3"
        alias.write_text("external")
        self.index.symlink_to(alias)
        with self.assertRaisesRegex(ValueError, "UNSAFE_ACTION_PATH"):
            rebuild(self.archive, self.index)
        self.assertEqual(alias.read_text(), "external")
        self.index.unlink()
        self.archive.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "UNSAFE_ACTION_FILE"):
            rebuild(self.archive, self.index)

    def test_financial_database_never_opened_or_changed(self):
        self.add(1, receipt("05-0001", "ZM05-0001-A01"))
        finance = self.root / "management.sqlite3"
        finance.write_bytes(b"do not touch private finance")
        original = finance.read_bytes()
        rebuild(self.archive, self.index)
        self.assertEqual(finance.read_bytes(), original)
        self.assertFalse((self.root / "management.sqlite3-journal").exists())


if __name__ == "__main__":
    unittest.main()
