"""Source regression: the public Taniya book cover must be fetchable by crawlers.

These tests inspect the actual template only. They never change the live page,
access private files, or claim that Google has indexed the image.
"""

from html.parser import HTMLParser
from pathlib import Path
import unittest


TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "taniya_studio" / "index.html"
EXPECTED_COVER = "/static/site/mojplaywin-products/taniya-baker-worms.webp?v=20261026"


class Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "img":
            self.elements.append(dict(attrs))


class TestTaniyaStudioCover(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = TEMPLATE.read_text(encoding="utf-8")
        cls.parser = Images()
        cls.parser.feed(cls.source)

    def test_no_diagnostic_truncation_in_image_source(self):
        self.assertNotIn("Warning: truncated output", self.source)
        self.assertNotIn("tokens truncated", self.source)
        self.assertNotIn("data:image/", self.source)

    def test_original_book_cover_uses_public_first_party_url(self):
        matching = [img for img in self.parser.elements
                    if "Front cover of Taniya and the Little Baker Worms" in (img.get("alt") or "")]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["src"], EXPECTED_COVER)

    def test_cover_keeps_descriptive_alt(self):
        img = next(img for img in self.parser.elements if img.get("src") == EXPECTED_COVER)
        self.assertEqual(img["alt"],
                         "Front cover of Taniya and the Little Baker Worms, by Mojtaba Roozegar")


if __name__ == "__main__":
    unittest.main()
