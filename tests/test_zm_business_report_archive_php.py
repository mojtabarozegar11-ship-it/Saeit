"""Synthetic CLI checks for the private report archive viewer; no live credentials."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "content/zomorod-business/chatgpt_reports.php"
SOURCE = "github:mojtabarozegar11-ship-it/Saeit:issue:1725"
PHP = shutil.which("php")
WRAPPER = r"""
function role(){return getenv('FAKE_ROLE') ?: 'admin';}
function esc($v){return htmlspecialchars((string)$v,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
function bail($message,$code=403){throw new RuntimeException('DENIED');}
$_GET=json_decode(getenv('FAKE_QUERY'),true);
require getenv('FAKE_VIEWER');
zmBusinessChatgptReports(getenv('FAKE_PRIVATE'));
"""


@unittest.skipUnless(PHP, "PHP CLI must be installed")
class PrivateReportArchivePhpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / "private"
        self.folder.mkdir(mode=0o700)
        self.archive = self.folder / "chatgpt_reports_archive.sqlite3"
        with sqlite3.connect(self.archive) as db:
            db.execute("CREATE TABLE reports (seq INTEGER PRIMARY KEY, report_code TEXT NOT NULL UNIQUE, comment_id INTEGER NOT NULL UNIQUE, occurred_at TEXT NOT NULL, body TEXT NOT NULL, evidence_url TEXT NOT NULL)")
            db.execute("CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("PRAGMA user_version=1")
            db.execute("INSERT INTO metadata VALUES ('source',?)", (SOURCE,))
            db.execute("INSERT INTO metadata VALUES ('last_checked_at','2026-11-02T00:00:00+00:00')")
            for number in range(1, 28):
                cid = 10000 + number
                db.execute(
                    "INSERT INTO reports(report_code,comment_id,occurred_at,body,evidence_url) VALUES (?,?,?,?,?)",
                    (
                        f"05-{number:04d}", cid, "2026-11-02T00:00:00+00:00",
                        "گزارش فارسی آزمایشی؛ <script>attack()</script> اجرا نشود.",
                        f"https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1725#issuecomment-{cid}",
                    ),
                )
        self.archive.chmod(0o600)

    def view(self, page="1", role="admin"):
        env = os.environ.copy()
        env.update({
            "FAKE_ROLE": role,
            "FAKE_QUERY": json.dumps({"page": "chatgpt_reports", "p": page}),
            "FAKE_VIEWER": str(VIEWER),
            "FAKE_PRIVATE": str(self.folder),
        })
        return subprocess.run([PHP, "-d", "display_errors=0", "-r", WRAPPER],
                              env=env, capture_output=True, text=True, timeout=12)

    def test_admin_paginated_persian_escape_and_five_cycles(self):
        first = self.view()
        self.assertEqual(first.returncode, 0, first.stderr[-500:])
        self.assertIn("تعداد گزارش‌های بایگانی‌شده: 27", first.stdout)
        self.assertIn("پایش پنج چرخهٔ ساعتی", first.stdout)
        self.assertIn("۲۰ اقدام / تحقق احرازنشده", first.stdout)
        self.assertIn("05-0027", first.stdout)
        self.assertNotIn("<script>attack()</script>", first.stdout)
        self.assertIn("&lt;script&gt;attack()&lt;/script&gt;", first.stdout)
        self.assertNotIn("<h3>05-0001</h3>", first.stdout)
        self.assertIn("صفحه قدیمی‌تر", first.stdout)
        second = self.view("2")
        self.assertEqual(second.returncode, 0, second.stderr[-500:])
        self.assertIn("<h3>05-0001</h3>", second.stdout)
        self.assertIn("صفحه جدیدتر", second.stdout)

    def test_role_and_corrupt_permissions_are_closed(self):
        self.assertNotEqual(self.view(role="viewer").returncode, 0)
        self.archive.chmod(0o644)
        response = self.view()
        self.assertEqual(response.returncode, 0)
        self.assertIn("اعتبارسنجی آرشیو ناموفق بود", response.stdout)
        self.archive.chmod(0o600)
        with sqlite3.connect(self.archive) as db:
            db.execute("UPDATE metadata SET value='wrong' WHERE name='source'")
        response = self.view()
        self.assertIn("اعتبارسنجی آرشیو ناموفق بود", response.stdout)

    def test_translation_bound_to_original_comment(self):
        pack = self.folder / "chatgpt_reports_fa.json"
        pack.write_text(json.dumps({
            "version": 1, "source": SOURCE, "kind": "persian_management_rendering",
            "items": {"05-0027": {"comment_id": 10027,
                                  "text_fa": "ترجمه فارسی آزمایشی و مستند گزارش شماره بیست‌وهفت."}}
        }, ensure_ascii=False), encoding="utf-8")
        pack.chmod(0o600)
        response = self.view()
        self.assertIn("ترجمه فارسی آزمایشی", response.stdout)
        changed = json.loads(pack.read_text(encoding="utf-8"))
        changed["items"]["05-0027"]["comment_id"] = 99999
        pack.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
        response = self.view()
        self.assertIn("اعتبارسنجی آرشیو ناموفق بود", response.stdout)


if __name__ == "__main__":
    unittest.main()
