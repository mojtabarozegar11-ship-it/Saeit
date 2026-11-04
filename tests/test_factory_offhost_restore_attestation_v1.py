"""Offline restore rehearsal and signature checks; no live off-host claims."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from factory_private_checkpoint_v1 import snapshot  # noqa: E402
from factory_offhost_restore_attestation_v1 import (  # noqa: E402
    rehearse,
    verify_signed_receipt,
)


class OffHostRestoreAttestationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys = tempfile.TemporaryDirectory()
        cls.key_dir = Path(cls.keys.name)
        cls.private_key = cls.key_dir / "receiver-private.pem"
        cls.public_key = cls.key_dir / "receiver-public.pem"
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048",
             "-out", str(cls.private_key)],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(cls.private_key), "-pubout",
             "-out", str(cls.public_key)],
            check=True, capture_output=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.keys.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "source.sqlite3"
        with sqlite3.connect(self.db) as connection:
            connection.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, sku TEXT)")
            connection.execute("INSERT INTO orders (id,sku) VALUES (1,'farm_enterprise_economics')")
        self.private = self.root / "private"
        (self.private / "quality").mkdir(parents=True)
        (self.private / "production-state.json").write_text('{"quality":0}')
        (self.private / "quality" / "evidence.json").write_text('{"status":"hold"}')
        self.checkpoint = self.root / "checkpoint"
        snapshot(self.db, self.private, self.checkpoint, 32)
        self.receipt = self.root / "receipt.json"
        self.signature = self.root / "receipt.sig"
        self.host_id = "independent-backup-host-a"

    def sign(self):
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(self.private_key),
             "-out", str(self.signature), str(self.receipt)],
            check=True, capture_output=True,
        )

    def verify(self, checkpoint=None, host=None):
        return verify_signed_receipt(
            checkpoint or self.checkpoint,
            self.receipt,
            self.signature,
            self.public_key,
            host or self.host_id,
            require_root_key=False,
        )

    def prepare_signed(self):
        rehearse(self.checkpoint, self.host_id, self.receipt)
        self.sign()

    def mutate_and_sign(self, field, value):
        content = json.loads(self.receipt.read_text())
        content[field] = value
        self.receipt.write_text(json.dumps(content, sort_keys=True))
        self.sign()

    def test_restores_private_files_and_database_then_verifies_signature(self):
        self.prepare_signed()
        verified = self.verify()
        self.assertEqual(verified["restored_file_count"], 2)
        self.assertEqual(verified["status"], "restored_and_verified_offhost")
        self.assertFalse(verified["auto_restore_authorized"])

    def test_without_signature_is_not_accepted(self):
        rehearse(self.checkpoint, self.host_id, self.receipt)
        with self.assertRaises((FileNotFoundError, ValueError)):
            self.verify()

    def test_tampering_with_signed_receipt_is_detected(self):
        self.prepare_signed()
        with self.receipt.open("ab") as target:
            target.write(b"tamper")
        with self.assertRaisesRegex(ValueError, "OFFHOST_RECEIPT_SIGNATURE_INVALID"):
            self.verify()

    def test_wrong_host_id_is_not_accepted(self):
        self.prepare_signed()
        with self.assertRaisesRegex(ValueError, "OFFHOST_RECEIPT_CONTENT_MISMATCH"):
            self.verify(host="other-host")

    def test_live_verifier_requires_admin_protected_key(self):
        self.prepare_signed()
        with self.assertRaisesRegex(ValueError, "OFFHOST_KEY_NOT_ADMIN_PROTECTED"):
            verify_signed_receipt(
                self.checkpoint, self.receipt, self.signature,
                self.public_key, self.host_id,
            )

    def test_replay_against_different_checkpoint_is_blocked(self):
        self.prepare_signed()
        (self.private / "production-state.json").write_text('{"quality":1}')
        replacement = self.root / "checkpoint-new"
        snapshot(self.db, self.private, replacement, 32)
        with self.assertRaisesRegex(ValueError, "OFFHOST_RECEIPT_CONTENT_MISMATCH"):
            self.verify(checkpoint=replacement)

    def test_signed_but_stale_receipt_is_blocked(self):
        self.prepare_signed()
        old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        self.mutate_and_sign("restore_verified_utc", old)
        with self.assertRaisesRegex(ValueError, "OFFHOST_RECEIPT_STALE_OR_FUTURE"):
            self.verify()

    def test_signed_auto_restore_permission_is_still_rejected(self):
        self.prepare_signed()
        self.mutate_and_sign("auto_restore_authorized", True)
        with self.assertRaisesRegex(ValueError, "OFFHOST_RECEIPT_CONTENT_MISMATCH"):
            self.verify()

    def test_modified_checkpoint_bytes_invalidate_receipt(self):
        self.prepare_signed()
        with (self.checkpoint / "private-state.tar.gz").open("ab") as target:
            target.write(b"appended")
        with self.assertRaisesRegex(ValueError, "CHECKPOINT_ARCHIVE_DIGEST_MISMATCH"):
            self.verify()

    def test_receipt_file_cannot_be_overwritten(self):
        rehearse(self.checkpoint, self.host_id, self.receipt)
        with self.assertRaisesRegex(ValueError, "OFFHOST_RECEIPT_ALREADY_EXISTS"):
            rehearse(self.checkpoint, self.host_id, self.receipt)

    def test_receipt_cannot_be_stored_inside_checkpoint(self):
        with self.assertRaisesRegex(ValueError, "OFFHOST_RECEIPT_INSIDE_CHECKPOINT"):
            rehearse(self.checkpoint, self.host_id, self.checkpoint / "receipt.json")


if __name__ == "__main__":
    unittest.main()
