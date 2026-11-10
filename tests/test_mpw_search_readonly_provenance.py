"""Contract tests for the no-write MojPlayWin provenance audit."""

import tempfile
import unittest
from pathlib import Path

from scripts.mpw_search_readonly_provenance import TARGETS, audit, inspect_file


class ProvenanceTests(unittest.TestCase):
    def test_inspection_metadata_and_no_source_disclosure(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "source.py"
            p.write_text("SECRET_TOKEN = 'never-echo-this'", encoding="utf-8")
            metadata, contents = inspect_file(p)
            self.assertEqual(metadata["state"], "present")
            self.assertEqual(len(metadata["sha256"]), 64)
            self.assertIn("never-echo-this", contents)
            self.assertNotIn("never-echo-this", str(metadata))

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            result, contents = inspect_file(Path(folder) / "absent")
            self.assertEqual(result, {"state": "missing"})
            self.assertIsNone(contents)

    def test_symlinks_are_not_followed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            destination = root / "real"
            destination.write_text("safe", encoding="utf-8")
            shortcut = root / "shortcut"
            shortcut.symlink_to(destination)
            result, contents = inspect_file(shortcut)
            self.assertEqual(result, {"state": "unsafe_symlink"})
            self.assertIsNone(contents)

    def test_audit_outputs_only_flags_and_hashes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app, site = root / "app", root / "site"
            for relative in TARGETS.values():
                target = app / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("placeholder", encoding="utf-8")
            (app / TARGETS["product_template"]).write_text(
                '<link rel="canonical" href="https://mojplaywin.com/store/product/72/">'
                '<script type="application/ld+json">{"@type":"Product"}</script>',
                encoding="utf-8",
            )
            (app / TARGETS["urlconf"]).write_text("robots.txt sitemap.xml", encoding="utf-8")
            site.mkdir()
            (site / "passenger_wsgi.py").write_text("APP='Saeit-staging'", encoding="utf-8")
            result = audit(app, site)
            self.assertTrue(all(entry["state"] == "present" for entry in result["files"].values()))
            self.assertTrue(all(result["signals"].values()))
            self.assertNotIn("<script", str(result))


if __name__ == "__main__":
    unittest.main()
