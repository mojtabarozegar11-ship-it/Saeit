"""Tests for the entirely new, content-preserving Zomorod Melal static homepage."""
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "content/zomorod-new-home/index.html"
CSS_PATH = ROOT / "content/zomorod-new-home/nova.css"


class Tags(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nodes = []
        self.ids = set()
        self.duplicate_ids = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.nodes.append((tag, attrs))
        if "id" in attrs:
            if attrs["id"] in self.ids:
                self.duplicate_ids.append(attrs["id"])
            self.ids.add(attrs["id"])


class TestNovaHomepage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")
        cls.css = CSS_PATH.read_text(encoding="utf-8")
        cls.doc = Tags()
        cls.doc.feed(cls.html)

    def test_new_template_and_original_archive_access(self):
        self.assertTrue(self.html.startswith("<!doctype html>"))
        self.assertIn("zm-nova-home-2026-v1", self.html)
        self.assertNotIn("agritech-luxe-v3.css", self.html)
        self.assertIn("/site-heritage/home-before-redesign/", self.html)
        self.assertIn('/static/site/company/company-logo.png', self.html)
        self.assertFalse(self.doc.duplicate_ids)

    def test_rich_content_and_original_route_families(self):
        self.assertGreaterEqual(sum(t == "section" for t, _ in self.doc.nodes), 11)
        self.assertGreaterEqual(sum(t == "img" for t, _ in self.doc.nodes), 16)
        for path in (
            "/agriculture/", "/agriculture/genetics/",
            "/agriculture/tools/", "/agriculture/gardening-tools/",
            "/company/", "/about/", "/industry/", "/research/",
            "/knowledge/", "/education/", "/agents/", "/contact/",
            "/amozeshgah/", "/en/", "/ar/", "/zh/",
        ):
            with self.subTest(path=path):
                self.assertIn('href="' + path + '"', self.html)

    def test_image_dimensions_alt_and_loading(self):
        for tag, attrs in self.doc.nodes:
            if tag != "img":
                continue
            self.assertTrue(attrs.get("src", "").startswith("/static/site/"))
            self.assertTrue(attrs.get("alt"), "All images need meaningful alt")
            self.assertTrue(attrs.get("width"))
            self.assertTrue(attrs.get("height"))
        self.assertEqual(self.html.count('fetchpriority="high"'), 2) # preload + visible hero

    def test_new_design_accessible_mobile_and_without_remote_dependencies(self):
        for needle in (
            "@media(max-width:650px)",
            "prefers-reduced-motion",
            "focus-visible",
            ".megapanel",
            ".hero-grid",
            ".sector-grid",
            ".journal-grid",
        ):
            self.assertIn(needle, self.css)
        self.assertNotIn("@import", self.css)
        self.assertNotIn("https://", self.css)
        self.assertNotIn("http://", self.css)
        self.assertIn('<html lang="fa" dir="rtl">', self.html)
        self.assertIn('class="skip"', self.html)
        self.assertIn('class="navtoggle"', self.html)

if __name__ == "__main__":
    unittest.main()
