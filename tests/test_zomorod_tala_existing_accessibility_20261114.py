"""Targeted regression checks for the existing Tala page, no new template.

Only source inspection. Production output needs a separately authorized deployment
and independent live axe validation. No network, writes, payments or form submission.
"""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "public/tala/index.html"


def contrast_ratio(foreground, background):
    def luminance(value):
        rgb = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [n / 12.92 if n <= .04045 else ((n + .055) / 1.055) ** 2.4
                  for n in rgb]
        return sum(a * b for a, b in zip(linear, (.2126, .7152, .0722)))
    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + .05) / (dark + .05)


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.headers = []
        self.regions = []
        self.asides = []
        self.sources = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headers.append(tag)
        if a.get("class") == "topline":
            self.regions.append((tag, a.get("role"), a.get("aria-label")))
        if tag == "aside" and a.get("class") == "daily":
            self.asides.append(a)
        if tag == "a" and a.get("href"):
            self.links.append(a)
            if a["href"] in ("https://gold-api.com/", "https://frankfurter.dev/"):
                self.sources.append(a)


class TalaSourceAccessibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf8")
        cls.dom = Markup()
        cls.dom.feed(cls.source)
        cls.dom.close()

    def test_existing_one_h1_and_footer_h3_headings(self):
        self.assertEqual(self.dom.headers.count("h1"), 1)
        self.assertEqual(self.dom.headers.count("h4"), 0)
        for heading in ("اکتشاف", "خدمات", "شبکه‌ها"):
            self.assertEqual(self.source.count("<h3>" + heading + "</h3>"), 1)
        self.assertIn(".footgrid h3{font-size:12px;font-weight:500;color:var(--gold)}",
                      self.source)

    def test_top_info_and_daily_note_are_semantically_not_nested_landmarks(self):
        self.assertEqual(self.dom.regions, [
            ("div", "region", "اطلاعات شرکت")])
        self.assertEqual(len(self.dom.asides), 1)
        self.assertEqual(self.dom.asides[0].get("role"), "note")

    def test_source_links_have_non_color_cue(self):
        self.assertEqual(len(self.dom.sources), 3)
        for link in self.dom.sources:
            href = link["href"]
            # One source reference is already underlined by .live-source-note.
            # The two within .notice must be underlined at the link itself.
            if href in ("https://frankfurter.dev/",):
                self.assertIn("text-decoration:underline", link.get("style", ""))
        self.assertEqual(
            self.source.count('style="color:var(--gold);text-decoration:underline;text-underline-offset:2px"'),
            2)
        self.assertIn(".live-source-note a{color:var(--gold);text-decoration:underline}",
                      self.source)

    def test_footer_copyright_has_wcag_aa_text_contrast(self):
        self.assertGreaterEqual(contrast_ratio("#a4a296", "#0d0e0c"), 4.5)
        self.assertIn("justify-content:space-between;color:#a4a296;font-size:9px",
                      self.source)
        self.assertNotIn("justify-content:space-between;color:#77766e;font-size:9px",
                         self.source)

    def test_no_business_routes_or_existing_site_structure_removed(self):
        for item in ['id="live-market"', 'id="market"', 'id="showcase"',
                     'id="calculators"', 'id="studio"', 'id="learn"',
                     'href="/tala/admin/"', 'id="contact"',
                     'class="footer"', 'class="topline"', '<main>']:
            self.assertIn(item, self.source)
        self.assertIn('class="brand" href="/tala/"', self.source)
        self.assertNotIn("<iframe", self.source.lower())


if __name__ == "__main__":
    unittest.main()
