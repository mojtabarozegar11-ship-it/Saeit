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
    def test_retired_numeric_installer_refuses_and_preserves_existing_files(self):
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
            with self.assertRaisesRegex(RuntimeError,"RETIRED_NUMERIC_QC_INSTALLER"):
                mod.install(staged, expected)
            self.assertEqual((dest / mod.FILES[0]).read_bytes(), old)
            self.assertEqual((dest / mod.PUBLISHER).read_text(), publisher)
            self.assertFalse((dest / ".qc1000-versioned-backups").exists())

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
            with self.assertRaisesRegex(RuntimeError, "RETIRED_NUMERIC_QC_INSTALLER"):
                mod.install(staged, expected)
            self.assertFalse((dest / mod.FILES[0]).exists())

if __name__ == "__main__":
    unittest.main()
