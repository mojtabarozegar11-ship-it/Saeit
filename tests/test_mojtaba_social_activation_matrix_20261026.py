"""One-owner-only activation status across all 3 brands, no false connected claims."""
import json
from pathlib import Path
import tempfile
import unittest

from social_hub.activation import build_activation_matrix, PRIORITIES
from social_hub.adapters import Blocked
from social_hub.catalog import BRANDS,PLATFORMS
from social_hub.store import Store

class ProviderActivationMatrixContracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(str(Path(self.tmp.name)/"social.sqlite"))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def matrix(self, brands=None,env=None):
        return build_activation_matrix(self.store,brands=brands or BRANDS,env=env or {})

    def test_empty_registry_is_not_misreported_as_social_accounts(self):
        plan=self.matrix()
        self.assertEqual(len(plan["entries"]),3*len(PLATFORMS))
        self.assertEqual(plan["catalogue_platform_count"],len(PLATFORMS))
        self.assertEqual(plan["registered_account_count"],0)
        self.assertEqual(plan["owner_attested_account_count"],0)
        self.assertEqual(plan["accounts_with_privately_configured_keys"],0)
        self.assertEqual(plan["provider_posting_permissions_confirmed"],0)
        self.assertFalse(plan["external_publish_enabled_by_plan"])
        self.assertFalse(plan["tokens_included"])
        self.assertEqual(plan["suggested_priority_platform_pairs"],
                         sum(len(v) for v in PRIORITIES.values()))
        self.assertTrue(all(x["next_action_code"]=="register_real_account"
                            for x in plan["entries"]))
        self.assertTrue(all(not x["accounts"] for x in plan["entries"]))

    def test_status_sequence_with_independent_real_owner_evidence(self):
        tg=self.store.add_account(brand="personal",platform_key="telegram",
            destination="@OfficialChannel",public_url="https://t.me/OfficialChannel",actor="owner")
        linkedin=self.store.add_account(brand="zomorod",platform_key="linkedin",
            destination="urn:li:organization:12345",
            public_url="https://www.linkedin.com/company/owned-test/",actor="owner")
        academic=self.store.add_account(brand="personal",platform_key="researchgate",
            destination="scholar-owner",
            public_url="https://www.researchgate.net/profile/Scholar-Owner",actor="owner")
        self.store.verify_account(academic,proof="owner-attested-professional-profile-proof",actor="owner")
        before=self.matrix()
        telegram=next(x for x in before["entries"] if x["brand"]=="personal" and x["platform"]=="telegram")
        self.assertEqual(telegram["next_action_code"],"record_owner_proof")
        self.assertEqual(telegram["registered_accounts"],1)
        self.assertEqual(before["owner_attested_account_count"],1)
        research=next(x for x in before["entries"] if x["platform"]=="researchgate" and x["brand"]=="personal")
        self.assertEqual(research["next_action_code"],"manual_profile_ready")
        self.assertFalse(research["write_adapter_implemented_locally"])
        self.assertEqual(research["credential_configured_accounts"],0)
        self.store.verify_account(tg,proof="owner-attested-independent-telegram",actor="owner")
        self.store.record_api_check(tg,status="identity_verified",identity="123456789",
             note="bot_and_channel_admin_checked",actor="owner")
        token=self.store.account(tg)["token_env"]
        value="this-is-a-FICTIONAL-owner-only-token"
        with_key=self.matrix(env={token:value})
        t=next(x for x in with_key["entries"] if x["brand"]=="personal" and x["platform"]=="telegram")
        self.assertEqual(t["next_action_code"],"write_scope_and_delivery_confirmation")
        self.assertTrue(t["accounts"][0]["credential_present"])
        self.assertFalse(t["accounts"][0]["remote_post_permission_verified"])
        self.assertEqual(with_key["provider_posting_permissions_confirmed"],0)
        text=json.dumps(with_key,ensure_ascii=False)
        self.assertNotIn(value,text)
        self.assertNotIn(token,text)
        self.assertNotIn("owner-attested-independent-telegram",text)
        self.assertEqual(with_key["registered_account_count"],3)
        self.assertEqual(with_key["owner_attested_account_count"],2)
        self.assertEqual(with_key["accounts_with_privately_configured_keys"],1)
        self.assertEqual(self.store.summary()["states"]["published"],0)

    def test_scoped_staff_sees_only_authorized_brands(self):
        a=self.store.add_account(brand="personal",platform_key="telegram",
            destination="@OwnerChannel",public_url="https://t.me/OwnerChannel",actor="owner")
        b=self.store.add_account(brand="mojplaywin",platform_key="discord",
            destination="123456789012345678",actor="owner")
        personal=self.matrix(brands={"personal"})
        self.assertEqual(personal["brands"],["personal"])
        self.assertEqual(len(personal["entries"]),len(PLATFORMS))
        self.assertEqual(personal["registered_account_count"],1)
        payload=json.dumps(personal)
        self.assertNotIn(b,payload)
        self.assertNotIn("mojplaywin",payload)
        with self.assertRaises(Blocked):
            self.matrix(brands={"personal","unauthorized"})
        with self.assertRaises(Blocked):
            build_activation_matrix(self.store,brands=[],env={})

    def test_restricted_account_is_never_offered_even_if_legacy_db_corrupted(self):
        aid=self.store.add_account(brand="mojplaywin",platform_key="instagram",
            destination="safe-account",
            public_url="https://www.instagram.com/safe-account/",actor="owner")
        with self.store.transaction():
            self.store.db.execute("UPDATE accounts SET destination=?,public_url=? WHERE id=?",
                                  ("dr.mojtaba.rozegar",
                                   "https://www.instagram.com/dr.mojtaba.rozegar/",aid))
        plan=self.matrix()
        item=next(x for x in plan["entries"] if x["brand"]=="mojplaywin" and x["platform"]=="instagram")
        self.assertEqual(item["registered_accounts"],0)
        self.assertEqual(item["next_action_code"],"register_real_account")
        self.assertNotIn("dr.mojtaba.rozegar",json.dumps(plan))

    def test_priority_lists_are_unique_and_within_catalogue(self):
        for brand,keys in PRIORITIES.items():
            self.assertIn(brand,BRANDS)
            self.assertEqual(len(keys),len(set(keys)))
            self.assertTrue(set(keys).issubset(PLATFORMS))
        self.assertTrue(all(x["documentation_url"].startswith("https://")
            for x in self.matrix()["entries"]))
        self.assertFalse(any(x["write_adapter_implemented_locally"]
            for x in self.matrix()["entries"] if x["platform"]=="researchgate"))

if __name__=="__main__":
    unittest.main()
