"""Offline guards: preserve all 152 observed MojPlayWin pages and extend image maps additively.

These tests read versioned evidence only: no network, deployment, search console, or writes.
"""
from pathlib import Path
import json
import tempfile
import unittest
from xml.etree import ElementTree as ET

from scripts.seo_sitemap_parity_guard import compare

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/seo/evidence"
CANDIDATES = ROOT / "docs/seo/release-candidates"
BASE = EVIDENCE / "mpw-public-152-page-reconstructed-baseline-20261112.xml"
OLD = CANDIDATES / "mpw-image-sitemap-20261111.xml"
NEW = CANDIDATES / "mpw-image-sitemap-20261112-book-covers.xml"
SITE = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
IMAGE = "{http://www.google.com/schemas/sitemap-image/1.1}"
ORIGIN = "https://mojplaywin.com"
COVERS = {
    ORIGIN + "/store/product/72/":
        ORIGIN + "/static/site/mojplaywin-products/chess-improvement.webp?v=20261026",
    ORIGIN + "/store/product/225/":
        ORIGIN + "/static/site/mojplaywin-products/taniya-baker-worms.webp?v=20261026",
}


def load_map(path):
    root = ET.parse(path).getroot()
    if root.tag != SITE + "urlset":
        raise ValueError("Expected standard urlset")
    entries = {}
    for item in root.findall(SITE + "url"):
        page = item.findtext(SITE + "loc")
        if not page or page in entries:
            raise ValueError("Missing or duplicate page loc")
        entries[page] = [
            entry.findtext(IMAGE + "loc")
            for entry in item.findall(IMAGE + "image")
        ]
    return entries


class MojPlayWinReleaseCandidateTests(unittest.TestCase):
    def test_reconstructed_152_page_baseline_matches_original_live_audit(self):
        inventory = json.loads((EVIDENCE / "mpw-image-inventory-20261111.json").read_text())
        report = json.loads((EVIDENCE / "mpw-image-verified-20261111.json").read_text())
        expected = set(inventory) | set(report["pages_without_verified_images"])
        self.assertEqual(len(inventory), 94)
        self.assertEqual(len(report["pages_without_verified_images"]), 58)
        self.assertEqual(len(expected), 152)
        self.assertEqual(set(load_map(BASE)), expected)

    def test_one_page_django_fallback_fails_parity_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "unsafe-single-page.xml"
            candidate.write_text(
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                '<url><loc>https://mojplaywin.com/store/</loc></url></urlset>',
                encoding="utf-8",
            )
            result = compare(BASE, candidate, ORIGIN,
                             ["/store/product/72/", "/store/product/225/",
                              "/store/product/879/"])
            self.assertEqual(result["status"], "HOLD")
            self.assertEqual(result["before_urls"], 152)
            self.assertEqual(result["after_urls"], 1)
            self.assertEqual(result["removed_count"], 151)
            self.assertEqual(result["missing_required_count"], 3)

    def test_new_image_candidate_preserves_every_prior_page_and_image(self):
        old = load_map(OLD)
        new = load_map(NEW)
        self.assertEqual(len(old), 94)
        self.assertEqual(len(new), 96)
        self.assertEqual({page: new[page] for page in old}, old)
        self.assertEqual(set(new) - set(old), set(COVERS))
        self.assertEqual(sum(map(len, old.values())), 396)
        self.assertEqual(sum(map(len, new.values())), 398)
        self.assertEqual(len({img for urls in new.values() for img in urls}), 284)

    def test_only_known_public_cover_mappings_are_added(self):
        before = load_map(OLD)
        after = load_map(NEW)
        for page, image in COVERS.items():
            self.assertNotIn(page, before)
            self.assertEqual(after[page], [image])
        self.assertNotIn(ORIGIN + "/store/product/879/", after)
        self.assertTrue(set(after).issubset(set(load_map(BASE))))

    def test_reconstructed_pages_and_images_are_public_same_origin(self):
        for page in load_map(BASE):
            self.assertTrue(page.startswith(ORIGIN + "/"), page)
            self.assertNotIn("?", page)
            self.assertNotIn("#", page)
        for page, images in load_map(NEW).items():
            self.assertTrue(page.startswith(ORIGIN + "/"))
            self.assertLessEqual(len(images), 1000)
            self.assertEqual(len(images), len(set(images)))
            for image in images:
                self.assertTrue(image.startswith(ORIGIN + "/"))
                self.assertFalse(any(x in image.lower() for x in
                                     ("/private/", "/download/", "/checkout/",
                                      "?token=", "&token=", "?signature=")))

    def test_cover_pages_are_not_mistaken_for_live_html_repairs(self):
        self.assertEqual(set(COVERS), set(load_map(NEW)) - set(load_map(OLD)))
        # This assertion protects scope: adding image sitemap rows NEVER
        # proves a public <img src> exists or a Google indexing event occurred.
        self.assertEqual(len(COVERS), 2)


if __name__ == "__main__":
    unittest.main()
