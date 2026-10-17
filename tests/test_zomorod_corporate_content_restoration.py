"""Regression gates for restoring historical Zomorod Melal corporate copy.

These tests are local/read-only; they do not prove the exact 2026-10-15 01:00
hosting backup matches, or that public routes/images and Lighthouse are healthy.
Those checks remain mandatory before any production publishing.
"""
import ast
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "content" / "zomorod-nova-pages"

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.ids = set()
        self.links = []
        self.images = []
        self.meta = []
        self.html_attrs = {}
        self.text = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append(tag)
        if tag == "html":
            self.html_attrs = attrs
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "img":
            self.images.append(attrs)
        if tag == "meta":
            self.meta.append(attrs)
    def handle_data(self, data):
        self.text.append(data)

def legacy_company_data():
    tree = ast.parse((ROOT / "core" / "views.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if not isinstance(key, ast.Constant) or key.value != "company":
                continue
            try:
                candidate = ast.literal_eval(value)
            except (ValueError, TypeError, SyntaxError, RecursionError):
                continue
            if isinstance(candidate, dict) and "product_chains" in candidate and "departments" in candidate:
                return candidate
    raise AssertionError("Original static corporate data not found in core/views.py")

class CorporateContentPreservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = {name: (PAGES / (name + ".html")).read_text(encoding="utf-8")
                   for name in ("about", "company")}
        cls.parsed = {}
        for name, document in cls.raw.items():
            parser = PageParser()
            parser.feed(document)
            cls.parsed[name] = parser
        cls.legacy = legacy_company_data()

    def test_safe_document_structure_and_mobile_rtl(self):
        for name, parser in self.parsed.items():
            with self.subTest(name=name):
                self.assertEqual(parser.html_attrs.get("lang"), "fa")
                self.assertEqual(parser.html_attrs.get("dir"), "rtl")
                self.assertEqual(parser.tags.count("main"), 1)
                self.assertEqual(parser.tags.count("h1"), 1)
                self.assertTrue(any(m.get("name") == "viewport" for m in parser.meta))
                self.assertLess(len(self.raw[name].encode("utf-8")), 140000)
                self.assertNotIn("javascript:", self.raw[name].lower())
                self.assertNotIn("<iframe", self.raw[name].lower())

    def test_complete_search_descriptions(self):
        for name, parser in self.parsed.items():
            with self.subTest(name=name):
                matches = [m.get("content", "") for m in parser.meta if m.get("name") == "description"]
                self.assertEqual(len(matches), 1)
                self.assertGreaterEqual(len(matches[0]), 95)
                self.assertLessEqual(len(matches[0]), 170)
                self.assertEqual(len(re.findall(r'<link[^>]+rel="canonical"[^>]*>', self.raw[name])), 1)

    def test_all_images_have_accessible_descriptions(self):
        for name, parser in self.parsed.items():
            with self.subTest(name=name):
                self.assertGreaterEqual(len(parser.images), 3)
                for image in parser.images:
                    self.assertTrue(image.get("alt"), f"{name}: image missing alt")

    def test_in_document_navigation_targets(self):
        for name, parser in self.parsed.items():
            with self.subTest(name=name):
                for href in parser.links:
                    if href.startswith("#") and len(href) > 1:
                        self.assertIn(href[1:], parser.ids)
                self.assertNotIn("/company/executive/", parser.links)

    def test_preserve_existing_editorial_sections(self):
        expected = {
            "about": ["مأموریت و نگاه مسئله‌محور", "مدیریت اقتصادی منابع", "اتصال دانش و کاربرد", "چهار راهنمای عملی برای تصمیم بهتر"],
            "company": ["مدیریت کشاورزی و روستایی", "باغبانی و تولید کنترل‌شده", "ژنتیک و اصلاح نژاد", "چهار راهنمای عملی برای تصمیم بهتر"],
        }
        for name, fragments in expected.items():
            for fragment in fragments:
                with self.subTest(name=name, fragment=fragment):
                    self.assertIn(fragment, unescape(self.raw[name]))

    def test_historical_company_sections_and_records(self):
        rendered = unescape(self.raw["company"])
        self.assertIn(self.legacy["body"], rendered)
        mandatory = (
            "items", "units", "departments", "advisors", "management_offices",
            "committees", "department_structure", "statutory_activities",
            "genetics_scopes", "social_responsibility", "product_chains",
            "future_chains", "projects", "channels",
        )
        for key in mandatory:
            records = self.legacy[key]
            self.assertGreater(len(records), 0, f"{key} is empty")
            for record in records:
                title = record.get("title") or record.get("department")
                if title:
                    with self.subTest(section=key, record=title):
                        self.assertIn(title, rendered)
                if record.get("text"):
                    with self.subTest(section=key, detail=title):
                        self.assertIn(record["text"], rendered)
                if record.get("role"):
                    with self.subTest(section=key, role=title):
                        self.assertIn(record["role"], rendered)

    def test_about_company_profile_and_active_anchor(self):
        about = unescape(self.raw["about"])
        self.assertIn("شرکت کشت و صنعت زمرد ملل", about)
        self.assertIn("مجتبی روزگار", about)
        self.assertIn("original-executive-profile", self.parsed["about"].ids)
        self.assertIn("#original-executive-profile", self.parsed["about"].links)
        self.assertIn("preserved-corporate-profile-20261017", about)
        self.assertIn("preserved-corporate-records-20261017", self.raw["company"])

if __name__ == "__main__":
    unittest.main()
