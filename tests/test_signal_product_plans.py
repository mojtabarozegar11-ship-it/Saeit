"""Proposed signal subscriptions: one paid entitlement across brand mirrors."""
from django.test import SimpleTestCase
from core.signal_product_plans import (
    SIGNAL_PLANS, PROOF_REQUIRED, canonical_signal_product,
    subscription_review,
)
from core.tron_tenant_policy import registered_scope, REQUIRED_ATTESTATIONS


class SignalSubscriptionCommercialTests(SimpleTestCase):
    def tenant(self, approved=True, brand="saman"):
        info = {
            "tenant_id": "signal_saman",
            "network": "tron-mainnet", "asset": "TRX",
            **{k: approved for k in REQUIRED_ATTESTATIONS},
        }
        return registered_scope(
            host="mojplaywin.com", brand=brand,
            registry={("mojplaywin.com", brand): info},
        )

    def full_review(self, **changes):
        kw = {
            "tenant": self.tenant(),
            "proofs": {k: True for k in PROOF_REQUIRED},
        }
        kw.update(changes)
        return subscription_review(**kw)

    def test_three_distinct_proposed_price_tiers(self):
        self.assertEqual(len(SIGNAL_PLANS), 3)
        self.assertEqual([str(p.monthly_usd_proposed) for p in SIGNAL_PLANS],
                         ["12.00", "29.00", "59.00"])
        self.assertEqual([p.market_limit for p in SIGNAL_PLANS], [1, 3, 5])

    def test_no_published_price_or_automatic_bill(self):
        for p in SIGNAL_PLANS:
            self.assertFalse(p.auto_billing_enabled)
            self.assertFalse(p.paid_access_enabled)
            self.assertFalse(p.outcome_guaranteed)

    def test_all_brand_mirrors_share_one_canonical_entitlement(self):
        products = [
            canonical_signal_product("moj-signals-plus", brand)
            for brand in ("saman", "zahra", "taniya")
        ]
        self.assertEqual({p["entitlement_sku"] for p in products},
                         {"moj-signals-plus"})
        self.assertTrue(all(p["one_global_entitlement"] for p in products))

    def test_unknown_brand_or_product_blocked(self):
        with self.assertRaises(ValueError):
            canonical_signal_product("moj-signals-plus", "badbrand")
        with self.assertRaises(ValueError):
            canonical_signal_product("invented-product", "saman")

    def test_complete_proofs_do_not_start_customer_charges(self):
        x = self.full_review()
        self.assertTrue(x["eligible_for_external_review"])
        self.assertFalse(x["checkout_enabled"])
        self.assertFalse(x["auto_renewal_enabled"])
        self.assertFalse(x["signal_execution_enabled"])
        self.assertFalse(x["prices_are_live"])

    def test_each_missing_proof_blocks_subscription(self):
        for k in PROOF_REQUIRED:
            with self.subTest(key=k):
                evidence = {item: True for item in PROOF_REQUIRED}
                evidence.pop(k)
                x = self.full_review(proofs=evidence)
                self.assertFalse(x["eligible_for_external_review"])
                self.assertIn(k, x["missing"])

    def test_ungrounded_truthy_strings_are_not_approval(self):
        x = self.full_review(proofs={k: "yes" for k in PROOF_REQUIRED})
        self.assertEqual(len(x["missing"]), len(PROOF_REQUIRED))

    def test_unapproved_tron_merchant_blocks_subscription(self):
        x = self.full_review(tenant=self.tenant(approved=False))
        self.assertFalse(x["eligible_for_external_review"])
        self.assertIn("merchant_approval_missing", x["missing"])

    def test_moj_prop_tenant_cannot_sell_signal_subscriptions(self):
        with self.assertRaises(ValueError):
            self.full_review(tenant=self.tenant(brand="moj_prop"))

    def test_malformed_proof_rejected(self):
        with self.assertRaises(ValueError):
            self.full_review(proofs="approved")
