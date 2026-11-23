"""Guard the deployed Moj Prop / native TRX buyer instructions from source regression.

Pure source inspections only. No network, customer, transaction, email, migration,
funding gate or backend configuration is changed by these tests.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAYMENT = ROOT / "templates/moj-prop/payment/index.html"
PAYMENT_V4 = ROOT / "templates/moj-prop-v4/payment/index.html"
TRX_HELP = ROOT / "templates/crypto-payments/index.html"


class CommercialPaymentCopyParityTests(unittest.TestCase):
    def test_payment_pages_keep_exact_deployed_safe_contract(self):
        for path in (PAYMENT, PAYMENT_V4):
            with self.subTest(path=path):
                page = path.read_text(encoding="utf-8")
                self.assertIn(
                    "Both Starter30 challenge and subsequent trading-account stages are simulated",
                    page,
                )
                self.assertNotIn(
                    "MOJ-PROP-01 and live funded accounts remain prelaunch",
                    page,
                )
                self.assertIn(
                    "unambiguous transaction-to-invoice attribution",
                    page,
                )
                self.assertIn(
                    "No customer should transfer TRX before a unique checkout invoice is issued",
                    page,
                )
                self.assertIn(
                    'href="/mojprop-starter30-checkout/"',
                    page,
                )

    def test_fixed_price_and_conditional_issuance_remain_clear(self):
        for path in (PAYMENT, PAYMENT_V4):
            with self.subTest(path=path):
                page = path.read_text(encoding="utf-8")
                self.assertIn("exact 30 TRX Starter30 invoice eligibility", page)
                self.assertIn(
                    "The Starter30 checkout form is visible, but invoice issuance requires",
                    page,
                )
                self.assertIn(
                    "Only a server-issued invoice can show the approved receive-only wallet",
                    page,
                )

    def test_trx_store_guide_does_not_claim_starter30_disabled(self):
        page = TRX_HELP.read_text(encoding="utf-8")
        self.assertIn(
            'href="/mojprop-starter30-checkout/"',
            page,
        )
        self.assertIn(
            "An invoice is conditional on identity and server-side payment checks",
            page,
        )
        self.assertNotIn(
            "while its official payment remains unavailable",
            page,
        )
        self.assertNotIn(
            "Do not transfer 30 TRX for Starter30",
            page,
        )

    def test_store_and_prop_remain_separate_checkouts(self):
        guide = TRX_HELP.read_text(encoding="utf-8")
        self.assertIn(
            "this payment guide concerns existing digital products in the MojPlayWin store only",
            guide,
        )
        self.assertIn(
            "not payable through this page",
            guide,
        )
        self.assertIn(
            "do not transfer TRX until that checkout issues your own unique invoice",
            guide,
        )


if __name__ == "__main__":
    unittest.main()
