"""Fail-closed primary backup link guards, using only private synthetic files."""
import tempfile
import io
import subprocess
import tarfile
import shutil
import json
import unittest
from pathlib import Path

from scripts.mojplaywin_backup_stream_cpanel import (assert_no_unbacked_symlinks, assert_scoped_public_asset_links, scoped_files_tar_command)


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



class ScopedPublicAssetsPreflightTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.account = Path(tmp.name)
        self.app = self.account / "Saeit-staging"
        self.site = self.account / "mojplaywin.com"
        self.app.mkdir()
        self.site.mkdir()
        (self.app / "main.py").write_text("synthetic", encoding="utf8")
        self.nested_site = self.site / "one-synthetic-nested-directory"
        self.nested_site.mkdir()
        self.targets = {}
        for label in ("static", "assets", "uploads"):
            t = self.account / "external-assets" / label
            t.mkdir(parents=True)
            (t / "example.css").write_text("synthetic", encoding="utf8")
            source_root = self.site if label == "static" else self.nested_site
            (source_root / label).symlink_to(t, target_is_directory=True)
            self.targets[label] = t

    def check(self, **overrides):
        args = {"roots": (self.app, self.site), "home": self.account}
        args.update(overrides)
        return assert_scoped_public_asset_links(**args)

    def test_only_three_reachable_alias_subtrees_accepted(self):
        report = self.check()
        self.assertEqual(set(report), {"static", "assets", "uploads"})
        self.assertTrue(all(v[2] == 1 for v in report.values()))
        self.assertTrue(all(v[3] == len("synthetic") for v in report.values()))
        self.assertNotIn(str(self.account), json.dumps(report))
        self.assertTrue((self.app / "main.py").exists())

    def test_synthetic_tar_materializes_aliases_inside_only_primary_roots(self):
        if not shutil.which("tar"):
            self.skipTest("GNU tar unavailable")
        private = self.account / "unlinked-independent-project"
        private.mkdir()
        (private / "unlinked-private-data.bin").write_bytes(b"synthetic")
        self.check()
        proc = subprocess.run(
            scoped_files_tar_command(self.account, (self.app, self.site)),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        )
        with tarfile.open(fileobj=io.BytesIO(proc.stdout), mode="r:") as archive:
            members = {m.name: m for m in archive.getmembers()}
            source = self.nested_site.name
            expected = (
                "Saeit-staging/main.py",
                "mojplaywin.com/static/example.css",
                "mojplaywin.com/" + source + "/assets/example.css",
                "mojplaywin.com/" + source + "/uploads/example.css",
            )
            for name in expected:
                self.assertIn(name, members)
                self.assertTrue(members[name].isfile())
            self.assertFalse(any(m.issym() or m.islnk() for m in members.values()))
            self.assertFalse(any("unlinked-independent-project" in name for name in members))
            self.assertFalse(any(name.startswith("external-assets") for name in members))

    def test_missing_alias_blocks(self):
        (self.nested_site / "uploads").unlink()
        with self.assertRaisesRegex(RuntimeError, "REQUIRED_PUBLIC_ASSET_ALIAS_MISSING"):
            self.check()

    def test_unlisted_primary_symlink_blocks(self):
        (self.app / "unexpected").symlink_to(self.targets["assets"])
        with self.assertRaisesRegex(RuntimeError, "UNKNOWN_PUBLIC_ALIAS"):
            self.check()

    def test_nested_asset_aliases_must_share_one_direct_child_parent(self):
        other = self.site / "another-synthetic-subsite"
        other.mkdir()
        (self.nested_site / "uploads").unlink()
        (other / "uploads").symlink_to(self.targets["uploads"], target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "NESTED_ASSET_PARENT_MISMATCH"):
            self.check()

    def test_deeper_nested_asset_alias_fails(self):
        deeper = self.nested_site / "deeper"
        deeper.mkdir()
        (self.nested_site / "assets").unlink()
        (deeper / "assets").symlink_to(self.targets["assets"], target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "UNEXPECTED_ASSET_ALIAS_DEPTH"):
            self.check()

    def test_nested_target_symlink_blocks(self):
        (self.targets["assets"] / "nested").symlink_to(self.targets["uploads"])
        with self.assertRaisesRegex(RuntimeError, "ASSET_TREE_UNAPPROVED_MEMBER"):
            self.check()

    def test_sensitive_alias_member_blocks(self):
        (self.targets["assets"] / "database.sql").write_text("secret synthetic", encoding="utf8")
        with self.assertRaisesRegex(RuntimeError, "ASSET_TREE_SENSITIVE_FILE_SHAPE"):
            self.check()

    def test_archive_like_asset_is_flagged_without_name_disclosure(self):
        (self.targets["assets"] / "ordinary-download.zip").write_bytes(b"synthetic")
        with self.assertRaisesRegex(RuntimeError, "ASSET_TREE_ARCHIVE_FILE_SHAPE"):
            self.check()

    def test_gzip_sidecar_with_matching_web_file_is_allowed(self):
        (self.targets["assets"] / "example.css.gz").write_bytes(b"synthetic")
        self.assertEqual(set(self.check()), {"static", "assets", "uploads"})

    def test_at_most_two_tiny_orphaned_compressed_assets_are_tolerated(self):
        (self.targets["assets"] / "unmatched-one.json.gz").write_bytes(b"synthetic")
        (self.targets["assets"] / "unmatched-two.json.gz").write_bytes(b"synthetic")
        self.assertEqual(set(self.check()), {"static", "assets", "uploads"})

    def test_third_orphan_compressed_asset_is_blocked(self):
        for label in ("one", "two", "three"):
            (self.targets["assets"] / ("unmatched-" + label + ".json.gz")).write_bytes(b"synthetic")
        with self.assertRaisesRegex(RuntimeError, "ASSET_COMPRESSED_SIDECAR_UNVERIFIED"):
            self.check()

    def test_large_orphan_compressed_asset_is_blocked(self):
        (self.targets["assets"] / "unmatched.json.gz").write_bytes(b"x" * (256 * 1024 + 1))
        with self.assertRaisesRegex(RuntimeError, "ASSET_COMPRESSED_SIDECAR_UNVERIFIED"):
            self.check()

    def test_hidden_asset_entry_blocks(self):
        (self.targets["assets"] / ".env").write_text("synthetic", encoding="utf8")
        with self.assertRaisesRegex(RuntimeError, "ASSET_TREE_UNAPPROVED_MEMBER"):
            self.check()

    def test_byte_budget_blocks(self):
        with self.assertRaisesRegex(RuntimeError, "ASSET_TREE_BYTE_LIMIT"):
            self.check(max_asset_bytes=1)

    def test_other_account_target_blocks(self):
        with tempfile.TemporaryDirectory() as external:
            link = self.nested_site / "assets"
            link.unlink()
            link.symlink_to(Path(external), target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, "ASSET_LINK_TARGET_OUT_OF_SCOPE"):
                self.check()


if __name__ == "__main__":
    unittest.main()
