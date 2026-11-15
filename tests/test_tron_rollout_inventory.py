"""Multi-domain TRX rollout inventory; 37 scopes are not 37 deployed sites."""
from django.test import SimpleTestCase
from core.tron_rollout_inventory import (
    DISCOVERED_DOMAIN_ANCHORS, rollout_targets, inspect_rollout,
    inspect_explicit_site_expansion,
)
from core.tron_tenant_policy import (
    CANONICAL_ASSET, CANONICAL_CHAIN, REQUIRED_ATTESTATIONS,
)


class RolloutCoverageTests(SimpleTestCase):
    def test_only_two_grounded_site_domains(self):
        self.assertEqual(DISCOVERED_DOMAIN_ANCHORS, ("mojplaywin.com", "zomorodmelal.ir"))

    def test_exactly_thirty_seven_logical_payment_scopes(self):
        self.assertEqual(len(rollout_targets()), 37)
        self.assertEqual(len(set((x["host"], x["brand"]) for x in rollout_targets())), 37)

    def test_signal_brands_covered_on_both_real_site_hosts(self):
        scopes = rollout_targets()
        for host in DISCOVERED_DOMAIN_ANCHORS:
            self.assertEqual(
                len([x for x in scopes if x["host"] == host and x["section"] == "market_signal_subscription"]),
                17,
            )

    def test_moj_prop_is_first_priority_not_following_books(self):
        scopes = rollout_targets()
        self.assertEqual(scopes[0]["section"], "prop_trader_challenge")
        self.assertEqual(scopes[0]["priority"], 1)
        self.assertTrue(all(a["priority"] <= b["priority"] for a,b in zip(scopes, scopes[1:])))

    def test_all_scopes_unavailable_without_trusted_registry(self):
        data = inspect_rollout()
        self.assertFalse(data["live_gateway_connected"])
        self.assertEqual(data["logical_payment_scopes_not_hosts"], 37)
        self.assertTrue(all(not item["eligible_for_adapter_review"] for item in data["entries"]))
        self.assertTrue(all(not item["checkout_enabled"] for item in data["entries"]))

    def test_singly_approved_scope_does_not_activate_other_scopes(self):
        reg = {
            ("mojplaywin.com", "moj_prop"): {
                "tenant_id": "moj_prop", "network": CANONICAL_CHAIN,
                "asset": CANONICAL_ASSET,
                **{key: True for key in REQUIRED_ATTESTATIONS},
            }
        }
        result = inspect_rollout(reg)
        eligible = [r for r in result["entries"] if r["eligible_for_adapter_review"]]
        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0]["brand"], "moj_prop")
        self.assertFalse(eligible[0]["checkout_enabled"])

    def test_only_canonical_agent_is_branded(self):
        d = inspect_rollout()
        self.assertEqual(d["trading_bot"], "mojtaba.bot.ai")
        self.assertEqual(d["excluded_instagram_profile"], "Dr.mojtaba.rozegar")

    def test_extra_unverified_domains_not_silently_enumerated(self):
        data = inspect_rollout(extra_owned_domains=["additional-verified.com"])
        self.assertEqual(data["known_canonical_site_domains"], 2)
        self.assertEqual(data["logical_payment_scopes_not_hosts"], 37)

    def test_wrong_extra_domain_type_rejected(self):
        with self.assertRaises(ValueError):
            inspect_rollout(extra_owned_domains="rogue.com")

    def test_main_store_is_not_automatically_moj_prop_merchant(self):
        data = inspect_rollout()
        main = [x for x in data["entries"] if x["host"] == "mojplaywin.com" and x["brand"] == ""]
        prop = [x for x in data["entries"] if x["brand"] == "moj_prop"]
        self.assertEqual(len(main), 1)
        self.assertEqual(len(prop), 1)
        self.assertNotEqual(main[0]["section"], prop[0]["section"])

    def test_explicit_third_host_expands_inventory_without_enabling_billing(self):
        result = inspect_explicit_site_expansion(
            merchant_registry={}, approved_site_hosts=["shop.example.org"],
        )
        self.assertEqual(result["logical_payment_scopes_not_hosts"], 55)
        third = [x for x in result["entries"] if x["host"] == "shop.example.org"]
        self.assertEqual(len(third), 18)
        self.assertEqual(len([x for x in third if x["section"] == "market_signal_subscription"]), 17)
        self.assertTrue(all(not x["checkout_enabled"] for x in third))
        self.assertTrue(all(not x["eligible_for_adapter_review"] for x in third))
        self.assertTrue(all(not x["domain_live_independently_verified"] for x in third))

    def test_explicit_subdomain_does_not_inherit_parent_merchant(self):
        registry = {("mojplaywin.com", ""): {
            "tenant_id": "main", "network": CANONICAL_CHAIN,
            "asset": CANONICAL_ASSET,
            **{key: True for key in REQUIRED_ATTESTATIONS},
        }}
        result = inspect_explicit_site_expansion(
            merchant_registry=registry,
            approved_site_hosts=["play.mojplaywin.com"],
        )
        sub = [x for x in result["entries"] if x["host"] == "play.mojplaywin.com"]
        self.assertEqual(len(sub), 18)
        self.assertTrue(all(not x["eligible_for_adapter_review"] for x in sub))
        self.assertFalse(result["live_gateway_connected"])

    def test_registered_new_host_without_independent_site_proof_stays_blocked(self):
        registry = {("shop.example.org", ""): {
            "tenant_id": "example_store", "network": CANONICAL_CHAIN,
            "asset": CANONICAL_ASSET,
            **{key: True for key in REQUIRED_ATTESTATIONS},
        }}
        result = inspect_explicit_site_expansion(
            merchant_registry=registry,
            approved_site_hosts=["shop.example.org"],
        )
        third = [x for x in result["entries"] if x["host"] == "shop.example.org"]
        self.assertEqual(sum(x["eligible_for_adapter_review"] for x in third), 0)
        self.assertTrue(all(
            "site_ownership_dns_tls_or_merchant_proof_missing" in x["missing"]
            for x in third
        ))
        self.assertTrue(all(not x["checkout_enabled"] for x in third))

    def test_new_host_requires_exact_independent_site_proof_and_exact_merchant(self):
        registry = {("shop.example.org", ""): {
            "tenant_id": "example_store", "network": CANONICAL_CHAIN,
            "asset": CANONICAL_ASSET,
            **{key: True for key in REQUIRED_ATTESTATIONS},
        }}
        proof = {
            "ownership_verified": True, "dns_verified": True,
            "tls_verified": True, "merchant_host_approved": True,
        }
        for key in proof:
            invalid = {**proof, key: "yes"}
            with self.subTest(missing=key):
                result = inspect_explicit_site_expansion(
                    merchant_registry=registry, approved_site_hosts=["shop.example.org"],
                    verified_host_attestations={"shop.example.org": invalid},
                )
                third = [x for x in result["entries"] if x["host"] == "shop.example.org"]
                self.assertFalse(any(x["eligible_for_adapter_review"] for x in third))
        result = inspect_explicit_site_expansion(
            merchant_registry=registry, approved_site_hosts=["shop.example.org"],
            verified_host_attestations={"shop.example.org": proof},
        )
        third = [x for x in result["entries"] if x["host"] == "shop.example.org"]
        self.assertEqual(sum(x["eligible_for_adapter_review"] for x in third), 1)
        self.assertTrue(any(x["brand"] == "" and x["eligible_for_adapter_review"] for x in third))
        self.assertTrue(all(not x["checkout_enabled"] for x in third))
        self.assertTrue(all(x["domain_live_independently_verified"] for x in third))

    def test_new_host_attestation_shape_rejects_extra_keys_and_forged_types(self):
        for registry in (True, "yes", (), ["yes"]):
            with self.subTest(registry=registry), self.assertRaises(ValueError):
                inspect_explicit_site_expansion(
                    merchant_registry={}, approved_site_hosts=["shop.example.org"],
                    verified_host_attestations=registry,
                )
        evidence = {
            "ownership_verified": True, "dns_verified": True,
            "tls_verified": True, "merchant_host_approved": True, "unsafe": True,
        }
        result = inspect_explicit_site_expansion(
            merchant_registry={}, approved_site_hosts=["shop.example.org"],
            verified_host_attestations={"shop.example.org": evidence},
        )
        third = [x for x in result["entries"] if x["host"] == "shop.example.org"]
        self.assertTrue(all(not x["domain_live_independently_verified"] for x in third))

    def test_extra_host_inputs_are_bounded_unique_and_canonical(self):
        for hosts in ("shop.example.org", ["mojplaywin.com"],
                      ["new.example.org"] * 2, ["https://shop.example.org"],
                      ["site%d.example.org" % i for i in range(101)]):
            with self.subTest(hosts=repr(hosts)[:30]), self.assertRaises(ValueError):
                inspect_explicit_site_expansion(
                    merchant_registry={}, approved_site_hosts=hosts,
                )
        with self.assertRaises(ValueError):
            inspect_explicit_site_expansion(
                merchant_registry=None, approved_site_hosts=["shop.example.org"],
            )
