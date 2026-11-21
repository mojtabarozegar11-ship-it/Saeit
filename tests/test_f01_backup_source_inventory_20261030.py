import tempfile
import unittest
from pathlib import Path
from scripts.f01_backup_source_inventory_20261030 import inspection

class BackupSourceInventoryTests(unittest.TestCase):
    def test_only_metadata_and_no_transfer(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            b = root / "operations" / "backups"
            b.mkdir(parents=True)
            (b / "master-before-20261029T120000Z.sqlite3").write_bytes(b"1234")
            (b / "ignore.txt").write_bytes(b"irrelevant")
            result = inspection(root)
            self.assertEqual(result["status"], "INSPECT_ONLY")
            self.assertEqual(result["existing_snapshot_count"], 1)
            self.assertEqual(result["newest_three_metadata_only"][0]["bytes"], 4)
            self.assertNotIn("master-before", str(result))
            self.assertFalse(result["transfer_allowed"])
            self.assertFalse(result["reboot_allowed"])

    def test_reject_linked_ancestor(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root / "real").mkdir()
            (root / "linked").symlink_to(root / "real", target_is_directory=True)
            self.assertEqual(inspection(root / "linked")["reason"], "LINKED_ANCESTOR")

    def test_reject_linked_operations(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/"other"/"backups").mkdir(parents=True)
            (root/"operations").symlink_to(root/"other",target_is_directory=True)
            self.assertEqual(inspection(root)["status"], "BLOCKED")

    def test_missing_root(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(inspection(Path(t))["reason"], "BACKUPS_UNAVAILABLE")

if __name__ == "__main__":
    unittest.main()
