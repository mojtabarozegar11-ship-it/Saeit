"""TRON multitenant scope isolation without real payment or wallet operations."""
from django.test import SimpleTestCase
from core.tron_tenant_policy import (
    CANONICAL_CHAIN, CANONICAL_ASSET, REQUIRED_ATTESTATIONS,
    canonical_host, registered_scope, signed_routing_context,
)

TEST_KEY = "development-only-internal-scope-key-should-not-be-reused"
MERCHANT = {
    "tenant_id": "mojplaywin_main",
    "network": CANONICAL_CHAIN,
    "asset": CANONICAL_ASSET,
    **{key: True for key in REQUIRED_ATTESTATIONS},
}


class TronMultiTenantTests(SimpleTestCase):
    def match(self, *, host="mojplaywin.com", brand="", registry=None, anchors=None):
        x = {("mojplaywin.com", ""): MERCHANT} if registry is None else registry
        return registered_scope(host=host, brand=brand, registry=x, allowed_anchors=anchors)

    def test_exact_registered_main_domain_eligible_for_review(self):
        result = self.match()
        self.assertTrue(result.eligible_for_checkout_review)
        self.assertEqual(result.tenant_id, "mojplaywin_main")
        self.assertFalse(result.payment_enabled)
        self.assertFalse(result.invoice_created)

    def test_subdomain_has_no_inherited_parent_payment_rights(self):
        result = self.match(host="shop.mojplaywin.com")
        self.assertFalse(result.eligible_for_checkout_review)

    def test_www_is_separate_tenant_not_auto_authorized(self):
        self.assertFalse(self.match(host="www.mojplaywin.com").eligible_for_checkout_review)

    def test_other_brand_on_same_site_is_isolated(self):
        self.assertFalse(self.match(brand="saman").eligible_for_checkout_review)
        reg = {("mojplaywin.com", "saman"): {
            **MERCHANT, "tenant_id": "saman_brand",
        }}
        result = self.match(brand="saman", registry=reg)
        self.assertTrue(result.eligible_for_checkout_review)
        self.assertEqual(result.tenant_id, "saman_brand")

    def test_zomorod_domain_needs_separate_merchant(self):
        self.assertFalse(self.match(host="zomorodmelal.ir").eligible_for_checkout_review)

    def test_host_suffix_spoofing_is_not_owned(self):
        for host in (
            "mojplaywin.com.evil.net", "evilmojplaywin.com",
            "zomorodmelal.ir.attacker.org",
        ):
            with self.subTest(host=host):
                self.assertFalse(self.match(host=host).eligible_for_checkout_review)

    def test_untrusted_host_and_scheme_rejected(self):
        for value in ("https://mojplaywin.com", "mojplaywin.com:443",
                      "mojplaywin.com/path", "mojplaywin.com.",
                      "", "site..mojplaywin.com", "موج.com"):
            with self.subTest(host=value), self.assertRaises(ValueError):
                canonical_host(value)

    def test_approved_registered_subdomain_is_allowed_by_exact_match(self):
        registry = {("shop.mojplaywin.com", ""): {
            **MERCHANT, "tenant_id": "separate_shop",
        }}
        x = self.match(host="shop.mojplaywin.com", registry=registry)
        self.assertTrue(x.eligible_for_checkout_review)
        self.assertEqual(x.tenant_id, "separate_shop")

    def test_explicit_additional_parent_domain_requires_approval(self):
        registry = {("new-example.org", ""): {**MERCHANT, "tenant_id": "site_2"}}
        self.assertFalse(self.match(host="new-example.org", registry=registry).eligible_for_checkout_review)
        x = self.match(host="new-example.org", registry=registry,
                       anchors=("mojplaywin.com","new-example.org"))
        self.assertTrue(x.eligible_for_checkout_review)

    def test_no_registry_never_becomes_enabled(self):
        z = registered_scope(host="mojplaywin.com")
        self.assertFalse(z.eligible_for_checkout_review)
        self.assertIn("tenant_registry_missing", z.missing)

    def test_unknown_brand_rejected(self):
        with self.assertRaises(ValueError):
            self.match(brand="hacker")

    def test_all_required_attestations_must_be_literal_true(self):
        for key in REQUIRED_ATTESTATIONS:
            with self.subTest(key=key):
                payload = {**MERCHANT, key: 1}
                x = self.match(registry={("mojplaywin.com", ""): payload})
                self.assertFalse(x.eligible_for_checkout_review)
                self.assertIn(key, x.missing)

    def test_trx_not_usdt_or_other_chain(self):
        for change in ({"network": "tron-testnet"}, {"asset": "USDT"},
                       {"network": "solana-mainnet"}):
            with self.subTest(change=change):
                x = self.match(registry={("mojplaywin.com", ""): {**MERCHANT, **change}})
                self.assertFalse(x.eligible_for_checkout_review)

    def test_valid_routing_scope_is_not_payment(self):
        out = signed_routing_context(decision=self.match(), product_sku="book-72", key=TEST_KEY)
        self.assertEqual(out["network"], "tron-mainnet")
        self.assertEqual(out["asset"], "TRX")
        self.assertFalse(out["checkout_enabled"])
        self.assertFalse(out["is_invoice"])
        self.assertFalse(out["is_paid"])
        self.assertEqual(len(out["routing_digest"]), 64)

    def test_separate_tenants_have_separate_hmac_proofs(self):
        first = signed_routing_context(decision=self.match(), product_sku="book-72", key=TEST_KEY)
        other_registry = {("mojplaywin.com", "saman"): {
            **MERCHANT, "tenant_id": "saman_brand",
        }}
        second = signed_routing_context(
            decision=self.match(brand="saman", registry=other_registry),
            product_sku="book-72", key=TEST_KEY,
        )
        self.assertNotEqual(first["routing_digest"], second["routing_digest"])

    def test_sku_changes_hmac_digest(self):
        a = signed_routing_context(decision=self.match(), product_sku="book-72", key=TEST_KEY)
        b = signed_routing_context(decision=self.match(), product_sku="book-225", key=TEST_KEY)
        self.assertNotEqual(a["routing_digest"], b["routing_digest"])

    def test_invalid_skus_and_weak_keys_rejected(self):
        for sku in ("../invoice", "", "x"*121, "a b"):
            with self.subTest(sku=sku), self.assertRaises(ValueError):
                signed_routing_context(decision=self.match(), product_sku=sku, key=TEST_KEY)
        with self.assertRaises(ValueError):
            signed_routing_context(decision=self.match(), product_sku="book-72", key="short")

    def test_unapproved_tenant_cannot_get_signed_scope(self):
        with self.assertRaises(ValueError):
            signed_routing_context(
                decision=self.match(registry={}), product_sku="book-72", key=TEST_KEY
            )
