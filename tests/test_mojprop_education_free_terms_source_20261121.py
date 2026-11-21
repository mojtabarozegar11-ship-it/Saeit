"""English MOJ PROP educational intent routing; no customer POST or paid checkout."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "templates" / "moj-prop" / "education"
FREE = "/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=starter-30-trx"
DOCS = (
    ("index.html", "https://mojplaywin.com/moj-prop/education/"),
    ("drawdown-and-position-sizing/index.html", "https://mojplaywin.com/moj-prop/education/drawdown-and-position-sizing/"),
    ("simulated-versus-live/index.html", "https://mojplaywin.com/moj-prop/education/simulated-versus-live/"),
)


class EducationFreeTermsCTAContract(unittest.TestCase):
    def test_pages_offer_real_no_charge_starter30_enquiry(self):
        for rel, canonical in DOCS:
            with self.subTest(path=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                self.assertEqual(text.count("Request written terms free"), 1)
                self.assertEqual(text.count(FREE), 1)
                self.assertIn('href="/moj-prop/starter-30-trx/"', text)
                self.assertIn('href="/moj-prop/rules/"', text)
                self.assertIn(canonical, text)
                self.assertNotIn('href="/mojprop-starter30-checkout/"', text)
                self.assertNotIn('name="wallet"', text)

    def test_no_challenge_purchase_or_return_promise(self):
        for rel, _ in DOCS:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("Start secure 30 TRX checkout", text)
            self.assertNotIn("guaranteed monthly profit", text.lower())
            self.assertNotIn("<form method=\"post\"", text.lower())


if __name__ == "__main__":
    unittest.main()
