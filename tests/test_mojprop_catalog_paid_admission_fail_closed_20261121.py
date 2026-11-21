"""No unverified paid enrollment CTA may reappear on English MOJ PROP catalog."""
from pathlib import Path
import unittest

PAGE = Path(__file__).resolve().parents[1] / "templates/moj-prop-v4/catalog/index.html"
FREE = "/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=starter-30-trx"


class CatalogPaidAdmissionFailClosedTest(unittest.TestCase):
    def test_starter30_no_legacy_checkout_invitation(self):
        page = PAGE.read_text("utf-8")
        self.assertEqual(page.count('id="starter-30"'), 1)
        self.assertIn("payment admission under independent verification", page)
        self.assertIn("Ask for written eligibility and invoice conditions — free", page)
        self.assertIn(FREE, page)
        self.assertNotIn('href="/mojprop-starter30-checkout/"', page)
        self.assertIn("Pay only after the secure server issues an invoice", page)
        self.assertIn("no real broker connection", page)

    def test_catalog_retains_other_distinct_services(self):
        page = PAGE.read_text("utf-8")
        for service in ("prop-blueprint", "gold-market-brief",
                        "educational-signal", "commercial-gate-audit"):
            with self.subTest(service=service):
                self.assertIn("/moj-prop/samples/" + service + "/", page)
        self.assertIn('/moj-prop/starter-30-trx/', page)


if __name__ == "__main__":
    unittest.main()
