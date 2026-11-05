"""Synthetic-only, no-network admission-floor tests for private SQL restoration."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.mojplaywin_recovery_stream_vps import (
    estimate_restore_budget, inspect_vps_restore_capacity,
)


STEM = "mojplaywin_20261102T090223Z_3c23e70544115e95"
SQL_BYTES = 17_901_542_305
FILES_BYTES = 533_944_368
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "mojplaywin_recovery_stream_vps.py"


def synthetic_pair(home, sql_size=SQL_BYTES, files_size=FILES_BYTES):
    """Build private metadata and fake ciphertext, never real SQL or credentials."""
    root = home / ".private-mojplaywin-offhost-backups"
    gpg_home = home / ".config" / "mojplaywin-backup-recovery" / "gnupg-v2"
    root.mkdir(parents=True, mode=0o700)
    gpg_home.mkdir(parents=True, mode=0o700)
    key = gpg_home.parent / "recovery-key.bin"
    key.write_bytes(b"synthetic-unit-test-key-material!"[:32])
    key.chmod(0o600)
    for kind, size in (("mysql", sql_size), ("files", files_size)):
        name = "{}_{}_gpgv2.gpg".format(STEM, kind)
        ciphertext = root / name
        ciphertext.write_bytes(b"SYNTHETIC_NOT_REAL_CIPHERTEXT")
        ciphertext.chmod(0o600)
        meta = {
            "kind": kind,
            "archive_name": name,
            "format": "OpenPGP-AES256-GPGv2",
            "ciphertext_roundtrip_integrity_verified": True,
            "source_completion_footer_verified": True,
            "encrypted_bytes": ciphertext.stat().st_size,
            "plaintext_sha256": "a" * 64,
            "plaintext_bytes": size,
            "backup_set_stem": STEM,
            "explicit_backup_set_id": True,
            "release_permitted": False,
        }
        manifest = root / ("{}_{}_gpgv2.manifest.json".format(STEM, kind))
        manifest.write_text(json.dumps(meta), encoding="ascii")
        manifest.chmod(0o600)
    return root


class RestoreBudgetTests(unittest.TestCase):
    def test_observed_backup_requires_40_gib_without_decrypt(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            synthetic_pair(home)
            with patch("scripts.mojplaywin_recovery_stream_vps.subprocess.Popen") as gpg:
                result = estimate_restore_budget(STEM, home=home)
                gpg.assert_not_called()
            self.assertEqual(result["required_free_gib"], 40)
            self.assertEqual(result["mysql_plaintext_gib_ceiling"], 17)
            self.assertEqual(result["files_plaintext_gib_ceiling"], 1)
            self.assertFalse(result["budget_is_sufficiency_proof"])
            self.assertFalse(result["gpg_stream_reverified"])
            self.assertFalse(result["isolated_restore_performed"])
            self.assertFalse(result["release_permitted"])

    def test_budget_uses_sql_and_files_upper_bounds(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            synthetic_pair(home, sql_size=1024, files_size=12 * 1024 ** 3)
            self.assertEqual(estimate_restore_budget(STEM, home)["required_free_gib"], 30)
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            synthetic_pair(home, sql_size=48 * 1024 ** 3, files_size=1024)
            self.assertEqual(estimate_restore_budget(STEM, home)["required_free_gib"], 102)

    def test_pair_mismatch_and_missing_manifest_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            root = synthetic_pair(home)
            manifest = root / (STEM + "_files_gpgv2.manifest.json")
            metadata = json.loads(manifest.read_text(encoding="ascii"))
            metadata["release_permitted"] = True
            manifest.write_text(json.dumps(metadata), encoding="ascii")
            with self.assertRaises(RuntimeError):
                estimate_restore_budget(STEM, home)

    def test_readonly_vps_probe_rejects_small_filesystem_and_unproven_runtime(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            synthetic_pair(home)
            low_space = SimpleNamespace(f_bavail=20 * 1024 ** 3, f_frsize=1)
            with patch("scripts.mojplaywin_recovery_stream_vps.os.statvfs",
                       return_value=low_space), patch(
                       "scripts.mojplaywin_recovery_stream_vps.subprocess.Popen") as run:
                result = inspect_vps_restore_capacity(STEM, home)
                run.assert_not_called()
            self.assertEqual(result["vps_free_gib_floor"], 20)
            self.assertEqual(result["required_free_gib"], 40)
            self.assertFalse(result["capacity_admission_passed"])
            self.assertFalse(result["runtime_operability_proven"])
            self.assertFalse(result["isolated_restore_performed"])
            self.assertFalse(result["release_permitted"])

    def test_readonly_vps_probe_reports_headroom_without_certifying_restore(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            synthetic_pair(home)
            headroom = SimpleNamespace(f_bavail=60 * 1024 ** 3, f_frsize=1)
            with patch("scripts.mojplaywin_recovery_stream_vps.os.statvfs",
                       return_value=headroom):
                result = inspect_vps_restore_capacity(STEM, home)
            self.assertTrue(result["capacity_admission_passed"])
            self.assertEqual(result["vps_free_gib_floor"], 60)
            self.assertFalse(result["runtime_operability_proven"])
            self.assertFalse(result["isolated_restore_performed"])

    def test_unavailable_vps_probe_is_fixed_fail_closed_no_private_paths(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            synthetic_pair(home)
            env = dict(os.environ, HOME=td, PYTHONDONTWRITEBYTECODE="1")
            ok = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "inspect-vps-pair", STEM],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=10, check=False)
            self.assertEqual(ok.returncode, 0, ok.stderr.decode())
            self.assertFalse(json.loads(ok.stdout)["release_permitted"])
            # Reject corrupt pair metadata before reporting capacity.
            manifest = home / ".private-mojplaywin-offhost-backups" / (
                STEM + "_mysql_gpgv2.manifest.json")
            manifest.write_text("INVALID_PRIVATE_METADATA", encoding="ascii")
            bad = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "inspect-vps-pair", STEM],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=10, check=False)
            self.assertEqual(bad.returncode, 1)
            self.assertEqual(bad.stdout, b"")
            self.assertEqual(bad.stderr.strip(), b"VPS_RESTORE_CAPACITY_UNAVAILABLE_NO_RELEASE")
            manifest.unlink()
            with self.assertRaises(RuntimeError):
                estimate_restore_budget(STEM, home)

    def test_cli_only_emits_sanitized_budget_or_fixed_failure(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            root = synthetic_pair(home)
            env = dict(os.environ, HOME=td, PYTHONDONTWRITEBYTECODE="1")
            success = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "estimate-pair", STEM],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=10, check=False)
            self.assertEqual(success.returncode, 0, success.stderr.decode())
            self.assertEqual(json.loads(success.stdout)["required_free_gib"], 40)
            self.assertEqual(success.stderr, b"")
            manifest = root / (STEM + "_mysql_gpgv2.manifest.json")
            manifest.write_text("{private-invalid-json", encoding="ascii")
            failure = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "estimate-pair", STEM],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=10, check=False)
            self.assertEqual(failure.returncode, 1)
            self.assertEqual(failure.stdout, b"")
            self.assertEqual(failure.stderr.strip(), b"RESTORE_BUDGET_UNAVAILABLE_NO_RELEASE")


if __name__ == "__main__":
    unittest.main()
