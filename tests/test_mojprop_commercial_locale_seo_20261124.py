"""Regression checks for commercial SEO using the existing 20-locale renderer."""
from html.parser import HTMLParser
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import mojprop_multilang_20261121_build as legacy
from scripts import mojprop_commercial_locale_seo_20261124 as seo


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.tags = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def links(self, rel):
        return [a.get("href") for tag, a in self.tags
                if tag == "link" and a.get("rel") == rel]


def originals():
    items = {row[0].lower(): row for row in legacy.L}
    items["en"] = ["en", "English", "MOJ PROP simulated trading education",
                   "An educational introduction to simulation.",
                   "Virtual reference balance.", "Risk control.",
                   "Read the rules.", "No guaranteed profit.",
                   "Information only.", "Read official English terms"]
    with patch.object(legacy, "path", lambda code: "/moj-prop/languages/" + code.lower() + "/"):
        return {code: legacy.localized(row) for code, row in items.items()}


class CommercialLocaleSeoTests(unittest.TestCase):
    def test_existing_twenty_locales_have_commercial_copy_and_preserved_links(self):
        pages = originals()
        self.assertEqual(set(pages), set(seo.COPY))
        self.assertEqual(len(pages), 20)
        for code, before in pages.items():
            with self.subTest(code=code):
                after = seo.transform(before, code)
                title, desc, cta = seo.COPY[code]
                from html import escape
                self.assertIn("<h1>MOJ PROP | " + escape(title, quote=True) + "</h1>", after)
                self.assertIn(escape(desc, quote=True), after)
                self.assertIn('href="/moj-prop/starter-30-trx/">' + escape(cta), after)
                self.assertEqual(Page(before).links("canonical"), Page(after).links("canonical"))
                self.assertEqual(Page(before).links("alternate"), Page(after).links("alternate"))
                self.assertEqual(after.count(seo.MARKER), 1)
                self.assertIn('30 TRX', desc)
                self.assertIn('<meta name="robots" content="index,follow', after)
                with self.assertRaises(ValueError):
                    seo.transform(after, code)

    def test_complete_tree_is_built_without_mutating_sources(self):
        pages = originals()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source", root / "candidate"
            for code, before in pages.items():
                path = source / code / "index.html"
                path.parent.mkdir(parents=True)
                path.write_text(before, encoding="utf-8")
            seo.build(source, output)
            self.assertEqual(len(list(output.glob("*/index.html"))), 20)
            for code, before in pages.items():
                self.assertEqual((source / code / "index.html").read_text(encoding="utf-8"), before)

    def test_invalid_canonical_does_not_produce_candidate(self):
        before = originals()["en"]
        with self.assertRaises(ValueError):
            seo.transform(before.replace(seo.BASE + "en/", "https://example.org/"), "en")


if __name__ == "__main__":
    unittest.main()
