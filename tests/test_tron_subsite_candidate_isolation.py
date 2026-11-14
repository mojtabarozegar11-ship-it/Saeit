"""Tenant-scoped TRX rollout: candidate subsites are not silently pay-enabled."""
from django.test import SimpleTestCase
from core.tron_rollout_inventory import (
    rollout_targets, inspect_rollout, DISCOVERED_DOMAIN_ANCHORS,
)
from core.tron_tenant_policy import CANONICAL_ASSET, CANONICAL_CHAIN, REQUIRED_ATTESTATIONS

class SubsiteIsolationTests(SimpleTestCase):
    SUB = "shop.mojplaywin.com"

    def approved(self, host, brand=""):
        return {(host, brand): {
            "tenant_id": "site_tenant_qualified", "network": CANONICAL_CHAIN,
            "asset": CANONICAL_ASSET,
            **{k: True for k in REQUIRED_ATTESTATIONS},
        }}

    def test_01_default_stays_37_logical_scopes(self):
        self.assertEqual(len(rollout_targets()),37)

    def test_02_specific_subsite_is_enumerated(self):
        self.assertEqual(len(rollout_targets([self.SUB])),55)

    def test_03_subsite_has_17_brand_mirrors(self):
        rows=rollout_targets([self.SUB])
        self.assertEqual(len([r for r in rows if r["host"]==self.SUB and r["brand"]]),17)

    def test_04_duplicate_and_canonical_parent_excluded(self):
        rows=rollout_targets([self.SUB,self.SUB,"mojplaywin.com"])
        self.assertEqual(len(rows),55)

    def test_05_unknown_external_tld_is_not_trusted(self):
        x=inspect_rollout(extra_owned_domains=["unknown-other.example"])
        self.assertEqual(x["logical_payment_scopes_not_hosts"],37)
        self.assertTrue(x["unverified_external_hosts_never_trusted"])

    def test_06_unregistered_subsite_is_never_checkout_enabled(self):
        x=inspect_rollout(extra_owned_domains=[self.SUB])
        rows=[r for r in x["entries"] if r["host"]==self.SUB]
        self.assertEqual(len(rows),18)
        self.assertTrue(all(not r["eligible_for_adapter_review"] for r in rows))
        self.assertTrue(all(not r["checkout_enabled"] for r in rows))

    def test_07_exact_subsite_approval_is_tenant_only(self):
        x=inspect_rollout(registry=self.approved(self.SUB),
                          extra_owned_domains=[self.SUB])
        eligible=[r for r in x["entries"] if r["eligible_for_adapter_review"]]
        self.assertEqual(len(eligible),1)
        self.assertEqual(eligible[0]["host"],self.SUB)
        self.assertEqual(eligible[0]["brand"],"")
        self.assertFalse(eligible[0]["checkout_enabled"])

    def test_08_other_brand_not_inherited_from_subsite(self):
        x=inspect_rollout(registry=self.approved(self.SUB),
                          extra_owned_domains=[self.SUB])
        self.assertTrue(all(not r["eligible_for_adapter_review"]
            for r in x["entries"] if r["brand"]))

    def test_09_sibling_host_cannot_borrow_approval(self):
        x=inspect_rollout(registry=self.approved(self.SUB),
            extra_owned_domains=[self.SUB,"other.mojplaywin.com"])
        eligible=[r for r in x["entries"] if r["eligible_for_adapter_review"]]
        self.assertEqual(len(eligible),1)
        self.assertEqual(eligible[0]["host"],self.SUB)

    def test_10_extra_host_malformed_rejected(self):
        with self.assertRaises(ValueError):
            inspect_rollout(extra_owned_domains=["https://shop.mojplaywin.com"])

    def test_11_more_than_64_candidates_rejected(self):
        with self.assertRaises(ValueError):
            inspect_rollout(extra_owned_domains=[
                f"b{i}.mojplaywin.com" for i in range(65)
            ])

    def test_12_noncollection_rejected(self):
        with self.assertRaises(ValueError):
            inspect_rollout(extra_owned_domains=self.SUB)

    def test_13_user_claim_of_external_host_not_enough(self):
        x=inspect_rollout(
            registry=self.approved("rogue.example"),
            extra_owned_domains=["rogue.example"],
        )
        self.assertFalse(any(r["host"]=="rogue.example" for r in x["entries"]))

    def test_14_no_bot_multiplication(self):
        x=inspect_rollout(extra_owned_domains=[self.SUB])
        self.assertEqual(x["trading_bot"],"mojtaba.bot.ai")

    def test_15_no_prop_challenge_mirror_on_subsite(self):
        x=rollout_targets([self.SUB])
        self.assertEqual(len([r for r in x if r["brand"]=="moj_prop"]),1)
        self.assertEqual(next(r for r in x if r["brand"]=="moj_prop")["host"],"mojplaywin.com")

    def test_16_signal_brand_path_is_host_scoped(self):
        x=rollout_targets([self.SUB])
        self.assertTrue(all(r["path"].endswith("/market-signals/")
            for r in x if r["host"]==self.SUB and r["brand"]))

    def test_17_no_invoice_from_inventory(self):
        x=inspect_rollout(registry=self.approved(self.SUB),
                          extra_owned_domains=[self.SUB])
        self.assertTrue(all(r["invoice_created"] is False for r in x["entries"]))

    def test_18_canonical_anchors_still_exact_two(self):
        self.assertEqual(len(DISCOVERED_DOMAIN_ANCHORS),2)
