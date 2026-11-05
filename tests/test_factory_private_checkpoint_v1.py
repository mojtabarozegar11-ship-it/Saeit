"""Offline verification of isolated factory state checkpoint safeguards."""

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.factory_private_checkpoint_v1 import (
    ARCHIVE,
    DB_COPY,
    MANIFEST,
    snapshot,
    verify,
)


class FactoryPrivateCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "isolated.sqlite3"
        with sqlite3.connect(self.db) as connection:
            connection.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, sku TEXT)")
            connection.execute("INSERT INTO orders (sku) VALUES (?)", ("farm_enterprise_economics",))
        self.private = self.root / "private"
        (self.private / "quality-excellence" / "product-flow").mkdir(parents=True)
        (self.private / "production-state.json").write_text('{"active_product_slot_recipes":["farm_enterprise_economics"]}')
        (self.private / "quality-excellence" / "product-flow" / "current.json").write_text('{"status":"hold"}')
        self.destination = self.root / "backup" / "factory-checkpoint"
        self.destination.parent.mkdir(mode=0o700)

    def create(self):
        return snapshot(self.db, self.private, self.destination, 32)

    def test_round_trip_preserves_database_and_private_bytes(self):
        result = self.create()
        self.assertEqual(result["file_count"], 2)
        self.assertFalse(result["independent_offhost_copy_verified"])
        self.assertFalse(result["auto_restore_authorized"])
        self.assertEqual(verify(self.destination)["db_sha256"], result["db_sha256"])
        with sqlite3.connect(self.destination / DB_COPY) as connection:
            self.assertEqual(connection.execute("SELECT sku FROM orders").fetchone()[0],
                             "farm_enterprise_economics")
        self.assertTrue((self.destination / ARCHIVE).is_file())
        self.assertTrue((self.destination / MANIFEST).is_file())

    def test_original_private_files_are_not_changed(self):
        original = (self.private / "production-state.json").read_bytes()
        self.create()
        self.assertEqual((self.private / "production-state.json").read_bytes(), original)

    def test_tampered_backup_archive_is_rejected(self):
        self.create()
        with (self.destination / ARCHIVE).open("ab") as out:
            out.write(b"tamper")
        with self.assertRaisesRegex(ValueError, "CHECKPOINT_ARCHIVE_DIGEST_MISMATCH"):
            verify(self.destination)

    def test_tampered_database_is_rejected(self):
        self.create()
        with (self.destination / DB_COPY).open("ab") as out:
            out.write(b"tamper")
        with self.assertRaisesRegex(ValueError, "CHECKPOINT_DB_DIGEST_MISMATCH"):
            verify(self.destination)

    def test_manifest_cannot_claim_independent_backup(self):
        self.create()
        manifest_file = self.destination / MANIFEST
        manifest = json.loads(manifest_file.read_text())
        manifest["independent_offhost_copy_verified"] = True
        manifest_file.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "CHECKPOINT_OFFHOST_CLAIM_NOT_ALLOWED"):
            verify(self.destination)

    def test_source_symlink_is_rejected_without_publishing_checkpoint(self):
        (self.private / "unsafe.json").symlink_to(self.db)
        with self.assertRaisesRegex(ValueError, "CHECKPOINT_SYMLINK_IN_PATH"):
            self.create()
        self.assertFalse(self.destination.exists())

    def test_directory_symlink_is_rejected(self):
        (self.private / "substitute").symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "CHECKPOINT_SYMLINK_IN_PATH"):
            self.create()
        self.assertFalse(self.destination.exists())

    def test_existing_checkpoint_is_never_overwritten(self):
        self.create()
        with self.assertRaisesRegex(ValueError, "CHECKPOINT_DESTINATION_ALREADY_EXISTS"):
            self.create()

    def test_small_size_cap_is_fail_closed(self):
        (self.private / "large.bin").write_bytes(b"a" * (2 * 1024 * 1024))
        with self.assertRaisesRegex(ValueError, "CHECKPOINT_SOURCE_LIMIT_EXCEEDED"):
            snapshot(self.db, self.private, self.destination, 1)
        self.assertFalse(self.destination.exists())

    def test_checkpoint_location_inside_source_is_rejected(self):
        bad = self.private / "embedded-checkpoint"
        with self.assertRaisesRegex(ValueError, "CHECKPOINT_DESTINATION_INSIDE_SOURCE"):
            snapshot(self.db, self.private, bad, 32)


if __name__ == "__main__":
    unittest.main()
