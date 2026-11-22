"""Executable source guard for the owner-approved, five-page English MOJ PROP offer.

Zero network, zero live buyer POST, zero database operations.
The English home free-terms change was deployed and backed up separately.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FREE = "/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=starter-30-trx"
PRODUCT = ROOT / "templates/moj-prop-v4/starter-30-trx/index.html"
EDUCATIONAL = (
    "risk-management",
    "sixty-day-simulated-challenge",
    "best-day-consistency",
)


class EnglishFreeTermsSourceParityTests(unittest.TestCase):
    def test_product_does_not_invite_unverified_invoice_or_trx_payment(self):
        content = PRODUCT.read_text(encoding="utf-8")
        self.assertIn("Request free written Starter30 terms", content)
        self.assertIn("Get written Starter30 conditions — free", content)
        self.assertIn("secure 30 TRX checkout", content)
        self.assertIn("payer-wallet verification", content)
        self.assertIn("single owner-approved receive-only wallet", content)
        self.assertIn(FREE, content)
        self.assertIn(">Open secure 30 TRX checkout</a>", content)
        self.assertIn('href="/mojprop-starter30-checkout/"', content)
        self.assertNotIn("payment admission under independent verification", content)

    def test_education_articles_route_reader_to_free_precise_offer(self):
        for slug in EDUCATIONAL:
            with self.subTest(slug=slug):
                doc = ROOT / "templates/moj-prop/education" / slug / "index.html"
                content = doc.read_text(encoding="utf-8")
                self.assertEqual(content.count("Request written terms free"), 1)
                self.assertEqual(content.count(FREE), 1)
                self.assertIn("/moj-prop/starter-30-trx/", content)
                self.assertIn("/moj-prop/rules/", content)
                self.assertNotIn('href="/mojprop-starter30-checkout/"', content)

    def test_all_public_offer_pages_keep_canonical_public_urls(self):
        paths = [
            PRODUCT,
            *[ROOT / "templates/moj-prop/education" / slug / "index.html"
              for slug in EDUCATIONAL],
        ]
        for path in paths:
            with self.subTest(path=path.name):
                txt = path.read_text(encoding="utf-8")
                self.assertIn('<link rel="canonical"', txt)
                self.assertIn("mojplaywin.com/moj-prop/", txt)


    def test_english_home_primary_free_terms_cta_matches_public_release(self):
        page = ROOT / "templates/moj-prop-v4/index.html"
        text = page.read_text(encoding="utf-8")
        self.assertIn("Request written terms — free", text)
        self.assertIn("listed entry fee 30 TRX", text)
        self.assertIn("real company-funded reward-settlement controls", text)
        self.assertIn(FREE, text)
        self.assertNotIn('>Open secure 30 TRX checkout</a>', text)
        self.assertNotIn('>Go to secure 30 TRX checkout</a>', text)
        self.assertIn('href="/moj-prop/rules/">Read the published Starter30 rules</a>', text)


if __name__ == "__main__":
    unittest.main()
