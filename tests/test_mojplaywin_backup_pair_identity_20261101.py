"""Synthetic-only explicit backup-pair identity tests; no cPanel/VPS access."""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.mojplaywin_backup_encrypt_vps_gpg import (
    MARKER, backup_set_stem, store,
)
from scripts.mojplaywin_recovery_stream_vps import (
    discover_explicit_pair, explicit_pair_readiness,
)

PAIR = "mojplaywin_20261101T120000Z_0123456789abcdef"
RECOVERY_CLI = Path(__file__).resolve().parents[1] / "scripts" / "mojplaywin_recovery_stream_vps.py"
WRONG = "mojplaywin_20261101T120000Z_1111111111111111"


class ExplicitPairIdentityTests(unittest.TestCase):
    def test_rejects_unscoped_and_historical_pair_ids(self):
        for value in ("../other", "mojplaywin_20261017",
                      "mojplaywin_20261021T120000Z_bad",
                      "mojplaywin_20261101T120000Z_0123456789ABCDEF"):
            with self.subTest(value=value):
                with patch.dict(os.environ, {"MPW_BACKUP_SET_STEM": value}):
                    with self.assertRaises(RuntimeError):
                        backup_set_stem()
                with self.assertRaises(RuntimeError):
                    discover_explicit_pair(value)

    def test_missing_new_pair_does_not_use_old_archives(self):
        with tempfile.TemporaryDirectory() as td:
            report = explicit_pair_readiness(PAIR, home=Path(td))
            self.assertFalse(report["both_manifests_selectable"])
            self.assertFalse(report["gpg_stream_reverified"])
            self.assertFalse(report["isolated_restore_performed"])
            self.assertFalse(report["release_permitted"])

    @unittest.skipUnless(shutil.which("gpg"), "Synthetic GPG v2 pair test requires gpg")
    def test_both_streams_share_exact_identity_and_no_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            synthetic = b"non-customer synthetic fixture\n" * 90 + MARKER
            with patch.dict(os.environ, {"MPW_BACKUP_SET_STEM": PAIR}):
                store(io.BytesIO(synthetic), "mysql", root=base, keyroot=base,
                      minimum_free=0)
                with self.assertRaises(RuntimeError):
                    discover_explicit_pair(PAIR, home=base)  # One kind is insufficient.
                store(io.BytesIO(synthetic), "files", root=base, keyroot=base,
                      minimum_free=0)
            self.assertEqual(discover_explicit_pair(PAIR, home=base),
                             {"mysql": PAIR, "files": PAIR})
            self.assertTrue(explicit_pair_readiness(PAIR, home=base)
                            ["both_manifests_selectable"])
            self.assertFalse(explicit_pair_readiness(WRONG, home=base)
                             ["both_manifests_selectable"])

            root = base / ".private-mojplaywin-offhost-backups"
            files_manifest = root / (PAIR + "_files_gpgv2.manifest.json")
            metadata = json.loads(files_manifest.read_text())
            metadata["backup_set_stem"] = WRONG
            files_manifest.write_text(json.dumps(metadata))
            with self.assertRaises(RuntimeError):
                discover_explicit_pair(PAIR, home=base)

    @unittest.skipUnless(shutil.which("gpg"), "Synthetic GPG CLI test requires gpg")
    def test_full_cli_gpg_pair_round_trip_rejects_old_and_wrong_selection(self):
        """Actual CLI decrypt of both synthetic streams, no live backup data."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            payload = b"synthetic-only encrypted SQL-or-files bytes\n" * 40 + MARKER
            with patch.dict(os.environ, {"MPW_BACKUP_SET_STEM": PAIR}):
                for kind in ("mysql", "files"):
                    store(io.BytesIO(payload), kind, root=base, keyroot=base,
                          minimum_free=0)

            def invoke(mode, stem=PAIR):
                env = dict(os.environ, HOME=str(base))
                return subprocess.run(
                    [sys.executable, "-B", str(RECOVERY_CLI), mode, stem],
                    env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=30, check=False,
                )

            ready = invoke("check-pair")
            self.assertEqual(ready.returncode, 0)
            status = json.loads(ready.stdout)
            self.assertTrue(status["both_manifests_selectable"])
            self.assertFalse(status["gpg_stream_reverified"])
            self.assertFalse(status["isolated_restore_performed"])
            self.assertFalse(status["release_permitted"])

            for kind in ("mysql", "files"):
                with self.subTest(kind=kind):
                    result = invoke(kind + "-pair")
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, payload)
                    self.assertIn(b"PRIVATE_STREAM_VERIFIED", result.stderr)

            wrong = invoke("mysql-pair", WRONG)
            self.assertNotEqual(wrong.returncode, 0)
            self.assertEqual(wrong.stdout, b"")
            self.assertIn(b"PRIVATE_RESTORE_STREAM_INTEGRITY_FAILURE", wrong.stderr)
            self.assertNotIn(b"synthetic-only", wrong.stderr)

            historical = subprocess.run(
                [sys.executable, "-B", str(RECOVERY_CLI), "check"],
                env=dict(os.environ, HOME=str(base)),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=30, check=False,
            )
            self.assertNotEqual(historical.returncode, 0)
            self.assertFalse(json.loads(historical.stdout)["both_primary_archives_complete"])

            files = base / ".private-mojplaywin-offhost-backups"
            damaged = files / (PAIR + "_files_gpgv2.gpg")
            raw = bytearray(damaged.read_bytes())
            raw[len(raw) // 2] ^= 1
            damaged.write_bytes(raw)
            bad = invoke("files-pair")
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn(b"PRIVATE_RESTORE_STREAM_INTEGRITY_FAILURE", bad.stderr)

    def test_invalid_identity_errors_never_echo_value_to_summary(self):
        with tempfile.TemporaryDirectory() as td:
            report = explicit_pair_readiness("../../private/customer/secret",
                                             home=Path(td))
            self.assertEqual(report["classification"],
                             "EXPLICIT_BACKUP_PAIR_MANIFEST_READINESS")
            self.assertNotIn("private", json.dumps(report))
            self.assertFalse(report["release_permitted"])


if __name__ == "__main__":
    unittest.main()
