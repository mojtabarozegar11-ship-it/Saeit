import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

SOURCE = Path(__file__).resolve().parents[1] / "scripts/mpw_sku879_private_rework_source_20261027.py"
spec = importlib.util.spec_from_file_location("sku879_rework", SOURCE)
rework = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rework)


class WritablePrivateReworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        original = self.root / "copies" / "879"
        original.mkdir(parents=True)
        raw = self.archive({"index.html": "<!doctype html><title>Original product</title>",
                            "assets/site.css": "body{min-width:453px}"})
        self.digest = hashlib.sha256(raw).hexdigest()
        self.original = original / (self.digest + ".bin")
        self.original.write_bytes(raw)

    @staticmethod
    def archive(files):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as package:
            for name, body in files.items():
                package.writestr(name, body)
        return stream.getvalue()

    def prepare(self):
        return rework.prepare(self.root, source_sha=self.digest, min_free_bytes=0)

    def test_prepares_writable_derivative_and_preserves_original(self):
        before = self.original.read_bytes()
        result = self.prepare()
        self.assertEqual(result["status"], "prepared")
        self.assertTrue(result["source_preserved"])
        working = self.root / "quality1000-rework" / "879" / self.digest / "writable-source"
        self.assertEqual((working / "index.html").read_text(),
                         "<!doctype html><title>Original product</title>")
        (working / "index.html").write_text("<title>Reworked privately</title>")
        self.assertEqual(self.original.read_bytes(), before)
        self.assertEqual(self.prepare()["status"], "already_prepared")
        self.assertIn("Original product", self.original.read_bytes().decode("latin1"))
        self.assertFalse(result["commercial_release_allowed"])
        self.assertFalse(result["quality1000_verified"])

    def test_rejects_tampered_original(self):
        self.original.write_bytes(self.original.read_bytes() + b"x")
        with self.assertRaisesRegex(RuntimeError, "REWORK_SOURCE_HASH_MISMATCH"):
            self.prepare()

    def test_rejects_traversal_without_creating_candidate(self):
        raw = self.archive({"index.html": "<title>x</title>",
                            "../escape.txt": "outside"})
        self.original.unlink()
        self.digest = hashlib.sha256(raw).hexdigest()
        self.original = self.root / "copies" / "879" / (self.digest + ".bin")
        self.original.write_bytes(raw)
        with self.assertRaisesRegex(RuntimeError, "REWORK_UNSAFE_ZIP_MEMBER"):
            self.prepare()
        self.assertFalse((self.root / "escape.txt").exists())
        self.assertFalse((self.root / "quality1000-rework" / "879" /
                          self.digest / "writable-source").exists())

    def test_refuses_untrusted_preexisting_target(self):
        working = (self.root / "quality1000-rework" / "879" /
                   self.digest / "writable-source")
        working.mkdir(parents=True)
        (working / "index.html").write_text("Keep this")
        with self.assertRaisesRegex(RuntimeError, "REWORK_EXISTING_TREE_UNTRUSTED"):
            self.prepare()
        self.assertEqual((working / "index.html").read_text(), "Keep this")


if __name__ == "__main__":
    unittest.main()
