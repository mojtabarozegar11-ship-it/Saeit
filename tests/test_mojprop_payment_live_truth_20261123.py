"""Guard the customer-facing payment-status copy against stale or overbroad claims."""
from pathlib import Path
import unittest

PAYMENT = Path(__file__).resolve().parents[1] / "templates/moj-prop/payment/index.html"

class MojPropPaymentLiveTruthTests(unittest.TestCase):
    def test_seo_and_schema_repeat_conditional_checkout_status(self):
        text = PAYMENT.read_text(encoding="utf-8")
        phrase = (
            "The Starter30 checkout form is visible, but invoice issuance requires "
            "independent customer, receiving-wallet and reward-funding validation;"
        )
        self.assertEqual(text.count(phrase), 4)
        self.assertIn(
            "no transfer should be sent without a server-issued invoice.", text
        )

    def test_visible_payment_status_never_claims_unconditional_collectability(self):
        text = PAYMENT.read_text(encoding="utf-8")
        self.assertIn(
            "Current status:</b> The Starter30 checkout form is visible, "
            "but invoice issuance requires independent customer, "
            "receiving-wallet and reward-funding validation.", text
        )
        for stale in (
            "Starter30 secure checkout is open after email and payer-wallet verification.",
            "Starter30 payment is currently unavailable; no invoice is being issued",
            "automatic checkout, KYC, paid challenges and live accounts are not active.",
        ):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, text)
        self.assertIn(
            "Only a server-issued invoice can show the approved receive-only wallet.", text
        )

if __name__ == "__main__":
    unittest.main()
