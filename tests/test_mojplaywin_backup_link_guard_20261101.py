"""Fail-closed primary backup link guards, using only private synthetic files."""
import tempfile
import unittest
from pathlib import Path

from scripts.mojplaywin_backup_stream_cpanel import assert_no_unbacked_symlinks


class BackupLinkGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root / "Saeit-staging"
        self.site = self.root / "mojplaywin.com"
        self.app.mkdir()
        self.site.mkdir()
        (self.app / "main.py").write_text("synthetic", encoding="utf-8")
        (self.site / "index.html").write_text("synthetic", encoding="utf-8")

    def test_regular_roots_without_symlinks_pass(self):
        report = assert_no_unbacked_symlinks((self.app, self.site))
        self.assertEqual(report["symlinks_inside_roots"], 0)

    def test_internal_symlink_only_passes(self):
        (self.site / "alias").symlink_to(self.app / "main.py")
        report = assert_no_unbacked_symlinks((self.app, self.site))
        self.assertEqual(report["symlinks_inside_roots"], 1)

    def test_existing_external_target_blocks_archive(self):
        private = self.root / "other-private-root"
        private.mkdir()
        (private / "external").write_text("private synthetic", encoding="utf-8")
        (self.site / "outside").symlink_to(private / "external")
        with self.assertRaisesRegex(RuntimeError, "BACKUP_LINK_OUTSIDE_APPROVED_ROOTS"):
            assert_no_unbacked_symlinks((self.app, self.site))
        self.assertTrue((private / "external").exists())

    def test_dangling_symlink_blocks_archive(self):
        (self.site / "broken").symlink_to(self.root / "missing")
        with self.assertRaisesRegex(RuntimeError, "BACKUP_LINK_UNRESOLVABLE"):
            assert_no_unbacked_symlinks((self.app, self.site))

    def test_unbounded_walk_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "BACKUP_LINK_SCAN_LIMIT"):
            assert_no_unbacked_symlinks((self.app, self.site), max_entries=1)


if __name__ == "__main__":
    unittest.main()
