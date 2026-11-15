"""One-time static-only Starter30 publication tests in an isolated temp tree."""
from pathlib import Path
from unittest.mock import patch
import json
import os
import tempfile
import unittest

from scripts import mojprop_starter30_static_release as rel

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "templates/moj-prop-v4/starter-30-trx"
COMMIT = "a" * 40


class Starter30StaticReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.docroot = self.home / "mojplaywin.com"
        self.route = self.docroot / "moj-prop"
        self.route.mkdir(parents=True)
        self.target = self.route / "starter-30-trx"
        self.backup = self.home / ".mojprop-starter30-backups"
        self.stage = self.home / ".mojprop-starter30-stage-123" / "templates/moj-prop-v4/starter-30-trx"
        self.stage.mkdir(parents=True)
        for name in rel.FILES:
            (self.stage / name).write_bytes((SOURCE / name).read_bytes())
        self.patchers = [
            patch.object(rel, "HOME", self.home),
            patch.object(rel, "ROOT", self.docroot),
            patch.object(rel, "TARGET", self.target),
            patch.object(rel, "BACKUP", self.backup),
            patch.object(rel, "_host"),
        ]
        for p in self.patchers:
            p.start()
            self.addCleanup(p.stop)

    def test_precisely_three_static_files(self):
        self.assertEqual(set(rel.FILES), {"index.html", "journal-template.csv", "journal-guide.txt"})

    def test_preflight_is_read_only(self):
        report = rel.preflight("123", COMMIT)
        self.assertEqual(report["scope"], "static-no-payment-no-backend")
        self.assertFalse(self.target.exists())
        self.assertFalse(self.backup.exists())

    def test_source_digest_pinned_in_manifest(self):
        report = rel.preflight("123", COMMIT)
        self.assertEqual(report["commit"], COMMIT)
        for name in rel.FILES:
            self.assertEqual(report["files"][name], rel.sha((SOURCE / name).read_bytes()))

    def test_deploy_requires_explicit_owner_release_flag(self):
        with patch.dict(os.environ, {"MOJPROP_STARTER30_OWNER_APPROVED": ""}):
            with self.assertRaises(RuntimeError):
                rel.deploy("123", COMMIT)
        self.assertFalse(self.target.exists())

    def test_deploy_and_rollback_do_not_touch_database(self):
        with patch.dict(os.environ, {"MOJPROP_STARTER30_OWNER_APPROVED": "static-only-approved"}):
            rel.deploy("123", COMMIT)
        for name in rel.FILES:
            self.assertEqual((self.target / name).read_bytes(), (SOURCE / name).read_bytes())
        self.assertFalse((self.docroot / "core").exists())
        rel.rollback("123", COMMIT)
        self.assertFalse(any((self.target / name).exists() for name in rel.FILES))

    def test_wrong_commit_refused_before_writes(self):
        with self.assertRaises(ValueError):
            rel.preflight("123", "not-a-commit")
        self.assertFalse(self.target.exists())

    def test_path_traversal_in_run_id_refused(self):
        with self.assertRaises(ValueError):
            rel.preflight("../123", COMMIT)

    def test_existing_customer_asset_refused(self):
        self.target.mkdir(parents=True)
        (self.target / "index.html").write_text("independent customer document")
        with self.assertRaises(RuntimeError):
            rel.preflight("123", COMMIT)
        self.assertEqual((self.target / "index.html").read_text(), "independent customer document")

    def test_existing_symlink_refused(self):
        self.target.mkdir(parents=True)
        (self.target / "index.html").symlink_to(self.stage / "index.html")
        with self.assertRaises(RuntimeError):
            rel.preflight("123", COMMIT)

    def test_tampered_staged_no_payment_copy_refused(self):
        (self.stage / "index.html").write_text("<html>BUY NOW</html>")
        with self.assertRaises(RuntimeError):
            rel.preflight("123", COMMIT)

    def test_missing_staged_guide_refused(self):
        (self.stage / "journal-guide.txt").unlink()
        with self.assertRaises(RuntimeError):
            rel.preflight("123", COMMIT)

    def test_wrong_rollback_commit_denied(self):
        with patch.dict(os.environ, {"MOJPROP_STARTER30_OWNER_APPROVED": "static-only-approved"}):
            rel.deploy("123", COMMIT)
        with self.assertRaises(RuntimeError):
            rel.rollback("123", "b" * 40)
        self.assertTrue((self.target / "index.html").exists())

    def test_existing_changed_asset_rollback_refused(self):
        with patch.dict(os.environ, {"MOJPROP_STARTER30_OWNER_APPROVED": "static-only-approved"}):
            rel.deploy("123", COMMIT)
        (self.target / "index.html").write_text("unexpected concurrent change")
        with self.assertRaises(RuntimeError):
            rel.rollback("123", COMMIT)
        self.assertEqual((self.target / "index.html").read_text(), "unexpected concurrent change")

    def test_replay_release_refused(self):
        with patch.dict(os.environ, {"MOJPROP_STARTER30_OWNER_APPROVED": "static-only-approved"}):
            rel.deploy("123", COMMIT)
            with self.assertRaises(RuntimeError):
                rel.deploy("123", COMMIT)

    def test_rollback_manifest_permissions_private(self):
        with patch.dict(os.environ, {"MOJPROP_STARTER30_OWNER_APPROVED": "static-only-approved"}):
            rel.deploy("123", COMMIT)
        manifest = self.backup / "123" / "manifest.json"
        self.assertEqual(manifest.stat().st_mode & 0o077, 0)
        self.assertEqual(json.loads(manifest.read_text("utf-8"))["run_id"], "123")

    def test_unprotected_manifest_denies_rollback(self):
        with patch.dict(os.environ, {"MOJPROP_STARTER30_OWNER_APPROVED": "static-only-approved"}):
            rel.deploy("123", COMMIT)
        manifest = self.backup / "123" / "manifest.json"
        manifest.chmod(0o644)
        with self.assertRaises(RuntimeError):
            rel.rollback("123", COMMIT)


if __name__ == "__main__":
    unittest.main()
