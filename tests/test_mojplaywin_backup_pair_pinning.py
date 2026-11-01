"""Synthetic pair-pinning tests; no hosts, production databases or user files."""
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.mojplaywin_backup_encrypt_vps_gpg import MARKER, store
from scripts.mojplaywin_recovery_stream_vps import (
    decrypt_to_stdout, readiness,
)


@unittest.skipUnless(shutil.which("gpg"), "Dedicated backup runner requires GPG")
class PinnedIndependentPairTests(unittest.TestCase):
    def test_explicit_fresh_pair_requires_both_and_verifies_ciphertext(self):
        stem = "mojplaywin_20261101T120000Z_aabbccddeeff0011"
        payloads = {
            "mysql": b"-- synthetic SQL\nSELECT 1;\n" * 150 + MARKER,
            "files": b"synthetic tar-shaped private bytes\n" * 100 + MARKER,
        }
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            self.assertFalse(readiness(home, stem)["both_primary_archives_complete"])
            for kind in ("mysql", "files"):
                report = store(io.BytesIO(payloads[kind]), kind, root=home,
                               keyroot=home, minimum_free=0, stem=stem)
                self.assertTrue(report["decryption_verified"])
                manifest = home / ".private-mojplaywin-offhost-backups" / (
                    stem + "_" + kind + "_gpgv2.manifest.json")
                self.assertEqual(json.loads(manifest.read_text())["pair_stem"], stem)
                if kind == "mysql":
                    self.assertFalse(readiness(home, stem)["both_primary_archives_complete"])
            self.assertTrue(readiness(home, stem)["both_primary_archives_complete"])
            self.assertFalse(readiness(home, stem)["release_permitted"])
            self.assertFalse(readiness(
                home, "mojplaywin_20261101T120001Z_aabbccddeeff0011"
            )["both_primary_archives_complete"])
            for kind, expected in payloads.items():
                out = io.BytesIO()
                self.assertEqual(
                    decrypt_to_stdout(kind, home=home, out=out, stem=stem), len(expected))
                self.assertEqual(out.getvalue(), expected)
            with self.assertRaises(RuntimeError):
                store(io.BytesIO(payloads["mysql"]), "mysql", root=home,
                      keyroot=home, minimum_free=0, stem=stem)
            # A mismatched pair marker cannot qualify even with valid encryption.
            mismatched = home / ".private-mojplaywin-offhost-backups" / (
                stem + "_files_gpgv2.manifest.json")
            data = json.loads(mismatched.read_text())
            data["pair_stem"] = "mojplaywin_20261101T120001Z_aabbccddeeff0011"
            mismatched.write_text(json.dumps(data))
            self.assertFalse(readiness(home, stem)["both_primary_archives_complete"])

    def test_reject_invalid_and_legacy_explicit_stems(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            payload = b"safe synthetic\n" * 100 + MARKER
            for stem in ("../escape", "mojplaywin_20261017",
                         "mojplaywin_20261101T120000Z_AABBCCDD00112233",
                         "mojplaywin_20261101T120000Z_0011223344556677/next",
                         ""):
                with self.subTest(stem=stem):
                    with self.assertRaises(RuntimeError):
                        store(io.BytesIO(payload), "mysql", root=home,
                              keyroot=home, minimum_free=0, stem=stem)
                    self.assertFalse(
                        readiness(home, stem)["both_primary_archives_complete"])
            self.assertFalse(
                (home / ".private-mojplaywin-offhost-backups").exists())


if __name__ == "__main__":
    unittest.main()
