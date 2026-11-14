"""Every catalog offer has differentiated, public nonbinding delivery terms."""
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from mojtaba_revenue_portfolio import OFFERS


class OfferBriefContracts(unittest.TestCase):
    def test_every_offer_has_service_specific_document(self):
        for code in OFFERS:
            with self.subTest(code=code):
                filename = ROOT / "docs/revenue-p0/cycle2/offers" / (code + ".md")
                self.assertTrue(filename.is_file())
                text = filename.read_text(encoding="utf-8")
                self.assertGreater(len(text), 550)
                self.assertIn("Offer ID:** " + code, text)
                self.assertIn("## Bounded intake", text)
                self.assertIn("## Proposed deliverable", text)
                self.assertIn("## Acceptance and verification", text)
                self.assertIn("mojtaba.bot.ai", text)
                self.assertIn("INQUIRY-ONLY", text)

    def test_proposed_items_not_claimed_live(self):
        for code in ("digital_publication", "game_license", "trading_education"):
            t = (ROOT / "docs/revenue-p0/cycle2/offers" / (code + ".md")).read_text()
            self.assertIn("NOT A CONTRACT", t)
            self.assertIn("not", t.lower())

    def test_no_source_offer_has_generic_unknown_domain(self):
        for code, offer in OFFERS.items():
            self.assertIn(offer.domain, {"mojplaywin.com", "zomorodmelal.ir"})
            self.assertNotIn("new.bot", str(offer))


if __name__ == "__main__":
    unittest.main()
