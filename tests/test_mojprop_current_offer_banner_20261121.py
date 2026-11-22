"""Contract test for the current Starter30 conversion banner."""
from pathlib import Path
import unittest

PAGE = Path(__file__).resolve().parents[1] / "templates/moj-prop-v4/index.html"


class MojPropCurrentOfferBannerTest(unittest.TestCase):
    def test_current_starter30_offer_is_before_prelaunch_block(self):
        text = PAGE.read_text(encoding="utf-8")
        before_plan1 = text.split('<section class="section" id="mojprop01"', 1)[0]
        self.assertIn('id="starter30-current-offer"', before_plan1)
        self.assertIn("Starter30 — 60-day simulated challenge; listed entry fee 30 TRX", before_plan1)
        self.assertIn('href="/moj-prop/starter-30-trx/"', before_plan1)
        self.assertIn('href="/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=starter-30-trx&amp;utm_source=moj_prop&amp;utm_medium=onsite&amp;utm_campaign=starter30_lead&amp;utm_content=free_terms"', before_plan1)

    def test_obsolete_free_plan_is_absent_and_payment_remains_closed(self):
        text = PAGE.read_text(encoding="utf-8")
        self.assertNotIn("Plan 1 (free)", text)
        self.assertNotIn("MOJ-PROP-01", text)
        self.assertIn("payment and new enrollment are currently unavailable", text.lower())
        self.assertIn("do not send trx", text.lower())

    def test_meta_description_matches_30trx_conditional_virtual_scaling(self):
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn("Starter30: 30 TRX listed entry", text)
        self.assertIn("14-level virtual pathway to $100,000", text)
        self.assertIn("Payment unavailable.", text)


if __name__ == "__main__":
    unittest.main()
