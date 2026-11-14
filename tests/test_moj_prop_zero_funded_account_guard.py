"""MOJ PROP $100 first-tier funding must never be bypassed by zero applicants."""
from django.test import SimpleTestCase
from core.tron_tenant_policy import TenantDecision
from prop_firm.challenge_commerce import assess_challenge_checkout, REQUIRED

class PropFundingBeforeFeesTests(SimpleTestCase):
    def merchant(self, host="mojplaywin.com", brand="moj_prop", verified=True):
        return TenantDecision("mojprop_merchant",host,brand,verified,())

    def assess(self, accounts=1, cash="100", reserves="0", tenant=None, **extra):
        return assess_challenge_checkout(
            merchant_tenant=tenant or self.merchant(),
            free_treasury_usd=cash,
            protected_reserves_usd=reserves,
            required_first_tier_accounts=accounts,
            attestations={k:True for k in REQUIRED},
            **extra,
        )

    def test_01_actual_one_hundred_cash_no_charges(self):
        d=self.assess()
        self.assertTrue(d.eligible_for_external_legal_review)
        self.assertFalse(d.checkout_enabled)
        self.assertFalse(d.invoice_created)
        self.assertFalse(d.trading_enabled)

    def test_02_zero_accounts_fails_closed(self):
        with self.assertRaises(ValueError):
            self.assess(accounts=0)

    def test_03_negative_accounts_rejected(self):
        with self.assertRaises(ValueError):
            self.assess(accounts=-1)

    def test_04_boolean_account_count_rejected(self):
        with self.assertRaises(ValueError):
            self.assess(accounts=True)

    def test_05_string_account_count_rejected(self):
        with self.assertRaises(ValueError):
            self.assess(accounts="1")

    def test_06_over_ten_thousand_refused(self):
        with self.assertRaises(ValueError):
            self.assess(accounts=10001)

    def test_07_two_accounts_need_two_hundred_cash(self):
        d=self.assess(accounts=2,cash="100")
        self.assertIn("real_initial_account_capital_shortfall",d.blockers)

    def test_08_reserve_is_separate_from_funding(self):
        d=self.assess(accounts=1,cash="100",reserves="10")
        self.assertFalse(d.eligible_for_external_legal_review)

    def test_09_no_money_no_sales_review(self):
        d=self.assess(cash="0")
        self.assertIn("real_initial_account_capital_shortfall",d.blockers)

    def test_10_unapproved_tenant_cannot_offer(self):
        d=self.assess(tenant=self.merchant(verified=False))
        self.assertIn("dedicated_moj_prop_tron_merchant_not_verified",d.blockers)

    def test_11_wrong_host_cannot_sell(self):
        d=self.assess(tenant=self.merchant(host="zomorodmelal.ir"))
        self.assertIn("dedicated_moj_prop_tron_merchant_not_verified",d.blockers)

    def test_12_signal_brand_cannot_sell_prop_challenge(self):
        d=self.assess(tenant=self.merchant(brand="saman"))
        self.assertIn("dedicated_moj_prop_tron_merchant_not_verified",d.blockers)

    def test_13_missing_legal_attestation_blocks(self):
        at={k:True for k in REQUIRED}
        del at["jurisdiction_authorized"]
        d=assess_challenge_checkout(
            merchant_tenant=self.merchant(),
            free_treasury_usd="100",
            protected_reserves_usd="0",
            attestations=at,
        )
        self.assertIn("jurisdiction_authorized",d.blockers)

    def test_14_provisional_eligibility_is_not_charge_permission(self):
        d=self.assess(cash="100000",accounts=3)
        self.assertFalse(d.checkout_enabled)
        self.assertFalse(d.invoice_created)
        self.assertFalse(d.trading_enabled)
