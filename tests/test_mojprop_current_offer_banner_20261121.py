"""Contract test for the current Starter30 conversion banner."""
from pathlib import Path
import unittest

PAGE = Path(__file__).resolve().parents[1] / "templates/moj-prop-v4/index.html"


class MojPropCurrentOfferBannerTest(unittest.TestCase):
    def test_current_starter30_offer_is_before_prelaunch_block(self):
        text = PAGE.read_text(encoding="utf-8")
        before_plan1 = text.split('<section class="section" id="mojprop01"', 1)[0]
        self.assertIn('id="starter30-current-offer"', before_plan1)
        self.assertIn("Current commercial route: Starter30", before_plan1)
        self.assertIn('href="/moj-prop/starter-30-trx/"', before_plan1)
        self.assertIn('href="/mojprop-starter30-checkout/"', before_plan1)

    def test_legal_prelaunch_disclosure_remains_present(self):
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn("MOJ-PROP-01", text)
        self.assertIn("Prelaunch only.", text)
        self.assertIn("Do not send money today.", text)

    def test_meta_description_matches_current_offer(self):
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn(
            "Moj Prop English Starter30: a 60-day simulated trading challenge",
            text,
        )
        self.assertIn("MOJ-PROP-01 remains prelaunch.", text)


if __name__ == "__main__":
    unittest.main()
