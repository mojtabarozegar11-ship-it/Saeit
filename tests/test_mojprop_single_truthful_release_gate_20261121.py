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

    def test_landing_page_does_not_claim_open_paid_checkout(self):
        page = (ROOT / "templates" / "moj-prop-v4" / "index.html").read_text(encoding="utf-8")
        self.assertIn("payment admission currently on hold", page)
        self.assertIn("Do not send TRX", page)
        self.assertNotIn("pay only against the server-issued 30 TRX invoice", page)


if __name__ == "__main__":
    unittest.main()
