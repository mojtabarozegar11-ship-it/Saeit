#!/usr/bin/env python3
"""Offline regression checks for G-01's independent S-01 static release helper."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("g01_s01_release_static_asset_gate_r45.py")
spec = importlib.util.spec_from_file_location("g01_static_gate_r45", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class StaticGateTests(unittest.TestCase):
    def test_local_asset_and_query_pass(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "ok.js").write_text("console.log(1)")
            (root / "index.html").write_text('<script src="ok.js?v=1"></script>')
            checked, errors = gate.audit(root)
            self.assertEqual(checked, ["ok.js"])
            self.assertEqual(errors, [])

    def test_double_encoded_path_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "index.html").write_text('<script src="%252e%252e/secret.js"></script>')
            _, errors = gate.audit(root)
            self.assertTrue(errors)

    def test_symlink_parent_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "real").mkdir()
            (root / "real" / "ok.js").write_text("console.log(1)")
            try:
                (root / "alias").symlink_to(root / "real", target_is_directory=True)
            except OSError:
                self.skipTest("symlinks unavailable")
            (root / "index.html").write_text('<script src="alias/ok.js"></script>')
            _, errors = gate.audit(root)
            self.assertTrue(errors)

    def test_parent_escape_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "index.html").write_text('<script src="../secret.js"></script>')
            _, errors = gate.audit(root)
            self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
