"""Local-only non-destructive acceptance checks for backup destination readiness."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import mojplaywin_backup_gzip_destination_preflight_v3 as preflight


class DestinationReadinessFixtures(unittest.TestCase):
    def setUp(self):
        obj = tempfile.TemporaryDirectory(prefix="gzip-v3-preflight-")
        self.addCleanup(obj.cleanup)
        self.root = Path(obj.name)
        self.backups = self.root / ".private-mojplaywin-offhost-backups"
        self.sec = self.root / ".config" / "mojplaywin-backup-recovery"
        self.gnupg = self.sec / "gnupg-v2"
        for p in (self.backups, self.sec, self.gnupg):
            p.mkdir(mode=0o700, parents=True)
            p.chmod(0o700)
        self.key = self.sec / "recovery-key.bin"
        self.key.write_bytes(b"s" * 32)
        self.key.chmod(0o600)

    def check(self):
        return preflight.check("20261020", home=self.root, min_free=0)

    def test_ready_with_owned_private_new_names(self):
        r = self.check()
        self.assertTrue(r["safe_to_begin_scoped_backup"])
        self.assertTrue(r["new_version_output_names_free"])
        self.assertFalse(r["isolated_restore_verified"])
        self.assertFalse(r["release_permitted"])

    def test_old_partial_is_preserved_but_new_date_checks_only_new_names(self):
        historical = self.backups / "mojplaywin_20261017_mysql_gpgv2.gpg.partial"
        historical.write_bytes(b"old partial must remain untouched")
        self.assertTrue(self.check()["safe_to_begin_scoped_backup"])
        self.assertEqual(historical.read_bytes(), b"old partial must remain untouched")

    def test_existing_any_new_output_blocks_without_delete(self):
        for kind in ("mysql", "files"):
            for suffix in (".gpg", ".gpg.partial", ".manifest.json"):
                name = self.backups / ("mojplaywin_20261020_" + kind + "_gpgv2" + suffix)
                name.write_bytes(b"do not overwrite")
                self.assertFalse(self.check()["safe_to_begin_scoped_backup"])
                self.assertEqual(name.read_bytes(), b"do not overwrite")
                name.unlink()

    def test_bad_key_and_dir_permissions_rejected(self):
        self.key.chmod(0o644)
        self.assertFalse(self.check()["safe_to_begin_scoped_backup"])
        self.key.chmod(0o600)
        self.gnupg.chmod(0o755)
        self.assertFalse(self.check()["safe_to_begin_scoped_backup"])

    def test_no_key_and_symlink_do_not_pass(self):
        self.key.unlink()
        self.assertFalse(self.check()["safe_to_begin_scoped_backup"])
        key_elsewhere = self.root / "different_key"
        key_elsewhere.write_bytes(b"x" * 32)
        self.key.symlink_to(key_elsewhere)
        self.assertFalse(self.check()["safe_to_begin_scoped_backup"])

    def test_not_enough_free_blocks(self):
        r = preflight.check("20261020", home=self.root, min_free=10**30)
        self.assertFalse(r["safe_to_begin_scoped_backup"])
        self.assertFalse(r["at_least_10_gib_free"])

    def test_unsafe_date_rejected(self):
        with self.assertRaises(ValueError):
            preflight.check("../etc/passwd", home=self.root, min_free=0)


if __name__ == "__main__":
    unittest.main()
