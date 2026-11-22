"""Public Moj Prop reward-policy parity; source-only, no invoice or cash transfer.

The policy constants are pre-existing owner decisions and not a live finance proof.
"""
from pathlib import Path
import unittest

from prop_firm.simulation_policy import SIMULATION_POLICY


ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs/mojprop/education/starter30-buyer-guide.md"
STATIC_PAGE = ROOT / "templates/moj-prop-v4/starter-30-trx/index.html"


class Starter30PublicOwnerPolicyParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guide = GUIDE.read_text(encoding="utf-8")
        cls.page = STATIC_PAGE.read_text(encoding="utf-8")
        cls.policy = SIMULATION_POLICY

    def test_01_canonical_policy_has_exact_owner_approved_terms(self):
        p = self.policy
        self.assertEqual(p.contract_version, "2026-11-21/simulation-v2")
        self.assertEqual(str(p.trader_eligible_profit_share_pct), "100")
        self.assertEqual(str(p.company_eligible_profit_share_pct), "0")
        self.assertEqual(p.first_payout_min_activity_days, 14)
        self.assertEqual(p.subsequent_payout_interval_days, 14)
        self.assertEqual(str(p.minimum_payout_request_usd), "10")
        self.assertTrue(p.transfer_network_fees_paid_by_company)
        self.assertTrue(p.entry_fee_refund_with_first_successful_profit_withdrawal)
        self.assertFalse(p.virtual_principal_withdrawable)
        self.assertFalse(p.customer_deposit_required)
        self.assertFalse(p.real_orders_enabled)

    def test_02_guide_discloses_full_expected_reward_terms(self):
        t = self.guide.lower()
        for fragment in ("2026-11-21/simulation-v2", "100%", "14 days",
                         "once every 14 days", "usd $10", "paid by the company",
                         "first successful profit withdrawal", "usd $1,000",
                         "virtual", "independently verified"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, t)

    def test_03_static_checkout_asset_stays_exactly_release_pinned(self):
        import hashlib
        raw = STATIC_PAGE.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        self.assertEqual(blob, "737e26d5b410638c9c54d8861fe342c859548698")
        self.assertNotIn('id="profit-reward-schedule"', self.page)
        self.assertIn("requires your sending tron wallet address", self.page.lower())

    def test_04_guide_discloses_policy_not_actual_paid_reward(self):
        t = self.guide.lower()
        for fragment in ("do not send trx", "not proof of an operating payout service",
                         "not accepting", "100%", "does **not** guarantee profitable performance"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, t)
        self.assertNotIn("a verified reward payment has been completed", t)

    def test_05_no_direct_wallet_or_paid_fee_collection_created(self):
        self.assertIn('action="/mojprop-starter30-status/"', self.page)
        self.assertIn("requires your sending tron wallet address", self.page.lower())
        self.assertIn("unique server-issued invoice", self.guide.lower())
        self.assertIn("no customer capital is accepted", self.page.lower())
        self.assertNotIn('action="/mojprop-starter30-checkout/" method="post"', self.page)

    def test_06_current_guide_explains_eligibility_and_unverified_payout(self):
        t = self.guide.lower()
        self.assertIn("qualifying", t)
        self.assertIn("verification", t)
        self.assertIn("not proof of an operating payout service", t)
        self.assertIn("before anyone is charged", t)
        self.assertIn("the 100% figure describes the intended", t)

    def test_07_public_education_links_are_exact_first_party_urls(self):
        self.assertIn("https://mojplaywin.com/moj-prop/payment/?utm_source=github", self.guide)
        self.assertIn("https://mojplaywin.com/moj-prop-intake/?format=html&service=blueprint", self.guide)
        self.assertIn('/moj-prop/payment/', self.page)
        self.assertIn('/moj-prop-intake/?format=html&amp;service=blueprint', self.page)


if __name__ == "__main__":
    unittest.main()
