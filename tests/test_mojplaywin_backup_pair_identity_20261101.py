"""Synthetic-only explicit backup-pair identity tests; no cPanel/VPS access."""
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from types import SimpleNamespace
from scripts import mojplaywin_backup_stream_cpanel as source_stream

from scripts.mojplaywin_backup_encrypt_vps_gpg import (
    MARKER, backup_set_stem, store,
)
from scripts.mojplaywin_recovery_stream_vps import (
    discover_explicit_pair, explicit_pair_readiness, load, verify_resumable_sql,
    decrypt_to_stdout,
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

    @unittest.skipUnless(shutil.which("gpg"), "Synthetic GPG verification requires gpg")
    def test_resume_only_verified_sql_and_per_kind_size_limits(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            synthetic = b"fake synthetic SQL; no real database rows\\n" * 80 + MARKER
            with patch.dict(os.environ, {"MPW_BACKUP_SET_STEM": PAIR}):
                store(io.BytesIO(synthetic), "mysql", root=base, keyroot=base,
                      minimum_free=0)
                store(io.BytesIO(synthetic), "files", root=base, keyroot=base,
                      minimum_free=0)
            verified = verify_resumable_sql(PAIR, home=base)
            self.assertTrue(verified["source_verified"])
            self.assertEqual(verified["plaintext_bytes"], len(synthetic))
            self.assertFalse(verified["release_permitted"])
            class ClosedPipe:
                def write(self, _payload):
                    raise BrokenPipeError("synthetic downstream close")
                def flush(self):
                    pass
            with self.assertRaises(BrokenPipeError):
                decrypt_to_stdout("mysql", home=base, stem=PAIR, out=ClosedPipe())
            with self.assertRaises(RuntimeError):
                verify_resumable_sql(WRONG, home=base)
            root = base / ".private-mojplaywin-offhost-backups"
            sql_manifest = root / (PAIR + "_mysql_gpgv2.manifest.json")
            metadata = json.loads(sql_manifest.read_text())
            metadata["plaintext_bytes"] = 17_901_542_305
            sql_manifest.write_text(json.dumps(metadata))
            self.assertEqual(load("mysql", home=base, stem=PAIR)[1]
                             ["plaintext_bytes"], 17_901_542_305)
            with self.assertRaises(RuntimeError):
                verify_resumable_sql(PAIR, home=base)  # SHA/size must match decrypted data.
            files_manifest = root / (PAIR + "_files_gpgv2.manifest.json")
            metadata = json.loads(files_manifest.read_text())
            metadata["plaintext_bytes"] = 17_901_542_305
            files_manifest.write_text(json.dumps(metadata))
            with self.assertRaisesRegex(RuntimeError, "manifest incomplete"):
                load("files", home=base, stem=PAIR)

    def test_scoped_tar_nonzero_is_fatal_with_private_safe_reason(self):
        for code, expected in ((1, "SCOPED_TAR_EXIT_WARNING"),
                               (2, "SCOPED_TAR_EXIT_FATAL")):
            with self.subTest(exit_code=code):
                fake = Mock()
                fake.stdout = io.BytesIO(b"synthetic archive data")
                fake.wait.return_value = code
                fake.poll.return_value = code
                sink = SimpleNamespace(buffer=io.BytesIO())
                with patch.object(source_stream.subprocess, "Popen",
                                  return_value=fake), patch.object(
                                      source_stream.sys, "stdout", sink):
                    with self.assertRaisesRegex(RuntimeError, expected):
                        source_stream.copy_exact_process_stdout(
                            ["nice", "-n", "15", "tar", "--dereference"])


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
