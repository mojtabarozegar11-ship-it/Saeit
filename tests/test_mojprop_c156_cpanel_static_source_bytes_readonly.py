"""C156 synthetic, isolated; no actual cPanel account access in CI."""
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from scripts import mojprop_c156_cpanel_static_source_bytes_readonly as c156


class ReadOnlyDiskClassifier(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "moj-prop"
        self.root.mkdir(mode=0o700)
        (self.root / "contact").mkdir(mode=0o700)

    def put(self, which, contents, mode=0o600):
        p = self.root / c156.FILES[which]
        p.write_bytes(contents)
        p.chmod(mode)
        return p

    def test_source_allowlist_does_not_touch_db_media_or_writable_files(self):
        self.assertEqual(set(c156.FILES), {"home", "contact"})
        self.assertEqual(set(c156.PINNED_GIT_BLOBS), {"home", "contact"})
        self.assertTrue(all(len(v) <= 3 for v in c156.PINNED_GIT_BLOBS.values()))

    def test_byte_identical_main_known_source_classified(self):
        self.assertEqual(
            c156.classify(b"identity synthetic", "home"),
            "unreviewed_or_unavailable",
        )
        self.assertEqual(
            c156.git_blob_id(b"hello"),
            "b6fc4c620b67d95f953a5c1c1230aaab5db5a1b0",
        )

    def test_absent_two_files_fail_closed(self):
        report = c156.inspect_disk(self.root)
        self.assertFalse(report["both_disk_files_reviewed_exact"])
        self.assertEqual(
            list(report["pages"].values()),
            ["unreviewed_or_unavailable", "unreviewed_or_unavailable"],
        )

    def test_non_source_bytes_never_are_admitted(self):
        self.put("home", b"<html>not reviewed</html>")
        self.put("contact", b"<html>not reviewed</html>")
        report = c156.inspect_disk(self.root)
        self.assertFalse(report["both_disk_files_reviewed_exact"])

    def test_world_writable_home_refused_before_hash(self):
        self.put("home", b"UNKNOWN PUBLIC FILE", mode=0o666)
        with patch.object(c156, "classify", side_effect=AssertionError("unsafe read")):
            r = c156.inspect_disk(self.root)
        self.assertEqual(r["pages"]["home"], "unreviewed_or_unavailable")

    def test_symlink_to_arbitrary_file_refused(self):
        outside = Path(self.tmp.name) / "outside"
        outside.write_text("never-read-me")
        (self.root / "index.html").symlink_to(outside)
        with patch.object(c156, "classify", side_effect=AssertionError("unsafe read")):
            r = c156.inspect_disk(self.root)
        self.assertEqual(r["pages"]["home"], "unreviewed_or_unavailable")

    def test_symlinked_contact_parent_refused(self):
        (self.root / "contact").rmdir()
        outside = Path(self.tmp.name) / "elsewhere"
        outside.mkdir()
        (outside / "index.html").write_text("unknown")
        (self.root / "contact").symlink_to(outside, target_is_directory=True)
        with patch.object(c156, "classify", side_effect=AssertionError("unsafe read")):
            r = c156.inspect_disk(self.root)
        self.assertEqual(r["pages"]["contact"], "unreviewed_or_unavailable")

    def test_hardlink_refused(self):
        self.put("home", b"not-meaningful")
        os.link(self.root / "index.html", self.root / "copy")
        with patch.object(c156, "classify", side_effect=AssertionError("unsafe read")):
            r = c156.inspect_disk(self.root)
        self.assertEqual(r["pages"]["home"], "unreviewed_or_unavailable")

    def test_oversized_file_is_not_opened_for_hashing(self):
        self.put("home", b"a" * (c156.MAX_BYTES + 1))
        with patch.object(c156, "classify", side_effect=AssertionError("oversized")):
            r = c156.inspect_disk(self.root)
        self.assertEqual(r["pages"]["home"], "unreviewed_or_unavailable")

    def test_root_symlink_refused(self):
        other = Path(self.tmp.name) / "root-link"
        other.symlink_to(self.root, target_is_directory=True)
        r = c156.inspect_disk(other)
        self.assertFalse(r["both_disk_files_reviewed_exact"])

    def test_unknown_owner_refused(self):
        self.put("home", b"unknown")
        r = c156.inspect_disk(self.root, expected_uid=os.geteuid() + 234)
        self.assertFalse(r["both_disk_files_reviewed_exact"])

    def test_report_excludes_file_contents_sha_values_and_release(self):
        r = c156.inspect_disk(self.root)
        self.assertTrue(r["read_only"])
        self.assertFalse(r["release_authorized"])
        self.assertFalse(r["database_backup_or_restore_performed"])
        self.assertFalse(r["customer_records_accessed"])
        self.assertTrue(r["no_file_content_hash_or_path_logged"])
        self.assertEqual(set(r["pages"]), {"home", "contact"})


if __name__ == "__main__":
    unittest.main()
