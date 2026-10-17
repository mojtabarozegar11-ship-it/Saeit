"""No-write regression tests for lexical rewrite and backup-evidence audit."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.mojplaywin_rewrite_backup_readonly import audit, summarize_rewrites


class MojPlayWinRewriteBackupReadonlyTests(unittest.TestCase):
    def test_counts_but_does_not_leak_rewrite_targets_or_private_paths(self):
        rules = """
        PassengerEnabled on
        RewriteEngine On
        RewriteCond %{REQUEST_URI} !^/picm/
        RewriteRule ^(.*)$ /secret/internal/target/$1 [L,QSA]
        """
        result = summarize_rewrites(rules)
        self.assertTrue(result["htaccess_readable"])
        self.assertEqual(result["rewriterule_count"], 1)
        self.assertEqual(result["rewritecond_count"], 1)
        self.assertTrue(result["explicit_prefix_mentions"]["picm"])
        self.assertNotIn("secret/internal/target", str(result))
        self.assertIsInstance(result["catch_all_patterns_present"], bool)

    def test_legacy_backup_presence_cannot_certify_real_restore(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            docroot=root/"www"
            backup_root=root/"backups"
            docroot.mkdir()
            backup_root.mkdir()
            (docroot/".htaccess").write_text("PassengerEnabled on\nRewriteRule ^(.*)$ index.py [L]")
            b=backup_root/"mojplaywin-main-12345"
            b.mkdir()
            (b/"manifest.json").write_text(json.dumps({"config/urls.py":{"existed":True}, "core/templates/mojplaywin/home.html":{"existed":True}}))
            (b/"DEPLOYED.json").write_text("{}")
            report=audit(docroot,backup_root)
            self.assertEqual(report["legacy_backups"]["legacy_manifest_found_count"],1)
            self.assertFalse(report["legacy_backups"]["database_backup_verified"])
            self.assertFalse(report["legacy_backups"]["media_backup_verified"])
            self.assertFalse(report["restore_test_verified"])
            self.assertFalse(report["release_permitted"])
            self.assertNotIn("12345",str(report))
            self.assertNotIn(str(root),str(report))

    def test_missing_source_and_backup_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            report=audit(root/"no-www",root/"no-backups")
            self.assertFalse(report["rewrite"]["htaccess_readable"])
            self.assertFalse(report["legacy_backups"]["inspection_complete"])
            self.assertFalse(report["production_isolation_proven"])

    def test_manifest_parse_error_remains_unverified(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"mojplaywin-main-42").mkdir()
            (root/"mojplaywin-main-42"/"manifest.json").write_text("not json")
            report=audit(root,root)
            self.assertEqual(report["legacy_backups"]["legacy_manifests_unreadable_or_invalid"],1)
            self.assertFalse(report["release_permitted"])


if __name__=="__main__":
    unittest.main()
