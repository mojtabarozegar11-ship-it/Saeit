"""TRON multitenant scope isolation without real payment or wallet operations."""
from django.test import SimpleTestCase
from core.tron_tenant_policy import (
    CANONICAL_CHAIN, CANONICAL_ASSET, REQUIRED_ATTESTATIONS,
    canonical_host, registered_scope, signed_routing_context,
    verify_signed_routing_context,
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

    def test_whitespace_smuggling_cannot_match_merchant_hostname(self):
        for candidate in (" mojplaywin.com", "mojplaywin.com ",
                          "\tmojplaywin.com", "mojplaywin.com\n"):
            with self.subTest(host=repr(candidate)), self.assertRaises(ValueError):
                canonical_host(candidate)

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

    def test_malformed_brand_collections_are_cleanly_denied(self):
        for forged in ([], {}, ["saman"], {"brand": "saman"}, 1, True, None):
            with self.subTest(value=repr(forged)), self.assertRaises(ValueError):
                self.match(brand=forged)

    def test_forged_truthy_routing_scope_never_issues_signed_context(self):
        from dataclasses import replace
        scope = self.match()
        for value in ("yes", 1, ["approved"]):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                signed_routing_context(
                    decision=replace(scope, eligible_for_checkout_review=value),
                    product_sku="book-72", key=TEST_KEY,
                )

    def test_unexpected_paid_or_invoice_flags_on_scope_are_denied(self):
        from dataclasses import replace
        scope = self.match()
        for value in ({"payment_enabled": True}, {"invoice_created": True}):
            with self.subTest(change=value), self.assertRaises(ValueError):
                signed_routing_context(
                    decision=replace(scope, **value),
                    product_sku="book-72", key=TEST_KEY,
                )

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


_UNSPECIFIED_CONTEXT = object()


class RoutingVerificationRegressionTests(SimpleTestCase):
    """Safety contract for source-authenticated multi-tenant TRX routing."""

    def setUp(self):
        self.registry = {("mojplaywin.com", ""): dict(MERCHANT)}
        self.decision = registered_scope(
            host="mojplaywin.com", registry=self.registry,
        )
        self.context = signed_routing_context(
            decision=self.decision, product_sku="book-72", key=TEST_KEY,
        )

    def verify(self, context=_UNSPECIFIED_CONTEXT, **changes):
        return verify_signed_routing_context(
            context=self.context if context is _UNSPECIFIED_CONTEXT else context,
            key=changes.pop("key", TEST_KEY),
            registry=changes.pop("registry", self.registry),
            **changes,
        )

    def test_valid_signed_routing_context_accepted_only_as_scope(self):
        self.assertTrue(self.verify())
        self.assertFalse(self.context["is_invoice"])
        self.assertFalse(self.context["is_paid"])
        self.assertFalse(self.context["checkout_enabled"])

    def test_signature_tampering_denied(self):
        self.assertFalse(self.verify({**self.context, "routing_digest": "0" * 64}))

    def test_non_ascii_and_malformed_hmac_are_cleanly_rejected(self):
        for digest in ("é" * 64, "x" * 64, "A" * 64, "0" * 63, "0" * 65):
            with self.subTest(digest=digest[:8]):
                self.assertFalse(self.verify({
                    **self.context, "routing_digest": digest,
                }))

    def test_product_sku_tampering_denied(self):
        self.assertFalse(self.verify({**self.context, "product_sku": "book-225"}))

    def test_brand_tampering_denied(self):
        self.assertFalse(self.verify({**self.context, "brand": "saman"}))

    def test_tenant_identity_tampering_denied(self):
        self.assertFalse(self.verify({**self.context, "tenant_id": "other"}))

    def test_host_tampering_denied(self):
        self.assertFalse(self.verify({**self.context, "domain": "www.mojplaywin.com"}))

    def test_external_host_spoof_denied(self):
        self.assertFalse(self.verify({**self.context, "domain": "mojplaywin.com.attacker.com"}))

    def test_other_chain_denied(self):
        self.assertFalse(self.verify({**self.context, "network": "tron-testnet"}))
        self.assertFalse(self.verify({**self.context, "asset": "USDT"}))

    def test_payment_flags_cannot_be_promoted(self):
        for flag in ("is_invoice", "is_paid", "checkout_enabled"):
            for value in (True, 0, None, "false"):
                with self.subTest(flag=flag, value=value):
                    self.assertFalse(self.verify({**self.context, flag: value}))

    def test_extra_payload_fields_denied(self):
        self.assertFalse(self.verify({**self.context, "destination_address": "fake"}))

    def test_missing_payload_fields_denied(self):
        value = dict(self.context)
        value.pop("routing_digest")
        self.assertFalse(self.verify(value))

    def test_no_registry_denied(self):
        self.assertFalse(self.verify(registry=None))
        self.assertFalse(self.verify(registry={}))

    def test_revoked_attestation_invalidates_previous_signature(self):
        registry = {("mojplaywin.com", ""): {
            **MERCHANT, "custody_control_verified": False,
        }}
        self.assertFalse(self.verify(registry=registry))

    def test_rotated_tenant_id_invalidates_old_signature(self):
        registry = {("mojplaywin.com", ""): {
            **MERCHANT, "tenant_id": "replacement_merchant",
        }}
        self.assertFalse(self.verify(registry=registry))

    def test_rotated_signing_key_invalidates_old_signature(self):
        self.assertFalse(self.verify(key="another-private-merchant-signing-key-example"))

    def test_malformed_data_denied(self):
        for payload in (None, [], "invalid", {}, {"routing_digest": "x"}):
            with self.subTest(payload=payload):
                self.assertFalse(self.verify(payload))


class CrossTenantIsolationTests(SimpleTestCase):
    def test_duplicate_tenant_id_on_www_alias_is_not_a_separate_merchant(self):
        reg = {
            ("mojplaywin.com", ""): dict(MERCHANT),
            ("www.mojplaywin.com", ""): dict(MERCHANT),
        }
        result = registered_scope(host="mojplaywin.com", registry=reg)
        self.assertFalse(result.eligible_for_checkout_review)
        self.assertIn("duplicate_tenant_id", result.missing)
        other = registered_scope(host="www.mojplaywin.com", registry=reg)
        self.assertFalse(other.eligible_for_checkout_review)

    def test_duplicate_id_across_signal_brand_and_prop_is_rejected(self):
        reg = {
            ("mojplaywin.com", "saman"): {**MERCHANT, "tenant_id": "brand_reused"},
            ("mojplaywin.com", "moj_prop"): {**MERCHANT, "tenant_id": "brand_reused"},
        }
        first = registered_scope(host="mojplaywin.com", brand="saman", registry=reg)
        second = registered_scope(host="mojplaywin.com", brand="moj_prop", registry=reg)
        self.assertFalse(first.eligible_for_checkout_review)
        self.assertFalse(second.eligible_for_checkout_review)

    def test_separate_unique_ids_remain_eligible_only_for_review(self):
        reg = {
            ("mojplaywin.com", "saman"): {**MERCHANT, "tenant_id": "brand_saman"},
            ("mojplaywin.com", "moj_prop"): {**MERCHANT, "tenant_id": "prop_firm"},
        }
        for brand in ("saman", "moj_prop"):
            with self.subTest(brand=brand):
                result = registered_scope(host="mojplaywin.com", brand=brand, registry=reg)
                self.assertTrue(result.eligible_for_checkout_review)
                self.assertFalse(result.payment_enabled)
                self.assertFalse(result.invoice_created)

    def test_malformed_registry_entry_halts_checkout_review(self):
        reg = {
            ("mojplaywin.com", ""): dict(MERCHANT),
            ("other.invalid", ""): "not-a-merchant-object",
        }
        result = registered_scope(host="mojplaywin.com", registry=reg)
        self.assertIn("malformed_tenant_registry", result.missing)
        self.assertFalse(result.eligible_for_checkout_review)

    def test_registry_denies_oversized_unreconciled_tenant_map(self):
        reg = {("mojplaywin.com", ""): dict(MERCHANT)}
        reg.update({
            (f"store{i}.mojplaywin.com", ""): {
                **MERCHANT, "tenant_id": f"store_{i}"
            }
            for i in range(4096)
        })
        result = registered_scope(host="mojplaywin.com", registry=reg)
        self.assertIn("tenant_registry_too_large", result.missing)
        self.assertFalse(result.eligible_for_checkout_review)
