"""Read-only source contract for the already-public MOJ PROP English trader enquiry."""

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree
import unittest


ROOT = Path(__file__).resolve().parents[1] / "templates" / "moj-prop"
ORIGIN = "https://mojplaywin.com"
PUBLIC_PATHS = (
    "/moj-prop/",
    "/moj-prop/rules/",
    "/moj-prop/starter-30-trx/",
    "/moj-prop/contact/",
    "/moj-prop/selected-traders/",
    "/moj-prop/education/",
    "/moj-prop/education/risk-management/",
    "/moj-prop/education/drawdown-and-position-sizing/",
    "/moj-prop/education/sixty-day-simulated-challenge/",
    "/moj-prop/education/best-day-consistency/",
    "/moj-prop/education/simulated-versus-live/",
    "/moj-prop/signals/",
    "/moj-prop/catalog/",
    "/moj-prop/payment/",
)


class _HTMLContract(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.canonicals = []
        self.h1 = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "h1":
            self.h1 += 1
        if tag == "a" and "href" in values:
            self.links.append(values["href"])
        if tag == "link" and values.get("rel") == "canonical":
            self.canonicals.append(values.get("href"))


class EnglishSelectedTradersStaticTests(unittest.TestCase):
    def test_separate_professional_trader_page_and_enquiry(self):
        source = (ROOT / "selected-traders/index.html").read_text("utf-8")
        parsed = _HTMLContract()
        parsed.feed(source)
        self.assertEqual(parsed.h1, 1)
        self.assertEqual(parsed.canonicals, [ORIGIN + "/moj-prop/selected-traders/"])
        self.assertIn("monthly salary", source.lower())
        self.assertIn("real-money", source.lower())
        self.assertIn("company-controlled", source.lower())
        self.assertIn("not a public job vacancy", source.lower())
        self.assertIn("not automatic acceptance", source.lower())
        self.assertIn("/moj-prop/contact/", parsed.links)
        self.assertIn("/moj-prop/starter-30-trx/", parsed.links)
        mails = [urlsplit(link) for link in parsed.links if link.startswith("mailto:")]
        self.assertEqual(len(mails), 1)
        self.assertEqual(mails[0].path, "mojtaba.rozegar11@gmail.com")
        args = parse_qs(mails[0].query)
        self.assertIn("Selected Professional Trader Enquiry", args["subject"][0])
        self.assertIn("Risk management method", args["body"][0])
        self.assertIn("does not constitute selection", args["body"][0])

    def test_static_sitemap_is_complete_public_only(self):
        xml = (ROOT / "sitemap.xml").read_text("utf-8")
        root = ElementTree.fromstring(xml)
        self.assertEqual(root.tag, "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset")
        locs = [node.text for node in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
        self.assertEqual(len(locs), 14)
        self.assertEqual(len(locs), len(set(locs)))
        self.assertEqual(set(locs), {ORIGIN + p for p in PUBLIC_PATHS})
        self.assertFalse(any("checkout" in u or "status" in u or "?" in u for u in locs))

    def test_education_and_pro_trader_cannot_be_conflated(self):
        text = (ROOT / "selected-traders/index.html").read_text("utf-8").lower()
        self.assertIn("not automatic acceptance", text)
        self.assertIn("no customer deposits", text)
        self.assertIn("individual written appointment", text)
        self.assertIn("virtual", text)
        self.assertIn("profit share", text)
        self.assertIn("approved work-related expenses", text)


if __name__ == "__main__":
    unittest.main()
