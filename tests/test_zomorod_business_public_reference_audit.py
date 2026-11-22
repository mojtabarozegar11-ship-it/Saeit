#!/usr/bin/env python3
"""Offline regression of homepage visual dependency coverage and safe traversal."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/zomorod_business_public_reference_audit.py"
spec = importlib.util.spec_from_file_location("public_reference_audit", SCRIPT)
assert spec and spec.loader
auditor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auditor)


class ReferencedVisualFiles(unittest.TestCase):
    def test_relative_css_urls_do_not_escape_root(self):
        self.assertEqual(
            auditor.reference_to_path("../fonts/site.woff2", "static/css/layout.css"),
            ("local", "static/fonts/site.woff2"),
        )
        self.assertEqual(
            auditor.reference_to_path("../../logo.svg", "static/css/layout.css"),
            ("local", "logo.svg"),
        )
        self.assertEqual(
            auditor.reference_to_path("../../../secret.css", "static/css/layout.css")[0],
            "unsafe",
        )
        self.assertEqual(
            auditor.reference_to_path("%2e%2e/%2e%2e/%2e%2e/private.js", "static/css/layout.css")[0],
            "unsafe",
        )

    def test_public_absolute_url_and_external_urls(self):
        self.assertEqual(
            auditor.reference_to_path("https://zomorodmelal.ir/static/app.js?v=12", "index.html"),
            ("local", "static/app.js"),
        )
        self.assertEqual(
            auditor.reference_to_path("https://cdn.example.net/site.js", "index.html")[0],
            "external",
        )
        self.assertEqual(auditor.reference_to_path("/about/", "index.html")[0], "ignored")

    def test_html_css_dependency_coverage_is_accounted(self):
        with tempfile.TemporaryDirectory(prefix="zomorod-public-references-") as tmp:
            root = Path(tmp)
            (root / "static" / "css").mkdir(parents=True)
            (root / "static" / "fonts").mkdir()
            (root / "assets").mkdir()
            (root / "index.html").write_text(
                '<html><head><link rel="stylesheet" href="/static/css/layout.css">'
                '<script src="/static/app.js"></script>'
                '<link rel="preload" href="https://cdn.example.net/font.woff2">'
                '</head><body><img src="/assets/hero.webp"></body></html>',
                encoding="utf-8",
            )
            (root / "static" / "css" / "layout.css").write_text(
                '@font-face{src:url("../fonts/site.woff2")}', encoding="utf-8",
            )
            (root / "static" / "app.js").write_bytes(b"console.log('ok')")
            (root / "static" / "fonts" / "site.woff2").write_bytes(b"font")
            (root / "assets" / "hero.webp").write_bytes(b"image")
            report = auditor.audit(root)
            self.assertEqual(report["LOCAL_REFERENCES"], 4)
            self.assertEqual(report["LOCAL_OUTSIDE_PROTECTED_SCOPE"], 0)
            self.assertEqual(report["LOCAL_MISSING_OR_SYMLINK"], 0)
            self.assertEqual(report["UNSAFE_REFERENCE_COUNT"], 0)
            self.assertEqual(report["EXTERNAL_DEPENDENCY_COUNT"], 1)
            self.assertEqual(report["CSS_FILES_PARSED"], 1)
            (root / "static" / "fonts" / "site.woff2").unlink()
            self.assertEqual(auditor.audit(root)["LOCAL_MISSING_OR_SYMLINK"], 1)

    def test_unprotected_root_subfolder_reference_flagged(self):
        with tempfile.TemporaryDirectory(prefix="zomorod-public-references-") as tmp:
            root = Path(tmp)
            (root / "static").mkdir()
            (root / "assets").mkdir()
            (root / "other").mkdir()
            (root / "other" / "hero.svg").write_bytes(b"svg")
            (root / "index.html").write_text('<img src="/other/hero.svg">', encoding="utf-8")
            result = auditor.audit(root)
            self.assertEqual(result["LOCAL_REFERENCES"], 1)
            self.assertEqual(result["LOCAL_OUTSIDE_PROTECTED_SCOPE"], 1)
            self.assertEqual(result["LOCAL_MISSING_OR_SYMLINK"], 0)


if __name__ == "__main__":
    unittest.main()
