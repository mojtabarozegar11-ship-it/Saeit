"""Source contracts for emergency, read-only Zomorod agent archive UI.

The original operational panel stays active when its PHP runtime exists.
This fallback is NOT a full replacement, never retires any file, and cannot
enable/toggle workers. CI synthetic business suite independently PHP-lints app.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "content/zomorod-business/app.php"


class AgentArchiveFallbackContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APP.read_text(encoding="utf-8")
        cls.archive = cls.source.split("function zmAgentArchiveView(", 1)[1].split(
            "\nfunction req(", 1
        )[0]

    def test_old_admin_function_still_preferred(self):
        self.assertIn(
            "if(function_exists('zmAgentDb')&&function_exists('zmAgentRender'))",
            self.source,
        )
        self.assertIn("zmAgentRender(zmAgentDb($private));", self.source)
        self.assertIn("zmAgentArchiveView($private);", self.source)

    def test_archive_is_nonprivileged_but_requires_management_view_access(self):
        self.assertIn("elseif($page==='agent_center')", self.source)
        self.assertIn("authorize('view');", self.source)
        self.assertIn("SQLite3($dbfile, SQLITE3_OPEN_READONLY)", self.archive)
        self.assertIn("PRAGMA query_only=ON", self.archive)
        self.assertNotIn("SQLITE3_OPEN_READWRITE", self.archive)
        self.assertNotIn("SQLITE3_OPEN_CREATE", self.archive)

    def test_bounded_private_archive_scope(self):
        for phrase in (
            "/home/zomorod2/.private/zomorod-business",
            "is_link($dbfile)", "is_link(dirname($private))",
            "536870912", "-wal", "-shm", "-journal",
            "PRAGMA quick_check(1)", "archive_changed_during_read",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.archive)

    def test_no_private_titles_or_findings_exported(self):
        for phrase in (
            "SELECT agent_code,status,http_code,occurred_at",
            "SELECT agent_code,status,quality_score,observed_at",
            "esc($row['agent_code'])", "esc($row['status'])",
            "esc($row['observed_at'])",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.archive)
        for forbidden in (
            "SELECT * FROM site_work_outputs",
            "SELECT title", "SELECT findings_json",
            "exec('UPDATE", "exec('DELETE", "exec('INSERT",
            "crontab", "unlink(", "file_put_contents(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.archive)

    def test_original_write_controls_remain_owner_only_or_unavailable(self):
        self.assertIn("if(role()!=='admin')bail('فقط مدیر اصلی مجاز است.',403);",
                      self.source)
        self.assertIn("if(!function_exists('zmAgentDb'))bail(", self.source)
        self.assertIn("zmAgentHandle(zmAgentDb($private),$action,req('code'));",
                      self.source)

    def test_readonly_view_explicitly_rejects_legacy_deletion_inference(self):
        self.assertIn("مجوز حذف فایل‌های قدیمی را اثبات نمی‌کند", self.archive)
        self.assertIn("تاریخچه اصلی باید حفظ شود", self.archive)
        self.assertIn("در حال ثبت هم‌زمان", self.archive)


if __name__ == "__main__":
    unittest.main()
