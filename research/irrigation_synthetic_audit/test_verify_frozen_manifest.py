"""Twenty independent integrity regressions; no simulated data represented as field observations."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from research.irrigation_synthetic_audit.verify_frozen_manifest import verify

class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.entries = []
        for role in ("input", "generator", "config", "output"):
            name = role + ".txt"
            raw = role.encode()
            (self.root / name).write_bytes(raw)
            self.entries.append(dict(role=role, path=name, bytes=len(raw),
                                     sha256=hashlib.sha256(raw).hexdigest()))
        self.data = dict(schema_version=1, study="R01", artifacts=self.entries)
    def runcheck(self):
        p = self.root / "manifest.json"
        p.write_text(json.dumps(self.data))
        return verify(p)
    def assertBlocked(self):
        self.assertTrue(self.runcheck())
    def test_01_valid(self): self.assertEqual(self.runcheck(), [])
    def test_02_schema(self): self.data["schema_version"]=2; self.assertBlocked()
    def test_03_study(self): self.data["study"]="R02"; self.assertBlocked()
    def test_04_root(self): self.data=[]; self.assertBlocked()
    def test_05_artifacts_type(self): self.data["artifacts"]={}; self.assertBlocked()
    def test_06_empty(self): self.data["artifacts"]=[]; self.assertBlocked()
    def test_07_item_type(self): self.entries[0]=None; self.assertBlocked()
    def test_08_role(self): self.entries[0]["role"]="field"; self.assertBlocked()
    def test_09_missing_input(self): self.entries.pop(0); self.assertBlocked()
    def test_10_missing_generator(self): self.entries.pop(1); self.assertBlocked()
    def test_11_missing_config(self): self.entries.pop(2); self.assertBlocked()
    def test_12_missing_output(self): self.entries.pop(3); self.assertBlocked()
    def test_13_missing_path(self): self.entries[0]["path"]=""; self.assertBlocked()
    def test_14_absolute_path(self): self.entries[0]["path"]="/tmp/a"; self.assertBlocked()
    def test_15_traversal(self): self.entries[0]["path"]="../secret"; self.assertBlocked()
    def test_16_duplicate(self): self.entries[1]["path"]=self.entries[0]["path"]; self.assertBlocked()
    def test_17_missing_file(self): self.entries[0]["path"]="absent"; self.assertBlocked()
    def test_18_wrong_bytes(self): self.entries[0]["bytes"]=999; self.assertBlocked()
    def test_19_wrong_hash(self): self.entries[0]["sha256"]="0"*64; self.assertBlocked()
    def test_20_invalid_hash(self): self.entries[0]["sha256"]="xyz"; self.assertBlocked()

    def test_21_missing_required_role_due_to_bad_hash(self):
        self.entries[0]["sha256"] = "0" * 64
        errors = self.runcheck()
        self.assertTrue(any("missing input role" in e for e in errors))

    def test_22_missing_required_role_due_to_wrong_size(self):
        self.entries[1]["bytes"] += 1
        errors = self.runcheck()
        self.assertTrue(any("missing generator role" in e for e in errors))

    def test_23_missing_required_role_due_to_absent_file(self):
        (self.root / "config.txt").unlink()
        errors = self.runcheck()
        self.assertTrue(any("missing config role" in e for e in errors))

    def test_24_optional_role_does_not_replace_required_role(self):
        self.entries[3]["role"] = "analysis"
        errors = self.runcheck()
        self.assertTrue(any("missing output role" in e for e in errors))

if __name__ == "__main__":
    unittest.main()
