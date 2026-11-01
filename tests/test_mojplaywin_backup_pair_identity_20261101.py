"""Synthetic-only explicit backup-pair identity tests; no cPanel/VPS access."""
import io
import json
import os
import shutil
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
