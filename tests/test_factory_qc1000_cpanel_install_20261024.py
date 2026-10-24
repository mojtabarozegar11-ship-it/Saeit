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
            publisher = ('def verify_sources(inbox, docroot):\n'
                         '    body = release.read_text(encoding="utf-8")\n'
                         '    return body\n')
            (dest / mod.PUBLISHER).write_text(publisher)
            mod.LIVE_PUBLISHER_SHA = hashlib.sha256(publisher.encode()).hexdigest()
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
            self.assertIn("quality.require_quality_clearance", (dest / mod.PUBLISHER).read_text())
            original_publisher_backup = (dest / ".qc1000-versioned-backups" /
                       hashlib.sha256(publisher.encode()).hexdigest() / mod.PUBLISHER)
            self.assertEqual(original_publisher_backup.read_text(), publisher)
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
            publisher = ('def verify_sources(inbox, docroot):\n'
                         '    body = release.read_text(encoding="utf-8")\n'
                         '    return body\n')
            (dest / mod.PUBLISHER).write_text(publisher)
            mod.LIVE_PUBLISHER_SHA = hashlib.sha256(publisher.encode()).hexdigest()
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
