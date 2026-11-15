"""Regression checks for manifest identity: no real agronomic evidence."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from research.irrigation_synthetic_audit.verify_frozen_manifest import verify

class ManifestBoundaryTests(unittest.TestCase):
    def test_duplicate_top_level_key_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "manifest.json"
            p.write_text('{"schema_version":1,"study":"R01","study":"OTHER","artifacts":[]}')
            self.assertTrue(any("duplicate JSON key" in e for e in verify(p)))

    def test_duplicate_nested_key_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "manifest.json"
            p.write_text('{"schema_version":1,"study":"R01","artifacts":[{"role":"input","role":"output"}]}')
            self.assertTrue(any("duplicate JSON key" in e for e in verify(p)))

    def test_manifest_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "real.json"
            target.write_text('{"schema_version":1,"study":"R01","artifacts":[]}')
            alias = Path(d) / "alias.json"
            alias.symlink_to(target)
            self.assertTrue(verify(alias))

    def test_manifest_directory_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(verify(Path(d)))

    def test_manifest_oversize_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "manifest.json"
            p.write_bytes(b" " * (2 * 1024 * 1024 + 1))
            self.assertTrue(any("size limit" in e for e in verify(p)))

if __name__ == "__main__":
    unittest.main()
