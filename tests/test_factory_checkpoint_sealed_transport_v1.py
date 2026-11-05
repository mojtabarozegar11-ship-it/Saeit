"""Local cryptographic negative/round-trip checks; never transfer production data."""

import json
from pathlib import Path
import sqlite3
import struct
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from factory_private_checkpoint_v1 import snapshot, verify  # noqa: E402
from factory_checkpoint_sealed_transport_v1 import (  # noqa: E402
    MAGIC, _fingerprint, _trusted_public_key, seal, unseal,
)


class FactorySealedTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        cls.fingerprint = _fingerprint(cls.key.public_key())

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.database = self.root / "factory.sqlite3"
        with sqlite3.connect(self.database) as db:
            db.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, description TEXT)")
            db.execute("INSERT INTO events VALUES (1, 'PRIVATE_DB_DATA_NEVER_LOG')")
        self.private = self.root / "private"
        self.private.mkdir(mode=0o700)
        (self.private / "state.json").write_text('{"marker":"PRIVATE_STATE_NEVER_LOG"}')
        self.checkpoint = self.root / "checkpoint"
        snapshot(self.database, self.private, self.checkpoint, 32)
        self.public = self.root / "recipient-public.pem"
        self.public.write_bytes(self.key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        self.private_key = self.root / "recipient-private.pem"
        self.private_key.write_bytes(self.key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
        self.private_key.chmod(0o600)
        self.bundle = self.root / "factory.sealed"
        self.restored = self.root / "offhost-restored"

    def make_bundle(self):
        return seal(self.checkpoint, self.public, self.fingerprint, self.bundle,
                    require_admin_key=False)

    def restore(self, **extra):
        return unseal(
            self.bundle, self.private_key, self.fingerprint,
            extra.get("destination", self.restored),
        )

    def test_ciphertext_round_trip_with_pinned_receiver_key(self):
        result = self.make_bundle()
        ciphertext = self.bundle.read_bytes()
        self.assertTrue(ciphertext.startswith(MAGIC))
        self.assertNotIn(b"PRIVATE_STATE_NEVER_LOG", ciphertext)
        self.assertNotIn(b"PRIVATE_DB_DATA_NEVER_LOG", ciphertext)
        self.assertFalse(result["offhost_restore_verified"])
        receipt = self.restore()
        self.assertTrue(receipt["checkpoint_verified"])
        self.assertFalse(receipt["offhost_receipt_signed"])
        self.assertEqual(verify(self.restored)["file_count"], 1)
        self.assertEqual((self.restored / "manifest.json").read_bytes(),
                         (self.checkpoint / "manifest.json").read_bytes())

    def test_tampered_ciphertext_cannot_reach_restored_destination(self):
        self.make_bundle()
        data = bytearray(self.bundle.read_bytes())
        data[-21] ^= 1
        self.bundle.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "SEALED_AUTHENTICATION_FAILED"):
            self.restore()
        self.assertFalse(self.restored.exists())

    def test_tampered_tag_cannot_reach_restored_destination(self):
        self.make_bundle()
        data = bytearray(self.bundle.read_bytes())
        data[-1] ^= 1
        self.bundle.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "SEALED_AUTHENTICATION_FAILED"):
            self.restore()
        self.assertFalse(self.restored.exists())

    def test_wrong_public_key_pin_rejected_before_output(self):
        with self.assertRaisesRegex(ValueError, "SEALED_RECIPIENT_PIN_MISMATCH"):
            seal(self.checkpoint, self.public, "0" * 64, self.bundle,
                 require_admin_key=False)
        self.assertFalse(self.bundle.exists())

    def test_private_key_must_not_be_exposed_to_other_users(self):
        self.make_bundle()
        self.private_key.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "SEALED_PRIVATE_KEY_PERMISSIONS"):
            self.restore()
        self.assertFalse(self.restored.exists())

    def test_output_is_not_overwritten(self):
        self.make_bundle()
        original = self.bundle.read_bytes()
        with self.assertRaisesRegex(ValueError, "SEALED_DESTINATION_EXISTS"):
            self.make_bundle()
        self.assertEqual(self.bundle.read_bytes(), original)

    def test_recovery_is_not_overwritten(self):
        self.make_bundle()
        self.restored.mkdir()
        with self.assertRaisesRegex(ValueError, "SEALED_DESTINATION_EXISTS"):
            self.restore()

    def test_symlink_bundle_rejected_without_plaintext(self):
        self.make_bundle()
        other = self.root / "symlink.sealed"
        other.symlink_to(self.bundle)
        with self.assertRaisesRegex(ValueError, "SEALED_SYMLINK_PATH"):
            unseal(other, self.private_key, self.fingerprint, self.restored)

    def test_world_readable_output_directory_rejected(self):
        self.root.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "SEALED_PARENT_NOT_PRIVATE"):
            self.make_bundle()
        self.assertFalse(self.bundle.exists())

    def test_unknown_magic_rejected(self):
        self.make_bundle()
        data = self.bundle.read_bytes()
        self.bundle.write_bytes(b"BROKEN" + data[6:])
        with self.assertRaisesRegex(ValueError, "SEALED_MAGIC_INVALID"):
            self.restore()
        self.assertFalse(self.restored.exists())

    def test_header_mutation_authentication_fails(self):
        self.make_bundle()
        data = self.bundle.read_bytes()
        offset = len(MAGIC)
        length = struct.unpack(">I", data[offset:offset+4])[0]
        header_start = offset + 4
        header = json.loads(data[header_start:header_start+length])
        # The authenticated pin itself is validated before decryption.
        header["public_key_sha256"] = "0" * 64
        altered = json.dumps(header, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(len(altered), length)
        self.bundle.write_bytes(data[:header_start] + altered + data[header_start+length:])
        with self.assertRaisesRegex(ValueError, "SEALED_RECIPIENT_PIN_MISMATCH"):
            self.restore()

    def test_2048_bit_recipient_key_is_not_accepted(self):
        legacy = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        key_file = self.root / "short-key.pem"
        key_file.write_bytes(legacy.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        with self.assertRaisesRegex(ValueError, "SEALED_RECIPIENT_KEY_UNSUPPORTED"):
            seal(self.checkpoint, key_file, _fingerprint(legacy.public_key()),
                 self.bundle, require_admin_key=False)
        self.assertFalse(self.bundle.exists())

    def test_production_rejects_unprivileged_public_key(self):
        self.public.chmod(0o666)
        with self.assertRaisesRegex(ValueError, "SEALED_PUBLIC_KEY_NOT_ADMIN_PROTECTED"):
            seal(self.checkpoint, self.public, self.fingerprint, self.bundle)
        self.assertFalse(self.bundle.exists())

    def test_receiver_public_key_rejects_untrusted_higher_ancestor(self):
        fake_key = Path("/tmp/outsider/protected/subdir/recipient.pem")
        pem = self.public.read_bytes()
        def fake_stat(path):
            return SimpleNamespace(
                st_uid=1000 if path == Path("/tmp/outsider") else 0,
                st_mode=0o755,
            )
        with patch("factory_checkpoint_sealed_transport_v1._read_pem", return_value=pem):
            with patch.object(Path, "stat", autospec=True, side_effect=fake_stat):
                with self.assertRaisesRegex(ValueError, "SEALED_PUBLIC_KEY_NOT_ADMIN_PROTECTED"):
                    _trusted_public_key(fake_key, self.fingerprint)

    def test_modified_checkpoint_is_rejected_before_encryption(self):
        with (self.checkpoint / "private-state.tar.gz").open("ab") as output:
            output.write(b"unauthorized-change")
        with self.assertRaisesRegex(ValueError, "CHECKPOINT_ARCHIVE_DIGEST_MISMATCH"):
            self.make_bundle()
        self.assertFalse(self.bundle.exists())

    def test_truncated_ciphertext_cannot_be_restored(self):
        self.make_bundle()
        self.bundle.write_bytes(self.bundle.read_bytes()[:-5])
        with self.assertRaisesRegex(ValueError, "SEALED_AUTHENTICATION_FAILED"):
            self.restore()
        self.assertFalse(self.restored.exists())


if __name__ == "__main__":
    unittest.main()

