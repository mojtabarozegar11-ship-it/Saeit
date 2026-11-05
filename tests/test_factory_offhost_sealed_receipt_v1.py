"""Synthetic encrypted recovery receipt chain; not a live off-host claim."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from factory_private_checkpoint_v1 import snapshot  # noqa: E402
from factory_checkpoint_sealed_transport_v1 import _fingerprint, seal  # noqa: E402
from factory_offhost_sealed_receipt_v1 import (  # noqa: E402
    rehearse_sealed, verify_signed_sealed_receipt,
)


class OffhostSealedReceiptChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receiver = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        cls.pin = _fingerprint(cls.receiver.public_key())
        cls.signing = tempfile.TemporaryDirectory()
        cls.signer_private = Path(cls.signing.name) / "independent-signing-private.pem"
        cls.signer_public = Path(cls.signing.name) / "independent-signing-public.pem"
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048",
             "-out", str(cls.signer_private)], check=True, capture_output=True,
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(cls.signer_private), "-pubout",
             "-out", str(cls.signer_public)], check=True, capture_output=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.signing.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        self.db = self.root / "factory.sqlite3"
        with sqlite3.connect(self.db) as connection:
            connection.execute("CREATE TABLE decision (id INTEGER PRIMARY KEY, state TEXT)")
            connection.execute("INSERT INTO decision VALUES (1,'PRIVATE_HOLD')")
        self.private = self.root / "private"
        self.private.mkdir(mode=0o700)
        (self.private / "cycle.json").write_text('{"product":"farm_enterprise_economics"}')
        self.checkpoint = self.root / "checkpoint"
        snapshot(self.db, self.private, self.checkpoint, 32)
        self.recipient_public = self.root / "recipient-public.pem"
        self.recipient_private = self.root / "recipient-private.pem"
        self.recipient_public.write_bytes(self.receiver.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        self.recipient_private.write_bytes(self.receiver.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
        self.recipient_private.chmod(0o600)
        self.bundle = self.root / "checkpoint.sealed"
        seal(self.checkpoint, self.recipient_public, self.pin, self.bundle,
             require_admin_key=False)
        self.receipt = self.root / "offhost-receipt.json"
        self.signature = self.root / "offhost-receipt.sig"
        self.host_id = "independent-recovery-host-alpha"

    def rehearse(self):
        return rehearse_sealed(
            self.bundle, self.recipient_private, self.pin, self.host_id,
            self.root, self.receipt,
        )

    def sign(self):
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(self.signer_private),
             "-out", str(self.signature), str(self.receipt)],
            check=True, capture_output=True,
        )

    def verify(self, **kwargs):
        return verify_signed_sealed_receipt(
            kwargs.get("checkpoint", self.checkpoint),
            self.bundle, self.receipt, self.signature, self.signer_public,
            kwargs.get("host", self.host_id), kwargs.get("pin", self.pin),
            require_admin_key=False,
        )

    def prepare_signed(self):
        self.rehearse()
        self.sign()

    def update_receipt(self, field, value):
        record = json.loads(self.receipt.read_text())
        record[field] = value
        self.receipt.write_text(json.dumps(record, sort_keys=True))
        self.sign()

    def test_end_to_end_authenticated_encrypted_restore_and_signature(self):
        interim = self.rehearse()
        self.assertEqual(interim["restored_file_count"], 1)
        self.assertEqual(interim["ciphertext_bytes"], self.bundle.stat().st_size)
        with self.assertRaises((ValueError, FileNotFoundError)):
            self.verify()
        self.sign()
        accepted = self.verify()
        self.assertTrue(accepted["source_offhost_verified_claim"])
        self.assertFalse(accepted["auto_restore_authorized"])

    def test_replaced_ciphertext_invalidates_signed_receipt(self):
        self.prepare_signed()
        data = bytearray(self.bundle.read_bytes())
        data[-1] ^= 1
        self.bundle.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "SEALED_RECEIPT_CONTENT_MISMATCH"):
            self.verify()

    def test_modified_signature_is_rejected(self):
        self.prepare_signed()
        self.receipt.write_text(self.receipt.read_text() + "attack")
        with self.assertRaisesRegex(ValueError, "SEALED_RECEIPT_SIGNATURE_INVALID"):
            self.verify()

    def test_wrong_offhost_identity_is_rejected(self):
        self.prepare_signed()
        with self.assertRaisesRegex(ValueError, "SEALED_RECEIPT_CONTENT_MISMATCH"):
            self.verify(host="local-factory-vps")

    def test_wrong_receiver_fingerprint_is_rejected(self):
        self.prepare_signed()
        with self.assertRaisesRegex(ValueError, "SEALED_RECEIPT_CONTENT_MISMATCH"):
            self.verify(pin="0" * 64)

    def test_wrong_checkpoint_is_rejected(self):
        self.prepare_signed()
        (self.private / "cycle.json").write_text('{"product":"wrong"}')
        other = self.root / "other-checkpoint"
        snapshot(self.db, self.private, other, 32)
        with self.assertRaisesRegex(ValueError, "SEALED_RECEIPT_CONTENT_MISMATCH"):
            self.verify(checkpoint=other)

    def test_even_signed_auto_restore_permission_is_rejected(self):
        self.prepare_signed()
        self.update_receipt("auto_restore_authorized", True)
        with self.assertRaisesRegex(ValueError, "SEALED_RECEIPT_CONTENT_MISMATCH"):
            self.verify()

    def test_stale_signed_receipt_is_rejected(self):
        self.prepare_signed()
        old = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        self.update_receipt("restore_verified_utc", old)
        with self.assertRaisesRegex(ValueError, "SEALED_RECEIPT_STALE_OR_FUTURE"):
            self.verify()

    def test_receipt_never_overwrites_existing_file(self):
        self.rehearse()
        with self.assertRaisesRegex(ValueError, "SEALED_RECEIPT_ALREADY_EXISTS"):
            self.rehearse()

    def test_untrusted_work_directory_cannot_receive_plaintext(self):
        self.root.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "SEALED_RECEIPT_WORKDIR_NOT_PRIVATE"):
            self.rehearse()
        self.assertFalse(self.receipt.exists())


if __name__ == "__main__":
    unittest.main()
