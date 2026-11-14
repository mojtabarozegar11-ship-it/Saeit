"""Multi-domain TRX rollout inventory; 37 scopes are not 37 deployed sites."""
from django.test import SimpleTestCase
from core.tron_rollout_inventory import (
    DISCOVERED_DOMAIN_ANCHORS, rollout_targets, inspect_rollout,
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


    def test_fully_approved_new_subdomain_is_included_once(self):
        reg = {
            ("signals.mojplaywin.com", "saman"): {
                "tenant_id": "new_signal_merchant", "network": CANONICAL_CHAIN,
                "asset": CANONICAL_ASSET,
                **{key: True for key in REQUIRED_ATTESTATIONS},
            },
        }
        result = inspect_rollout(
            registry=reg, extra_owned_domains=["signals.mojplaywin.com"],
        )
        self.assertEqual(result["logical_payment_scopes_not_hosts"], 38)
        self.assertEqual(result["additional_registered_site_hosts"], 1)
        new = [x for x in result["entries"]
               if x["host"] == "signals.mojplaywin.com"]
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0]["brand"], "saman")
        self.assertTrue(new[0]["eligible_for_adapter_review"])
        self.assertFalse(new[0]["checkout_enabled"])

    def test_new_host_without_merchant_registration_stays_excluded(self):
        result = inspect_rollout(extra_owned_domains=["signals.mojplaywin.com"])
        self.assertEqual(result["logical_payment_scopes_not_hosts"], 37)
        self.assertEqual(result["additional_registered_site_hosts"], 0)

    def test_new_subdomain_does_not_inherit_parent_wallet_scope(self):
        reg = {
            ("mojplaywin.com", "saman"): {
                "tenant_id": "main_signal_merchant", "network": CANONICAL_CHAIN,
                "asset": CANONICAL_ASSET,
                **{key: True for key in REQUIRED_ATTESTATIONS},
            },
        }
        result = inspect_rollout(
            registry=reg, extra_owned_domains=["signals.mojplaywin.com"],
        )
        self.assertEqual(result["additional_registered_site_hosts"], 0)

    def test_new_host_with_missing_attestation_stays_excluded(self):
        reg = {
            ("signals.mojplaywin.com", "saman"): {
                "tenant_id": "new_signal_merchant", "network": CANONICAL_CHAIN,
                "asset": CANONICAL_ASSET,
                **{key: True for key in REQUIRED_ATTESTATIONS},
                "network_settlement_verified": False,
            },
        }
        result = inspect_rollout(
            registry=reg, extra_owned_domains=["signals.mojplaywin.com"],
        )
        self.assertEqual(result["additional_registered_site_hosts"], 0)

    def test_new_host_with_unregistered_brand_stays_excluded(self):
        reg = {
            ("signals.mojplaywin.com", "notregistered"): {
                "tenant_id": "other_merchant", "network": CANONICAL_CHAIN,
                "asset": CANONICAL_ASSET,
                **{key: True for key in REQUIRED_ATTESTATIONS},
            },
        }
        result = inspect_rollout(
            registry=reg, extra_owned_domains=["signals.mojplaywin.com"],
        )
        self.assertEqual(result["additional_registered_site_hosts"], 0)

    def test_new_host_cannot_cross_duplicate_tenant_ids(self):
        merchant = {
            "tenant_id": "shared_danger", "network": CANONICAL_CHAIN,
            "asset": CANONICAL_ASSET,
            **{key: True for key in REQUIRED_ATTESTATIONS},
        }
        reg = {
            ("signals.mojplaywin.com", "saman"): merchant,
            ("mojplaywin.com", "saman"): merchant,
        }
        result = inspect_rollout(
            registry=reg, extra_owned_domains=["signals.mojplaywin.com"],
        )
        self.assertEqual(result["additional_registered_site_hosts"], 0)

    def test_identical_hosts_list_does_not_duplicate_merchant_routes(self):
        reg = {
            ("shop.mojplaywin.com", ""): {
                "tenant_id": "shop_merchant", "network": CANONICAL_CHAIN,
                "asset": CANONICAL_ASSET,
                **{key: True for key in REQUIRED_ATTESTATIONS},
            },
        }
        result = inspect_rollout(
            registry=reg,
            extra_owned_domains=["shop.mojplaywin.com", "shop.mojplaywin.com"],
        )
        self.assertEqual(result["logical_payment_scopes_not_hosts"], 38)
        self.assertEqual(result["additional_registered_site_hosts"], 1)

    def test_unowned_malformed_extra_hostname_fails_closed(self):
        with self.assertRaises(ValueError):
            inspect_rollout(extra_owned_domains=["https://evil.org"])
