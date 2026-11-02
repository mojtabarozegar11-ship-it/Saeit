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

    def test_bad_url_and_duplicate_inside_same_report_fail_closed(self):
        invalid = receipt("05-0001", "ZM05-0001-A01", url="javascript:alert(1)")
        self.assertEqual(parse_block(invalid, "05-0001"), ("invalid_contract", []))
        self.add(1, invalid)
        self.assertEqual(rebuild(self.archive, self.index), (0, 1, 1))
        with sqlite3.connect(self.index) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM actions").fetchone(), (0,))

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
