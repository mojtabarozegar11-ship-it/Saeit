"""MOJ PROP English social cards: first-party image, no layout or checkout drift.

Runs locally on tracked HTML only. Does not call Facebook, create traffic,
send social posts, alter payments, or require a network connection.
"""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
import unittest

ROOT = Path(__file__).resolve().parents[1] / "templates/moj-prop"
IMAGE = (
    "https://mojplaywin.com/design-preview-20261017/static/site/heroes/"
    "education-detail.ae7381d4181d.webp"
)
GUIDES = [
    "education/risk-management/index.html",
    "education/drawdown-and-position-sizing/index.html",
    "education/simulated-versus-live/index.html",
]
PAGES = GUIDES + ["selected-traders/index.html"]


class PageMeta(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.links = []
        self.tag_count = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            self.tags.append(a)
        if tag == "link":
            self.links.append(a)
        if tag == "script":
            self.tag_count += 1

    def property(self, name):
        return [a.get("content") for a in self.tags if a.get("property") == name]

    def named(self, name):
        return [a.get("content") for a in self.tags if a.get("name") == name]


class MojPropFacebookCards(unittest.TestCase):
    def load_page(self, path):
        html = (ROOT / path).read_text("utf-8")
        meta = PageMeta()
        meta.feed(html)
        return html, meta

    def test_one_first_party_og_card_image_per_page(self):
        for page in PAGES:
            with self.subTest(page=page):
                raw, meta = self.load_page(page)
                self.assertEqual(meta.property("og:image"), [IMAGE])
                self.assertEqual(meta.property("og:image:width"), ["1600"])
                self.assertEqual(meta.property("og:image:height"), ["900"])
                self.assertEqual(meta.named("twitter:image"), [IMAGE])
                self.assertEqual(meta.named("twitter:card"), ["summary_large_image"])
                self.assertEqual(len(meta.property("og:image:alt")), 1)
                self.assertEqual(len(meta.property("og:title")), 1)
                self.assertEqual(len(meta.property("og:description")), 1)
                self.assertNotIn("<script src=\"https://", raw)

    def test_public_canonical_still_matches_the_existing_english_route(self):
        for page in PAGES:
            url = "https://mojplaywin.com/moj-prop/" + page.removesuffix("index.html")
            with self.subTest(page=page):
                _, meta = self.load_page(page)
                canonicals = [a.get("href") for a in meta.links
                              if a.get("rel") == "canonical"]
                self.assertEqual(canonicals, [url])
                self.assertEqual(urlsplit(IMAGE).hostname, "mojplaywin.com")

    def test_education_js_continuity_and_trader_selection_are_preserved(self):
        for page in GUIDES:
            with self.subTest(page=page):
                raw, _ = self.load_page(page)
                self.assertIn('<script defer src="/moj-prop/education/campaign-attribution.js"></script>', raw)
                self.assertIn('href="/moj-prop/starter-30-trx/"', raw)
                self.assertNotIn("<form", raw.lower())
        traders, _ = self.load_page("selected-traders/index.html")
        self.assertIn("Selected Professional Traders", traders)
        self.assertNotIn("Customer capital", traders)
        self.assertNotIn('name="payer_address"', traders)

    def test_no_unreviewed_external_script_asset_added(self):
        for page in PAGES:
            with self.subTest(page=page):
                raw, meta = self.load_page(page)
                self.assertNotIn("connect.facebook.net", raw)
                self.assertNotIn("graph.facebook.com", raw)
                self.assertNotIn("pixel.facebook", raw)
                self.assertNotIn("facebook.com/tr", raw)
                self.assertNotIn("gtag(", raw)
                self.assertEqual(raw.count('property="og:image"'), 1)


if __name__ == "__main__":
    unittest.main()
