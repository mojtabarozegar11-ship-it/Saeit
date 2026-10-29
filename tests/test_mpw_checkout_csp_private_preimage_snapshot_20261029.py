"""Offline no-production-write regression for S-01 private checkout preimage."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "mpw_checkout_csp_private_preimage_snapshot_20261029.py"
spec = importlib.util.spec_from_file_location("s01_preimage", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class PrivatePreimageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "Saeit-staging/mpw_commerce").mkdir(parents=True)
        (self.root / "mojplaywin.com").mkdir()
        (self.root / ".private_mojplaywin_main_agents").mkdir(mode=0o700)
        self.source = self.root / "Saeit-staging/mpw_commerce/product_checkout_page.py"
        self.data = b"synthetic checkout source - no private data\n"
        self.source.write_bytes(self.data)
        (self.root / "mojplaywin.com/passenger_wsgi.py").write_text(mod.WSGI_MARKER)
        self.expected = hashlib.sha256(self.data).hexdigest()
        self.patches = [
            patch.object(mod, "EXPECTED_SHA256", self.expected),
            patch.object(mod, "STEM", "mpw-checkout-csp-preimage-" + self.expected[:16]),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.owner = pwd.getpwuid(os.getuid()).pw_name

    def run_snapshot(self):
        return mod.snapshot(self.root, self.owner)

    def paths(self):
        directory = self.root / ".private_mojplaywin_main_agents"
        return directory / (mod.STEM + ".bak"), directory / (mod.STEM + ".json")

    def test_creates_exact_private_copy_and_readback(self):
        result = self.run_snapshot()
        backup, manifest = self.paths()
        self.assertEqual(result["result"], "CREATED_AND_VERIFIED")
        self.assertEqual(backup.read_bytes(), self.data)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual(manifest.stat().st_mode & 0o777, 0o600)
        self.assertFalse(json.loads(manifest.read_text())["release_permitted"])
        self.assertFalse(result["offhost_restore_verified"])
        self.assertFalse(result["app_source_modified"])

    def test_idempotent_does_not_overwrite_preimage(self):
        self.run_snapshot()
        backup, _ = self.paths()
        before = backup.stat().st_mtime_ns
        self.assertEqual(self.run_snapshot()["result"], "EXISTING_VERIFIED")
        self.assertEqual(backup.stat().st_mtime_ns, before)

    def test_rejects_drift_without_creating_backup(self):
        self.source.write_bytes(b"changed source")
        with self.assertRaisesRegex(RuntimeError, "SHA drift"):
            self.run_snapshot()
        self.assertFalse(self.paths()[0].exists())

    def test_partial_snapshot_fails_closed_without_overwrite(self):
        backup, _ = self.paths()
        backup.write_bytes(b"partial")
        with self.assertRaises((OSError, RuntimeError)):
            self.run_snapshot()
        self.assertEqual(backup.read_bytes(), b"partial")

    def test_rejects_symlink_backup_directory(self):
        directory = self.root / ".private_mojplaywin_main_agents"
        directory.rmdir()
        directory.symlink_to(self.root / "mojplaywin.com", target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "private backup directory"):
            self.run_snapshot()

    def test_rejects_tampered_manifest(self):
        self.run_snapshot()
        _, manifest = self.paths()
        manifest.write_text("{}")
        with self.assertRaisesRegex(RuntimeError, "manifest mismatch"):
            self.run_snapshot()



class SafeBlockedSnapshotDiagnosticsTests(unittest.TestCase):
    def test_known_blocker_is_specific_but_private(self):
        self.assertEqual(
            mod.safe_failure_code(RuntimeError("checkout preimage SHA drift")),
            "SOURCE_SHA_DRIFT",
        )
        self.assertEqual(
            mod.safe_failure_code(RuntimeError("snapshot manifest mismatch")),
            "EXISTING_MANIFEST_MISMATCH",
        )
        self.assertEqual(mod.safe_failure_code(BlockingIOError()), "LOCK_BUSY")

    def test_untrusted_exception_text_is_never_returned(self):
        secret = "private customer record"
        self.assertEqual(
            mod.safe_failure_code(RuntimeError(secret)), "RUNTIME_GUARD_BLOCKED"
        )
        self.assertNotIn(secret, mod.safe_failure_code(OSError(secret)))



if __name__ == "__main__":
    unittest.main()
