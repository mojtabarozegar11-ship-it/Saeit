"""Safety checks for scoped live marker drift repair; no production access."""
from pathlib import Path
import tempfile
import unittest

from scripts.mpw_measure_static_integrity import PAGES, MARKER, plan, repair, inspect_page


class ScopedStaticIntegrityTests(unittest.TestCase):
    def fixture(self, root, missing=("moj-prop/index.html",)):
        for relative in PAGES:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if relative in missing:
                target.write_text("<html><body>fresh live content</body></html>")
            else:
                target.write_text("<html><body>existing live content\n" + MARKER + "</body></html>")
        folder = root / "mpw-measure"
        folder.mkdir()
        (folder / "tracker.js").write_text("/* existing */")

    def test_preflight_never_mutates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "web"; root.mkdir()
            self.fixture(root)
            state = plan(root)
            self.assertEqual(state["moj-prop/index.html"]["status"], "missing")
            self.assertEqual(sum(x["status"] == "present" for x in state.values()), 7)
            self.assertNotIn(MARKER, (root / "moj-prop/index.html").read_text())

    def test_backup_and_repair_only_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "web";root.mkdir()
            self.fixture(root)
            other = root / "store/index.html"
            original = other.read_bytes()
            state = plan(root)
            result = repair(root, Path(tmp) / "backup", state)
            self.assertEqual(result["changed"], ["moj-prop/index.html"])
            self.assertEqual(other.read_bytes(), original)
            self.assertIn(MARKER, (root / "moj-prop/index.html").read_text())
            backup = Path(result["backup"]) / "moj-prop/index.html"
            self.assertEqual(backup.read_text(), "<html><body>fresh live content</body></html>")
            self.assertEqual(repair(root, Path(tmp) / "backup", plan(root))["status"], "already_healthy")

    def test_changed_since_inspection_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "web";root.mkdir()
            self.fixture(root)
            state = plan(root)
            (root / "moj-prop/index.html").write_text("<html><body>concurrent edit</body></html>")
            with self.assertRaisesRegex(RuntimeError, "PAGE_CHANGED_BEFORE_BACKUP"):
                repair(root, Path(tmp) / "backup", state)
            self.assertEqual((root / "moj-prop/index.html").read_text(), "<html><body>concurrent edit</body></html>")

    def test_duplicate_marker_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "index.html"
            f.write_text("<html><body>" + MARKER * 2 + "</body></html>")
            with self.assertRaisesRegex(RuntimeError, "AMBIGUOUS_TRACKER"):
                inspect_page(f)

    def test_no_body_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "index.html";f.write_text("<html>missing body")
            with self.assertRaisesRegex(RuntimeError, "AMBIGUOUS_BODY"):
                inspect_page(f)


if __name__ == "__main__":
    unittest.main()
