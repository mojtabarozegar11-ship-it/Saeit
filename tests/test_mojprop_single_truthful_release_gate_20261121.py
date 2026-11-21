"""Regression tests for one truthful Starter30 commercial state.

These source-level checks prevent a generic release switch from reopening the
public 30 TRX route without independent evidence gates.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MojPropSingleTruthfulReleaseGateTests(unittest.TestCase):
    def test_live_checkout_requires_independent_commercial_evidence(self):
        source = (ROOT / "prop_firm" / "starter30_live.py").read_text(encoding="utf-8")
        required = (
            "MPW_MOJPROP_SELLER_ELIGIBILITY_VERIFIED",
            "MPW_MOJPROP_INVOICE_CUSTODY_VERIFIED",
            "MPW_MOJPROP_REWARD_RESERVE_VERIFIED",
            "MPW_MOJPROP_REWARD_SETTLEMENT_RAIL_VERIFIED",
            "MPW_MOJPROP_DELIVERY_RECOVERY_VERIFIED",
        )
        for flag in required:
            self.assertIn(f'"{flag}"', source)

    def test_all_new_gates_default_closed(self):
        source = (ROOT / "config" / "settings.py").read_text(encoding="utf-8")
        required = (
            "MPW_MOJPROP_SELLER_ELIGIBILITY_VERIFIED",
            "MPW_MOJPROP_INVOICE_CUSTODY_VERIFIED",
            "MPW_MOJPROP_REWARD_RESERVE_VERIFIED",
            "MPW_MOJPROP_REWARD_SETTLEMENT_RAIL_VERIFIED",
            "MPW_MOJPROP_DELIVERY_RECOVERY_VERIFIED",
        )
        for flag in required:
            self.assertIn(f'env.bool(\n    "{flag}", default=False\n)', source)

    def test_closed_checkout_copy_does_not_invite_transfer(self):
        source = (ROOT / "prop_firm" / "starter30_views.py").read_text(encoding="utf-8")
        self.assertIn("Payment is not available at this moment", source)
        self.assertIn("This request does not issue an invoice, collect TRX, or open an account.", source)
        self.assertIn("No transfer should be sent", source)


if __name__ == "__main__":
    unittest.main()
