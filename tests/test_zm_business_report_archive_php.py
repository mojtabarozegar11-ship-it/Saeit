"""Synthetic CLI checks for the private report archive viewer; no live credentials."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

from scripts.zm_chatgpt_action_index import rebuild

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

    def view(self, page="1", role="admin", cycle="05"):
        env = os.environ.copy()
        env.update({
            "FAKE_ROLE": role,
            "FAKE_QUERY": json.dumps({"page": "chatgpt_reports", "p": page, "cycle": cycle}),
            "FAKE_VIEWER": str(VIEWER),
            "FAKE_PRIVATE": str(self.folder),
        })
        return subprocess.run([PHP, "-d", "display_errors=0", "-r", WRAPPER],
                              env=env, capture_output=True, text=True, timeout=12)

    def test_command_center_is_readonly_and_never_invents_actions(self):
        result = self.view()
        self.assertEqual(result.returncode, 0, result.stderr[-500:])
        self.assertIn("اتاق فرمان چرخهٔ ساعتی ۰۵", result.stdout)
        self.assertIn("۲۰ اقدام", result.stdout)
        self.assertIn("تعداد اقدامات واقعی نامعلوم است", result.stdout)
        self.assertIn("عملیات مستقلاً تأییدشده از این قالب", result.stdout)

    def test_structured_action_receipt_claims_are_not_marked_verified(self):
        payload = {
            "version": 1, "report_code": "05-0027",
            "actions": [
                {"id": "ZM05-20261102-A01", "title_fa": "اصلاح آزمون مستقل مسیر <خطر>",
                 "status": "completed",
                 "evidence_url": "https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41410088193",
                 "impact_fa": "تأیید خروجی منبع، نه استقرار"},
                {"id": "ZM05-20261102-A02", "title_fa": "تأیید اتصال درگاه بانک شهر",
                 "status": "blocked", "evidence_url": "", "impact_fa": "مدرک بانکی موجود نیست"}
            ]
        }
        receipt = "\nZM_ACTIONS_V1_START\n" + json.dumps(payload, ensure_ascii=False) + "\nZM_ACTIONS_V1_END"
        with sqlite3.connect(self.archive) as db:
            db.execute("UPDATE reports SET body=? WHERE report_code='05-0027'",
                       ("گزارش کار، داده آزمایشی معتبر برای کنترل امنیت. " + receipt,))
        result = self.view()
        self.assertEqual(result.returncode, 0, result.stderr[-500:])
        self.assertIn("1 / ۲۰", result.stdout)
        self.assertIn("ZM05-20261102-A01", result.stdout)
        self.assertNotIn("ZM_ACTIONS_V1_START", result.stdout)
        self.assertIn("فهرست ساختاریافتهٔ اقدامات در جدول اتاق فرمان", result.stdout)
        self.assertIn("&lt;خطر&gt;", result.stdout)
        self.assertNotIn("<خطر>", result.stdout)
        self.assertIn("نیازمند راستی‌آزمایی", result.stdout)
        self.assertIn("تأیید مستقل این ردیف‌ها انجام نشده است", result.stdout)
        self.assertIn("کسری ردیف‌های عملیاتی ثبت‌شده نسبت به هدف: 18", result.stdout)
        self.assertNotIn("اعتبارسنجی آرشیو ناموفق", result.stdout)

    def test_bad_action_receipts_fail_closed_without_miscounting(self):
        cases = [
            {"version": 1, "report_code": "05-9999", "actions": []},
            {"version": 1, "report_code": "05-0027", "actions": [
                {"id": "ZM05-20261102-A01", "title_fa": "اقدام کامل آزمون",
                 "status": "completed", "evidence_url": "javascript:alert(1)"}]},
            {"version": 1, "report_code": "05-0027", "actions": [
                {"id": "ZM05-20261102-A01", "title_fa": "اقدام کامل آزمون",
                 "status": "completed", "evidence_url": ""}]},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                receipt = "\nZM_ACTIONS_V1_START\n" + json.dumps(payload, ensure_ascii=False) + "\nZM_ACTIONS_V1_END"
                with sqlite3.connect(self.archive) as db:
                    db.execute("UPDATE reports SET body=? WHERE report_code='05-0027'",
                               ("گزارش آزمایشی نامعتبر برای کنترل عدم اعتماد. " + receipt,))
                result = self.view()
                self.assertEqual(result.returncode, 0, result.stderr[-500:])
                self.assertIn("رسید ساختاریافته ناسازگار یا ناقص است", result.stdout)
                self.assertNotIn("javascript:alert(1)", result.stdout)

    def test_persian_source_character_length_does_not_hide_valid_archive(self):
        # The GitHub receipt extractor limits Unicode characters, whereas PHP
        # strlen measures UTF-8 bytes; a valid Persian report may exceed 8 KB.
        body = "گزارش واقعی ثبت خروجی با متن فارسی. " + ("زمرد ملل اقدام مستند " * 300)
        self.assertLessEqual(len(body), 8000)
        self.assertGreater(len(body.encode("utf-8")), 8000)
        self.assertLess(len(body.encode("utf-8")), 32000)
        with sqlite3.connect(self.archive) as db:
            db.execute("UPDATE reports SET body=? WHERE report_code='05-0027'", (body,))
        result = self.view()
        self.assertEqual(result.returncode, 0, result.stderr[-500:])
        self.assertIn("05-0027", result.stdout)
        self.assertIn("زمرد ملل اقدام مستند", result.stdout)
        self.assertNotIn("اعتبارسنجی آرشیو ناموفق", result.stdout)

    def test_private_index_shows_unique_claims_without_false_verification(self):
        payload = {"version": 1, "report_code": "05-0027", "actions": [
            {"id": "ZM05-0027-A01", "title_fa": "بهبود امنیت مسیر خرید کالا",
             "status": "completed",
             "evidence_url": "https://github.com/mojtabarozegar11-ship-it/Saeit/commit/" + "a" * 40,
             "impact_fa": "کاهش ریسک گزارش شده"}
        ]}
        body = ("گزارش فارسی معتبر با سند غیرمحرمانه.\nZM_ACTIONS_V1_START\n"
                + json.dumps(payload, ensure_ascii=False) + "\nZM_ACTIONS_V1_END")
        with sqlite3.connect(self.archive) as db:
            db.execute("UPDATE reports SET body=? WHERE report_code='05-0027'", (body,))
        self.archive.chmod(0o600)
        index = self.folder / "chatgpt_actions_index.sqlite3"
        self.assertEqual(rebuild(self.archive, index), (1, 0, 27))
        result = self.view()
        self.assertEqual(result.returncode, 0, result.stderr[-500:])
        self.assertIn("اقدامات با شناسه یکتای ثبت‌شده", result.stdout)
        self.assertIn("نمایهٔ جلوگیری از تکرار: 1 شناسهٔ یکتا", result.stdout)
        self.assertIn("1 ردیف کامل اظهاریِ غیرتکراری", result.stdout)
        self.assertIn("عملیات مستقلاً تأییدشده از این قالب", result.stdout)

    def test_foreign_action_id_is_rejected_in_all_recent_receipts(self):
        evidence = "https://github.com/mojtabarozegar11-ship-it/Saeit/commit/" + "a" * 40
        for number in (26, 27):
            code = f"05-{number:04d}"
            payload = {"version": 1, "report_code": code, "actions": [
                {"id": "ZM05-REPEATED-A01", "title_fa": "اقدام تکراری برای بررسی",
                 "status": "completed", "evidence_url": evidence, "impact_fa": "تکرار ممنوع"}
            ]}
            body = ("گزارش آزمایشی برای شناسایی اقدام تکراری.\nZM_ACTIONS_V1_START\n"
                    + json.dumps(payload, ensure_ascii=False) + "\nZM_ACTIONS_V1_END")
            with sqlite3.connect(self.archive) as db:
                db.execute("UPDATE reports SET body=? WHERE report_code=?", (body, code))
        self.archive.chmod(0o600)
        self.assertEqual(rebuild(self.archive, self.folder / "chatgpt_actions_index.sqlite3"),
                         (0, 2, 27))
        result = self.view()
        self.assertEqual(result.returncode, 0, result.stderr[-500:])
        self.assertIn("رسید جدید به علت ناسازگاری یا تکرار شناسه", result.stdout)
        self.assertIn("0 ردیف کامل اظهاریِ غیرتکراری", result.stdout)
        self.assertNotIn("اعتبارسنجی آرشیو ناموفق", result.stdout)

    def test_admin_paginated_persian_escape_and_five_cycles(self):
        first = self.view()
        self.assertEqual(first.returncode, 0, first.stderr[-500:])
        self.assertIn("تعداد گزارش‌های بایگانی‌شده: 27", first.stdout)
        self.assertIn("پایش پنج چرخهٔ ساعتی", first.stdout)
        self.assertIn("آخرین دریافت منبع", first.stdout)
        self.assertIn("فاقد اتصال خودکار و خصوصی", first.stdout)
        self.assertIn("متصل به دفتر مدیریت ۰۵", first.stdout)
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

    def test_stale_receipt_feed_warns_and_future_clock_blocks(self):
        with sqlite3.connect(self.archive) as db:
            db.execute("UPDATE metadata SET value='2020-01-01T00:00:00+00:00' WHERE name='last_checked_at'")
        output = self.view()
        self.assertEqual(output.returncode, 0)
        self.assertIn("هشدار: از آخرین دریافت موفق گزارش بیش از دو ساعت گذشته است", output.stdout)
        with sqlite3.connect(self.archive) as db:
            db.execute("UPDATE metadata SET value='2099-01-01T00:00:00+00:00' WHERE name='last_checked_at'")
        invalid = self.view()
        self.assertIn("اعتبارسنجی آرشیو ناموفق بود", invalid.stdout)

    def test_three_public_report_cycles_are_separate_and_readonly(self):
        public = self.folder / "chatgpt_reports_public_cycles.sqlite3"
        with sqlite3.connect(public) as db:
            db.execute("CREATE TABLE reports (seq INTEGER PRIMARY KEY, report_code TEXT NOT NULL UNIQUE, comment_id INTEGER NOT NULL UNIQUE, occurred_at TEXT NOT NULL, body TEXT NOT NULL, evidence_url TEXT NOT NULL)")
            db.execute("CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("PRAGMA user_version=1")
            db.execute("INSERT INTO metadata VALUES ('source','github:mojtabarozegar11-ship-it/Saeit:issue:1514')")
            db.execute("INSERT INTO metadata VALUES ('last_checked_at','2026-11-02T04:00:00+00:00')")
            for cycle, number, cid in [("01", 13, 1013), ("02", 14, 2014), ("04", 14, 4014)]:
                db.execute("INSERT INTO reports(report_code,comment_id,occurred_at,body,evidence_url) VALUES (?,?,?,?,?)",
                           (f"{cycle}-{number:04d}", cid, "2026-11-02T04:00:00+00:00",
                            "گزارش فارسی ساختگی از منبع عمومی <script>x()</script> بدون داده خصوصی.",
                            f"https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1514#issuecomment-{cid}"))
        public.chmod(0o600)
        dashboard=self.view()
        self.assertEqual(dashboard.returncode, 0, dashboard.stderr[-200:])
        self.assertIn("دفتر عمومی ۱۵۱۴ · متصل", dashboard.stdout)
        self.assertIn("01-0013", dashboard.stdout)
        self.assertIn("02-0014", dashboard.stdout)
        self.assertIn("04-0014", dashboard.stdout)
        for cycle, expected in [("01","01-0013"),("02","02-0014"),("04","04-0014")]:
            page=self.view(cycle=cycle)
            self.assertEqual(page.returncode, 0, page.stderr[-200:])
            self.assertIn("<h3>"+expected+"</h3>", page.stdout)
            self.assertIn("issues/1514#issuecomment-", page.stdout)
            self.assertNotIn("<script>x()</script>", page.stdout)
            self.assertIn("&lt;script&gt;x()&lt;/script&gt;", page.stdout)
        missing=self.view(cycle="03")
        self.assertIn("هنوز گزارش شماره‌دار از منبع معتبر دریافت نشده است", missing.stdout)
        self.assertNotIn("<h3>01-0013</h3>", missing.stdout)
        self.assertNotEqual(self.view(role="viewer", cycle="01").returncode, 0)
        public.chmod(0o644)
        blocked=self.view(cycle="01")
        self.assertIn("اعتبارسنجی آرشیو ناموفق بود", blocked.stdout)
        public.chmod(0o600)
        with sqlite3.connect(public) as db:
            db.execute("UPDATE metadata SET value='forged' WHERE name='source'")
        rejected=self.view(cycle="04")
        self.assertIn("اعتبارسنجی آرشیو ناموفق بود", rejected.stdout)

    def test_public_persian_summaries_identity_and_fail_closed(self):
        public = self.folder / "chatgpt_reports_public_cycles.sqlite3"
        with sqlite3.connect(public) as db:
            db.execute("CREATE TABLE reports (seq INTEGER PRIMARY KEY, report_code TEXT NOT NULL UNIQUE, comment_id INTEGER NOT NULL UNIQUE, occurred_at TEXT NOT NULL, body TEXT NOT NULL, evidence_url TEXT NOT NULL)")
            db.execute("CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("PRAGMA user_version=1")
            db.execute("INSERT INTO metadata VALUES ('source','github:mojtabarozegar11-ship-it/Saeit:issue:1514')")
            db.execute("INSERT INTO metadata VALUES ('last_checked_at','2026-11-02T04:00:00+00:00')")
            db.execute("INSERT INTO reports(report_code,comment_id,occurred_at,body,evidence_url) VALUES (?,?,?,?,?)",
                       ("01-0002", 11112, "2026-11-02T04:00:00+00:00",
                        "English-only text that must never appear raw in Persian report mode.",
                        "https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1514#issuecomment-11112"))
        public.chmod(0o600)
        pack = self.folder / "chatgpt_reports_public_fa.json"
        payload = {
            "source": "github:mojtabarozegar11-ship-it/Saeit:issue:1514",
            "version": 1, "kind": "persian_public_cycle_summaries",
            "items": {"01-0002": {"comment_id": 11112,
                                  "text_fa": "خلاصه مستند فارسی؛ صرف گزارش ادعای انتشار یا درآمد ندارد."}},
        }
        pack.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        pack.chmod(0o600)
        translated = self.view(cycle="01")
        self.assertEqual(translated.returncode, 0, translated.stderr[-200:])
        self.assertIn("خلاصهٔ فارسی مستند از گزارش", translated.stdout)
        self.assertIn("خلاصه مستند فارسی", translated.stdout)
        self.assertNotIn("English-only text", translated.stdout)
        self.assertNotIn("اعتبارسنجی آرشیو ناموفق بود", translated.stdout)
        self.assertNotEqual(self.view(role="viewer", cycle="01").returncode, 0)
        payload["items"]["01-0002"]["comment_id"] = 99999
        pack.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        blocked = self.view(cycle="01")
        self.assertIn("اعتبارسنجی آرشیو ناموفق بود", blocked.stdout)
        payload["items"]["01-0002"]["comment_id"] = 11112
        pack.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        pack.chmod(0o644)
        blocked = self.view(cycle="01")
        self.assertIn("اعتبارسنجی آرشیو ناموفق بود", blocked.stdout)

    def test_public_translation_package_is_public_only_and_numbered(self):
        source_file = ROOT / "content/zomorod-business/chatgpt_reports_public_fa.json"
        payload = json.loads(source_file.read_text(encoding="utf-8"))
        self.assertEqual(payload["source"], "github:mojtabarozegar11-ship-it/Saeit:issue:1514")
        self.assertEqual(payload["kind"], "persian_public_cycle_summaries")
        self.assertEqual(payload["version"], 1)
        self.assertEqual(len(payload["items"]), 25)
        for code, item in payload["items"].items():
            self.assertRegex(code, r"^(01|02|04)-[0-9]{4}$")
            self.assertGreater(item["comment_id"], 0)
            self.assertGreater(len(item["text_fa"]), 50)
            self.assertNotIn("https://docs.google.com", item["text_fa"])
            self.assertNotIn("/Research/", item["text_fa"])
            self.assertNotIn("/Game Releases/", item["text_fa"])

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
