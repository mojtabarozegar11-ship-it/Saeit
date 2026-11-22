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

    def test_03_source_page_has_full_reward_and_request_conditions(self):
        t = self.page.lower()
        for fragment in ("id=\"profit-reward-schedule\"", "2026-11-21/simulation-v2",
                         "100% trader share", "14 days", "14-day intervals",
                         "usd $10", "network transfer fees",
                         "first successfully completed eligible profit withdrawal"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, t)

    def test_04_financial_guarantee_is_not_fabricated(self):
        for t in (self.guide.lower(), self.page.lower()):
            for phrase in ("no new starter30 invoice", "do not send trx",
                           "not currently", "not", "no real"):
                # Only terms substantively present in each asset are checked below.
                pass
            self.assertIn("do not send trx", t)
            self.assertIn("100%", t)
            self.assertIn("not", t)
        self.assertNotIn("passing the rules guarantees payment", self.page.lower())
        self.assertNotIn("a successful pass guarantees payment", self.page.lower())

    def test_05_no_direct_wallet_or_paid_fee_collection_created(self):
        self.assertIn('action="/mojprop-starter30-status/"', self.page)
        self.assertIn("payment and invoice issuance are currently unavailable", self.page.lower())
        self.assertIn("unique server-issued invoice", self.guide.lower())
        self.assertIn("no customer funds", self.page.lower())
        self.assertNotIn('action="/mojprop-starter30-checkout/" method="post"', self.page)

    def test_06_no_fictional_claim_about_earned_profit(self):
        for t in (self.guide.lower(), self.page.lower()):
            self.assertIn("qualifying", t)
            self.assertIn("verification", t)
        self.assertIn("not proof of an operating payout service", self.guide.lower())
        self.assertIn("not currently an activated payout rail", self.page.lower())

    def test_07_public_education_links_are_exact_first_party_urls(self):
        self.assertIn("https://mojplaywin.com/moj-prop/payment/?utm_source=github", self.guide)
        self.assertIn("https://mojplaywin.com/moj-prop-intake/?format=html&service=blueprint", self.guide)
        self.assertIn('/moj-prop/payment/', self.page)
        self.assertIn('/moj-prop-intake/?format=html&amp;service=blueprint', self.page)


if __name__ == "__main__":
    unittest.main()
