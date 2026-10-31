"""Synthetic checks for the owner-sealed approval CSV transfer."""
import base64
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from scripts import zomorod_approval_envelope_encrypt as encryptor


class TestApprovalEnvelope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        cls.public_pem = cls.private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def test_sealed_envelope_authenticity_and_source_roundtrip(self):
        sample = b"source_id,external_key\n1,ZM-001\n"
        old_size, old_sha = encryptor.EXPECTED_SIZE, encryptor.EXPECTED_SHA
        try:
            encryptor.EXPECTED_SIZE = len(sample)
            encryptor.EXPECTED_SHA = hashlib.sha256(sample).hexdigest()
            encoded = encryptor.envelope(sample, self.public_pem, now=123456)
            doc = json.loads(encoded)
            self.assertEqual(doc["v"], 1)
            self.assertLess(len(encoded), 22000)
            aes_key = self.private.decrypt(
                base64.b64decode(doc["ek"]),
                padding.OAEP(mgf=padding.MGF1(hashes.SHA1()), algorithm=hashes.SHA1(), label=None),
            )
            aad = f"{encryptor.PURPOSE}|{len(sample)}|{encryptor.EXPECTED_SHA}|123456".encode()
            compressed = AESGCM(aes_key).decrypt(
                base64.b64decode(doc["iv"]),
                base64.b64decode(doc["ct"]) + base64.b64decode(doc["tag"]),
                aad,
            )
            self.assertEqual(gzip.decompress(compressed), sample)
            with self.assertRaises(ValueError):
                encryptor.envelope(sample + b"X", self.public_pem, now=123456)
        finally:
            encryptor.EXPECTED_SIZE, encryptor.EXPECTED_SHA = old_size, old_sha

    def test_weak_rsa_blocked(self):
        sample = b"x"
        weak = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = weak.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        old_size, old_sha = encryptor.EXPECTED_SIZE, encryptor.EXPECTED_SHA
        try:
            encryptor.EXPECTED_SIZE = len(sample)
            encryptor.EXPECTED_SHA = hashlib.sha256(sample).hexdigest()
            with self.assertRaisesRegex(ValueError, "RSA 3072"):
                encryptor.envelope(sample, pem)
        finally:
            encryptor.EXPECTED_SIZE, encryptor.EXPECTED_SHA = old_size, old_sha

    @unittest.skipUnless(shutil.which("php"), "PHP is exercised on the Actions runner")
    def test_php_receiver_private_new_only_roundtrip(self):
        sample = b"source_id,external_key\n1,ZM-001\n"
        sample_sha = hashlib.sha256(sample).hexdigest()
        old_size, old_sha = encryptor.EXPECTED_SIZE, encryptor.EXPECTED_SHA
        try:
            encryptor.EXPECTED_SIZE = len(sample)
            encryptor.EXPECTED_SHA = sample_sha
            encoded = encryptor.envelope(sample, self.public_pem, now=int(time.time()))
        finally:
            encryptor.EXPECTED_SIZE, encryptor.EXPECTED_SHA = old_size, old_sha
        with tempfile.TemporaryDirectory() as temp:
            private = Path(temp)
            private.chmod(0o700)
            keyfile = private / ".chat-command-rsa.key"
            keyfile.write_bytes(self.private.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            ))
            keyfile.chmod(0o600)
            sealed = private / "envelope.json"
            sealed.write_bytes(encoded)
            sealed.chmod(0o600)
            receiver_source = Path(__file__).with_name("approval_sealed_receive.php")
            if not receiver_source.exists():
                receiver_source = Path(__file__).resolve().parents[1] / "scripts" / "zomorod_approval_sealed_receive.php"
            receiver = receiver_source.read_text(encoding="utf-8")
            receiver = receiver.replace(
                "$private = '/home/zomorod2/.private/zomorod-business';",
                "$private = " + json.dumps(str(private)) + ";",
            ).replace(
                "$sourceSha = '40c09b1aff17143cf315884177b61a35c6b1d62aa30a445056cfd8303deb3366';",
                "$sourceSha = '" + sample_sha + "';",
            ).replace("$sourceSize = 52072;", "$sourceSize = " + str(len(sample)) + ";")
            self.assertNotIn("/home/zomorod2", receiver)
            script = private / "receiver.php"
            script.write_text(receiver, encoding="utf-8")
            script.chmod(0o600)
            target = private / "zomorod_projects_import_20261031.csv"
            result = subprocess.run(
                ["php", str(script), str(sealed), str(target)],
                text=True, capture_output=True, timeout=8, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.read_bytes(), sample)
            self.assertEqual(target.stat().st_mode & 0o077, 0)
            replay = subprocess.run(
                ["php", str(script), str(sealed), str(target)],
                text=True, capture_output=True, timeout=8, check=False,
            )
            self.assertNotEqual(replay.returncode, 0)
            self.assertIn("DESTINATION_EXISTS", replay.stderr)


if __name__ == "__main__":
    unittest.main()
