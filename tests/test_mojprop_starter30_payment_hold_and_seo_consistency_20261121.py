"""Contract: consistent English Starter30 payment hold, trust copy and SEO.

Source-only; does not assert the live host has deployed these bytes.
"""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1] / "templates/moj-prop-v4"
HOME = ROOT / "index.html"
STARTER = ROOT / "starter-30-trx/index.html"
FREE_TERMS = (
    "/moj-prop-intake/?format=html&service=blueprint&package=starter-30-trx"
    "&utm_source=moj_prop&utm_medium=onsite&utm_campaign=starter30_lead"
    "&utm_content=free_terms"
)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.forms = []
        self.meta = {}
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        info = dict(attrs)
        if tag == "a":
            self.links.append(info.get("href"))
        if tag == "form":
            self.forms.append(info)
        if tag == "meta":
            key = info.get("name") or info.get("property")
            if key:
                self.meta.setdefault(key, []).append(info.get("content", ""))
        if tag == "script":
            self.scripts.append(info)


class Starter30ClosedPaymentContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {
            "home": HOME.read_text(encoding="utf-8"),
            "starter": STARTER.read_text(encoding="utf-8"),
        }
        cls.pages = {}
        for key, text in cls.sources.items():
            parser = Page()
            parser.feed(text)
            cls.pages[key] = parser

    def test_two_pages_agree_enrollment_and_payment_currently_unavailable(self):
        for key, source in self.sources.items():
            with self.subTest(page=key):
                self.assertTrue("payment currently unavailable" in source.lower() or "payment and new enrollment are currently unavailable" in source.lower())
                self.assertIn("do not send trx", source.lower())
                self.assertNotIn("/mojprop-starter30-checkout/", [
                    link for link in self.pages[key].links if link
                ])
                self.assertNotIn("walletconnect", source.lower())
                self.assertNotIn("tronweb.trx.sendtransaction", source.lower())
        self.assertIn("no invoice is being issued", self.sources["home"].lower())
        self.assertIn("invoice issuance are currently unavailable",
                      self.sources["starter"].lower())
        self.assertNotIn(
            "prelaunch “no payment” message does not apply",
            self.sources["starter"].lower(),
        )

    def test_free_terms_attribution_is_fixed_and_payment_never_leaks_into_link(self):
        starter = self.pages["starter"]
        self.assertEqual(starter.links.count(FREE_TERMS), 3)
        self.assertTrue(all(not link or "wallet=" not in link and "email=" not in link
                            for link in starter.links))
        self.assertTrue(any(link == FREE_TERMS for link in self.pages["home"].links))
        self.assertFalse(any(link and link.startswith("/mojprop-starter30-checkout/")
                             for parser in self.pages.values() for link in parser.links))

    def test_public_invoice_form_is_read_only_and_not_an_order(self):
        forms = self.pages["starter"].forms
        self.assertEqual(len(forms), 1)
        self.assertEqual(forms[0].get("action"), "/mojprop-starter30-status/")
        self.assertEqual(forms[0].get("method"), "get")
        self.assertNotIn('name="txid"', self.sources["starter"])
        self.assertNotIn('name="payer_address"', self.sources["starter"])

    def test_search_previews_are_short_and_trustworthy(self):
        for key, page in self.pages.items():
            with self.subTest(page=key):
                description, = page.meta["description"]
                self.assertLessEqual(len(description), 200)
                self.assertIn("30 trx", description.lower())
                self.assertTrue("payment unavailable" in description.lower()
                                or "payment is currently unavailable" in description.lower())
                for field in ("og:description", "twitter:description"):
                    snippets = page.meta[field]
                    self.assertEqual(len(snippets), 1)
                    self.assertLessEqual(len(snippets[0]), 200)
                self.assertNotIn("guaranteed earnings", description.lower())

    def test_starter_has_two_known_scripts_plus_inert_jsonld_only(self):
        tags = self.pages["starter"].scripts
        self.assertEqual(len(tags), 3)
        external = {tag.get("src") for tag in tags if tag.get("src")}
        self.assertEqual(external, {
            "/mpw-measure/tracker.js",
            "/moj-prop/starter-30-trx/checkout-attribution.js",
        })
        inline = [tag for tag in tags if not tag.get("src")]
        self.assertEqual(len(inline), 1)
        self.assertEqual(inline[0].get("type"), "application/ld+json")
        text = self.sources["starter"]
        schema_match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>', text, re.DOTALL
        )
        self.assertIsNotNone(schema_match)
        schema = json.loads(schema_match.group(1))
        types = [row.get("@type") for row in schema.get("@graph", [])]
        self.assertIn("WebPage", types)
        self.assertIn("BreadcrumbList", types)
        self.assertNotIn("Product", types)
        self.assertNotIn("Offer", types)
        self.assertNotIn("AggregateRating", types)


if __name__ == "__main__":
    unittest.main()
