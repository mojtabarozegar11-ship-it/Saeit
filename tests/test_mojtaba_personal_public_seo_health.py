#!/usr/bin/env python3
"""Unit tests for safe, public, read-only personal SEO audit and FAQ source."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "personal_health_audit",
    ROOT / "scripts/mojtaba_personal_public_seo_health_audit.py",
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
FAQ_PATH = ROOT / "content/mojtaba_personal_public_identity_faq_20261016.json"

def valid_page():
    person = json.dumps({"@context": "https://schema.org", "@type": "ProfilePage",
                         "mainEntity": {"@type": "Person", "name": "Mojtaba Roozegar"}})
    return (f"<html><head><title>Mojtaba Roozegar | Official Website</title>"
            f'<meta name="description" content="Mojtaba Roozegar official personal website">'
            f'<meta name="robots" content="index,follow">'
            f'<link rel="canonical" href="{audit.ROOT}">'
            f'<script type="application/ld+json">{person}</script>'
            f"</head><body>Professional information</body></html>").encode()

class PublicSEOTests(unittest.TestCase):
    def test_healthy_home_meta(self):
        self.assertEqual(audit.evaluate_home(valid_page())["errors"], [])

    def test_noindex_detected(self):
        self.assertIn("home_not_explicitly_indexable",
                      audit.evaluate_home(valid_page().replace(
                          b"index,follow", b"noindex,nofollow"))["errors"])

    def test_wrong_canonical_detected(self):
        self.assertIn("home_canonical_missing_or_incorrect",
                      audit.evaluate_home(valid_page().replace(
                          audit.ROOT.encode(), b"https://example.net/"))["errors"])

    def test_missing_person_detected(self):
        self.assertIn("person_jsonld_missing",
                      audit.evaluate_home(valid_page().replace(
                          b'"name": "Mojtaba Roozegar"', b'"name": "Someone Else"'))["errors"])

    def test_sitemap_count_and_main_url(self):
        locs = [audit.ROOT] + [audit.ROOT + f"blog/story-{i}/" for i in range(103)]
        xml = ("<urlset>" + "".join(f"<url><loc>{url}</loc></url>" for url in locs)
               + "</urlset>").encode()
        details = audit.check_sitemap(xml)
        self.assertEqual(details["errors"], [])
        self.assertEqual(details["personal_urls"], 104)

    def test_sitemap_guard_detects_missing_articles(self):
        self.assertIn("personal_sitemap_below_protected_page_floor",
                      audit.check_sitemap(b"<urlset><url><loc>https://mojplaywin.com/mojtaba.roozegar/</loc></url></urlset>")["errors"])

    def test_faq_professional_bilingual_scope(self):
        data = json.loads(FAQ_PATH.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], 1)
        self.assertEqual(len(data["questions"]), 8)
        self.assertEqual(data["target"], audit.ROOT)
        ids = set()
        for row in data["questions"]:
            ids.add(row["id"])
            for language in ("en", "fa"):
                self.assertGreaterEqual(len(row[language]["question"]), 10)
                self.assertGreaterEqual(len(row[language]["answer"]), 40)
                self.assertNotIn("<script", row[language]["answer"].lower())
        self.assertEqual(ids, set(range(1, 9)))

if __name__ == "__main__":
    unittest.main()
