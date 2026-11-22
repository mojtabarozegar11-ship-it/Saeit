"""C89: keep the public Moj Prop status truthful and commercially safe.

A public visual badge must not imply that a live desk, funded account, or
payment route is active when the customer path is still manual review.
"""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SURFACES = (
    ROOT / "templates/moj-prop-v4/index.html",
    ROOT / "templates/moj-prop/index.html",
)


class MojPropTruthfulPublicStatusTests(unittest.TestCase):
    def test_every_public_moj_prop_surface_uses_review_status(self):
        for path in PUBLIC_SURFACES:
            with self.subTest(path=path):
                html = path.read_text(encoding="utf-8")
                self.assertNotIn("DESK ONLINE", html)
                if path == PUBLIC_SURFACES[0]:
                    # The English v4 offer is now listed at 30 TRX, but checkout
                    # remains gated. No obsolete Plan 1 or real funded capital.
                    self.assertIn("payment and new enrollment are currently unavailable", html.lower())
                    self.assertIn("do not send trx", html.lower())
                    self.assertNotIn("Plan 1 (free)", html)
                    self.assertIn("not withdrawable cash or real funded capital", html.lower())
                else:
                    # Historical public informational page retains its prior
                    # unchargeable manual-review warning unchanged.
                    self.assertIn("REQUEST REVIEW — NO PAYMENT", html)
                self.assertIn("No payment", html)
                self.assertIn("live account", html.lower())

    def test_v4_request_contract_remains_bound_to_manual_intake(self):
        html = PUBLIC_SURFACES[0].read_text(encoding="utf-8")
        self.assertIn("const endpoint='/moj-prop-intake/';", html)
        self.assertIn('<option value="urgent">', html)
        self.assertIn('<option value="week">', html)
        self.assertIn('<option value="month">', html)
        self.assertIn('<option value="review">', html)
        self.assertIn('id="consent"', html)
        self.assertIn("No payment was taken.", html)
        self.assertNotIn("mailto:", html.lower())

    def test_payment_page_does_not_publish_an_unbound_wallet_or_fake_receipt(self):
        html = (ROOT / "templates/moj-prop/payment/index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("No public TRX wallet address is displayed.", html)
        self.assertIn("written offer", html)
        self.assertNotIn("payment_verified", html)
        self.assertIn("does not create a confirmed order", html.lower())


if __name__ == "__main__":
    unittest.main()
