#!/usr/bin/env python3
"""Only isolated fake packages: test installer without touching live store."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
INSTALL = REPO / "deploy/install_factory_qc1000_cpanel_private_20261024.py"


def imported():
    spec = importlib.util.spec_from_file_location("qc1000_install", INSTALL)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


class ScopedPrivateQC1000Install(unittest.TestCase):
    def test_install_guard_and_preserve_existing_source_with_backups(self):
        mod = imported()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            dest, staged = base / "bin", base / "stage"
            dest.mkdir()
            staged.mkdir()
            (dest / mod.PUBLISHER).write_text(
                "quality.require_quality_clearance(...) "
                "factory_commercial_quality_release_guard_v1.py")
            old = b"print('older guard')\n"
            (dest / mod.FILES[0]).write_bytes(old)
            expected = {}
            for name in mod.FILES:
                raw = (REPO / "scripts" / name).read_bytes()
                (staged / name).write_bytes(raw)
                expected[name] = hashlib.sha256(raw).hexdigest()
            mod.TARGET = dest
            mod.install(staged, expected)
            for name in mod.FILES:
                self.assertEqual(
                    hashlib.sha256((dest / name).read_bytes()).hexdigest(),
                    expected[name])
            backup = (dest / ".qc1000-versioned-backups" /
                      hashlib.sha256(old).hexdigest() / mod.FILES[0])
            self.assertEqual(backup.read_bytes(), old)
            self.assertIn("require_quality_clearance",
                          (dest / mod.PUBLISHER).read_text())
            # Idempotent re-execution must preserve exact bytes.
            mod.install(staged, expected)
            self.assertEqual(backup.read_bytes(), old)

    def test_wrong_upload_hash_refuses_before_install(self):
        mod = imported()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            dest, staged = base / "bin", base / "stage"
            dest.mkdir()
            staged.mkdir()
            (dest / mod.PUBLISHER).write_text(
                "require_quality_clearance factory_commercial_quality_release_guard_v1.py")
            expected = {}
            for name in mod.FILES:
                raw = (REPO / "scripts" / name).read_bytes()
                (staged / name).write_bytes(raw)
                expected[name] = hashlib.sha256(raw).hexdigest()
            expected[mod.FILES[0]] = "a" * 64
            mod.TARGET = dest
            with self.assertRaisesRegex(RuntimeError, "UPLOAD_HASH_MISMATCH"):
                mod.install(staged, expected)
            self.assertFalse((dest / mod.FILES[0]).exists())

if __name__ == "__main__":
    unittest.main()
