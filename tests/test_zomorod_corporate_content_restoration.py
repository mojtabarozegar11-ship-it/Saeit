"""Regression gates for restoring historical Zomorod Melal corporate copy.

These tests are local/read-only; they do not prove the exact 2026-10-14 01:00
hosting backup matches, or that public routes/images and Lighthouse are healthy.
Those checks remain mandatory before any production publishing.
"""
import ast
import hashlib
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

def legacy_about_data():
    tree = ast.parse((ROOT / "core" / "views.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if not isinstance(key, ast.Constant) or key.value != "about":
                continue
            try:
                candidate = ast.literal_eval(value)
            except (ValueError, TypeError, SyntaxError, RecursionError):
                continue
            if isinstance(candidate, dict) and "items" in candidate and "cta_title" in candidate:
                return candidate
    raise AssertionError("Original About archive not found in core/views.py")


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
        cls.archived_about = legacy_about_data()

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

    def test_no_repeated_content_photographs_in_six_corporate_pages(self):
        # Logo is a recurring brand mark, NOT a photograph or article image.
        source_owners = {}
        byte_owners = {}
        for name in ("about", "company", "services", "industry", "research", "knowledge"):
            doc = (PAGES / (name + ".html")).read_text(encoding="utf-8")
            parser = PageParser()
            parser.feed(doc)
            photographs = [image["src"] for image in parser.images
                           if image.get("src")
                           and "company-logo" not in image["src"]]
            self.assertGreaterEqual(len(photographs), 2, name)
            for src in photographs:
                with self.subTest(page=name, image=src):
                    self.assertNotIn(src, source_owners,
                                     f"Repeated photograph: {src} in {name} and {source_owners.get(src)}")
                    source_owners[src] = name
                    if src.startswith("/static/site/"):
                        file = ROOT / "core" / "static" / "site" / src.removeprefix("/static/site/")
                        self.assertTrue(file.is_file(), f"Missing photograph in source: {src}")
                        digest = hashlib.sha256(file.read_bytes()).hexdigest()
                        self.assertNotIn(digest, byte_owners,
                                         f"Same photograph bytes under different filenames: {src} and {byte_owners.get(digest)}")
                        byte_owners[digest] = src

    def test_page_images_are_not_removed(self):
        # Every original image inside the proposed About/Company page must
        # be either kept or replaced with a distinct, relevant image.
        for name, parser in self.parsed.items():
            with self.subTest(page=name):
                self.assertGreaterEqual(len(parser.images), 3)
                photos = [img for img in parser.images if "company-logo" not in img.get("src", "")]
                self.assertEqual(len(photos), 2)
                self.assertEqual(len({img["src"] for img in photos}), 2)

    def test_all_seven_website_pages_have_distinct_editorial_images(self):
        from collections import Counter
        pages = {
            "home": ROOT / "content/zomorod-new-home/index.html",
            **{slug: PAGES / (slug + ".html") for slug in
               ("about", "company", "services", "industry", "research", "knowledge")},
        }
        photographs = []
        for slug, path in pages.items():
            parser = PageParser()
            parser.feed(path.read_text(encoding="utf-8"))
            photos = [img for img in parser.images
                      if img.get("src") and "company-logo" not in img["src"]]
            self.assertGreaterEqual(len(photos), 2, slug)
            for img in photos:
                with self.subTest(page=slug, src=img["src"]):
                    self.assertTrue(img.get("alt"), "Required meaningful alt")
                    photographs.append(img["src"])
        self.assertEqual(len(photographs), 30)
        repeats = {path: count for path, count in Counter(photographs).items()
                   if count > 1}
        self.assertEqual(repeats, {}, "Editorial images must never repeat across pages")

    def test_photo_licenses_file_integrity_and_no_false_company_claims(self):
        import json
        licenses = ROOT / "docs/zomorod-cc0-editorial-photographs.json"
        self.assertTrue(licenses.is_file())
        records = json.loads(licenses.read_text(encoding="utf-8"))["photos"]
        self.assertEqual(len(records), 17)
        seen_hashes = set()
        source_urls = set()
        for image in records:
            with self.subTest(image=image["file"]):
                self.assertEqual(image["license"], "cc0")
                self.assertFalse(image["is_company_project_photo"])
                self.assertTrue(image["source_url"].startswith("https://"))
                self.assertNotIn(image["source_url"], source_urls)
                source_urls.add(image["source_url"])
                self.assertIn("نمونه تصویری", image["label"])
                file = ROOT / image["file"]
                self.assertTrue(file.is_file())
                self.assertGreater(file.stat().st_size, 15000)
                self.assertLess(file.stat().st_size, 400000)
                digest = hashlib.sha256(file.read_bytes()).hexdigest()
                self.assertEqual(digest, image["sha256"])
                self.assertNotIn(digest, seen_hashes)
                seen_hashes.add(digest)

    def test_original_emerald_system_stylesheet_preserved(self):
        css = ROOT / "core/static/site/emerald-system.css"
        self.assertTrue(css.is_file(), "Restore original published CSS into repository")
        data = css.read_bytes()
        self.assertEqual(len(data), 3480)
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            "efeb49358d01f93bad576aff9db89f1400a9ea734a1240be86831f026481aeb4",
        )

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

    def test_complete_historical_about_portal_copied(self):
        original = self.archived_about
        about = unescape(self.raw["about"])
        for key in ("lead", "heading", "body", "cta_title", "cta_text"):
            with self.subTest(section="about", field=key):
                self.assertIn(original[key], about)
        for item in original["items"]:
            with self.subTest(section="about", record=item["title"]):
                self.assertIn(item["title"], about)
                self.assertIn(item["text"], about)
        for original_link in original["links"]:
            with self.subTest(section="about", url=original_link["url"]):
                self.assertIn(original_link["url"], self.parsed["about"].links)
        self.assertIn("historic-executive-duties", self.parsed["about"].ids)
        for archived_manager_duty in (
            "راهبری و هدایت ساختار سازمانی و مسیرهای توسعه شرکت.",
            "تکیه بر مطالعه، شواهد، تحلیل فنی و اقتصادی و کنترل ریسک.",
            "توجه به انطباق قانونی، مستندسازی، کنترل کیفیت و تصمیم‌گیری انسانی.",
        ):
            self.assertIn(archived_manager_duty, about)

    def test_historical_company_context_status_and_cta(self):
        page = unescape(self.raw["company"])
        for key in ("lead", "heading", "cta_title", "cta_text"):
            with self.subTest(field=key):
                self.assertIn(self.legacy[key], page)
        for planned_chain in self.legacy.get("future_chains", []):
            with self.subTest(plan=planned_chain["title"]):
                self.assertIn(planned_chain["title"], page)
                self.assertIn(planned_chain["status"], page)
        self.assertIn("historic-company-collaboration", self.parsed["company"].ids)

    def test_about_company_profile_and_active_anchor(self):
        about = unescape(self.raw["about"])
        self.assertIn("شرکت کشت و صنعت زمرد ملل", about)
        self.assertIn("مجتبی روزگار", about)
        self.assertIn("original-executive-profile", self.parsed["about"].ids)
        self.assertIn("#historic-executive-duties", self.parsed["about"].links)
        self.assertIn("preserved-corporate-profile-20261017", about)
        self.assertIn("preserved-corporate-records-20261017", self.raw["company"])

if __name__ == "__main__":
    unittest.main()
