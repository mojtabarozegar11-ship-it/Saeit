"""R01 path and provenance integrity regression suite; synthetic fixtures only."""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from research.irrigation_synthetic_audit.verify_frozen_manifest import verify

class FrozenManifestSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.artifacts = []
        for role in ("input", "generator", "config", "output"):
            name = role + ".txt"
            data = role.encode()
            (self.root / name).write_bytes(data)
            self.artifacts.append(dict(role=role, path=name, bytes=len(data),
                                       sha256=hashlib.sha256(data).hexdigest()))
        self.manifest = self.root / "manifest.json"
        self.save()

    def save(self):
        self.manifest.write_text(json.dumps(dict(schema_version=1, study="R01",
                                                  artifacts=self.artifacts)))

    def failures(self):
        self.save()
        return verify(self.manifest)

    def test_01_valid_fixture(self): self.assertEqual(self.failures(), [])
    def test_02_missing_input(self):
        self.artifacts.pop(0); self.assertTrue(self.failures())
    def test_03_missing_generator(self):
        self.artifacts.pop(1); self.assertTrue(self.failures())
    def test_04_missing_config(self):
        self.artifacts.pop(2); self.assertTrue(self.failures())
    def test_05_missing_output(self):
        self.artifacts.pop(3); self.assertTrue(self.failures())
    def test_06_bad_study(self):
        self.save(); data=json.loads(self.manifest.read_text()); data["study"]="R02"
        self.manifest.write_text(json.dumps(data)); self.assertTrue(verify(self.manifest))
    def test_07_bad_version(self):
        self.save(); data=json.loads(self.manifest.read_text()); data["schema_version"]=True
        self.manifest.write_text(json.dumps(data)); self.assertTrue(verify(self.manifest))
    def test_08_wrong_hash(self):
        self.artifacts[0]["sha256"]="0"*64; self.assertTrue(self.failures())
    def test_09_wrong_size(self):
        self.artifacts[0]["bytes"]+=1; self.assertTrue(self.failures())
    def test_10_negative_size(self):
        self.artifacts[0]["bytes"]=-1; self.assertTrue(self.failures())
    def test_11_boolean_size(self):
        self.artifacts[0]["bytes"]=True; self.assertTrue(self.failures())
    def test_12_absolute_path(self):
        self.artifacts[0]["path"]="/tmp/file"; self.assertTrue(self.failures())
    def test_13_parent_traversal(self):
        self.artifacts[0]["path"]="../file"; self.assertTrue(self.failures())
    def test_14_dot_segment(self):
        self.artifacts[0]["path"]="./input.txt"; self.assertTrue(self.failures())
    def test_15_empty_segment(self):
        self.artifacts[0]["path"]="a//b"; self.assertTrue(self.failures())
    def test_16_backslash(self):
        self.artifacts[0]["path"]="a\\b"; self.assertTrue(self.failures())
    def test_17_duplicate_path(self):
        self.artifacts[1]["path"]=self.artifacts[0]["path"]; self.assertTrue(self.failures())
    def test_18_leaf_symlink(self):
        (self.root/"input.txt").unlink(); (self.root/"input.txt").symlink_to("output.txt")
        self.assertTrue(self.failures())
    def test_19_nested_symlink(self):
        (self.root/"outside").mkdir(); (self.root/"outside"/"input.txt").write_text("input")
        (self.root/"alias").symlink_to(self.root/"outside", target_is_directory=True)
        self.artifacts[0]["path"]="alias/input.txt"; self.assertTrue(self.failures())
    def test_20_fifo_rejected(self):
        if not hasattr(os, "mkfifo"): self.skipTest("POSIX only")
        (self.root/"input.txt").unlink(); os.mkfifo(self.root/"input.txt")
        self.assertTrue(self.failures())

if __name__ == "__main__":
    unittest.main()
