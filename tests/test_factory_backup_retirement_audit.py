import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "factory_backup_retirement_audit.py"
SPEC = importlib.util.spec_from_file_location("factory_backup_retirement_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RetirementAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "factory-runtime"
        self.backups = self.root / "operations" / "backups"
        self.backups.mkdir(parents=True)
        (self.root / "django-app").mkdir()
        (self.root / "django-app" / "db.sqlite3").write_bytes(b"live")

    def test_identical_content_never_permits_deletion(self):
        (self.backups / "old.sqlite3").write_bytes(b"snapshot")
        nested = self.backups / "native-master"
        nested.mkdir()
        (nested / "copy.sqlite3").write_bytes(b"snapshot")
        report = MODULE.audit(self.root, hash_files=True)
        self.assertEqual(report["sqlite_backup_count"], 2)
        self.assertEqual(len(report["identical_content_groups"]), 1)
        self.assertEqual(report["verified_safe_deletion_paths"], [])
        self.assertTrue((self.backups / "old.sqlite3").exists())

    def test_same_size_is_not_exact_duplicate(self):
        (self.backups / "a.sqlite3").write_bytes(b"ab")
        (self.backups / "b.sqlite3").write_bytes(b"cd")
        report = MODULE.audit(self.root, hash_files=True)
        self.assertEqual(len(report["same_size_groups"]), 1)
        self.assertEqual(report["identical_content_groups"], [])
        self.assertGreaterEqual(report["disk"]["required_free_before_new_local_snapshot_bytes"], 2 * MODULE.GIB + 4)

    def test_symlink_backup_is_not_scanned(self):
        other = Path(self.temp.name) / "elsewhere.sqlite3"
        other.write_bytes(b"sensitive")
        (self.backups / "link.sqlite3").symlink_to(other)
        report = MODULE.audit(self.root, hash_files=True)
        self.assertEqual(report["sqlite_backup_count"], 0)

    def test_rejects_symlink_backup_root(self):
        other = Path(self.temp.name) / "other"
        other.mkdir()
        self.backups.rmdir()
        self.backups.symlink_to(other, target_is_directory=True)
        with self.assertRaises(ValueError):
            MODULE.audit(self.root, hash_files=False)

    def test_inventory_without_full_hash_is_explicitly_unverified(self):
        (self.backups / "a.sqlite3").write_bytes(b"snapshot")
        report = MODULE.audit(self.root, hash_files=False)
        self.assertFalse(report["sha256_complete"])
        self.assertIsNone(report["identical_content_groups"])
        self.assertIsNone(report["files"][0]["sha256"])


if __name__ == "__main__":
    unittest.main()
