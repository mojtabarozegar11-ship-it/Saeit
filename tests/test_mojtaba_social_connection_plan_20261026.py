"""One-phase social provider account preparation is private, brand-scoped, token-free."""
import json
from pathlib import Path
import tempfile
import unittest

from social_hub.store import Store
from social_hub.connection_plan import build_connection_plan
from social_hub.adapters import Blocked

class PrivateAPISetupChecklistTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=Store(str(Path(self.temp.name)/"db.sqlite"))
        self.tg=self.db.add_account(brand="personal",platform_key="telegram",
            destination="@RealChannel",public_url="https://t.me/RealChannel",
            actor="owner")
        self.db.verify_account(self.tg,proof="verified-owner-evidence-1234",actor="owner")
        self.linkedin=self.db.add_account(brand="zomorod",platform_key="linkedin",
            destination="urn:li:organization:1234",
            public_url="https://www.linkedin.com/company/official-company/",
            actor="owner")
        self.research=self.db.add_account(brand="personal",platform_key="researchgate",
            destination="official-scientist",
            public_url="https://www.researchgate.net/profile/Official-Scientist",
            actor="owner")
        self.db.verify_account(self.research,proof="verified-owner-profile-12345",actor="owner")

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_no_secret_values_and_clear_provider_scope(self):
        key=self.db.account(self.tg)["token_env"]
        value="SENSITIVE_DO_NOT_LEAK_PRIVATE_API_TOKEN"
        checklist=build_connection_plan(self.db,brands={"personal","zomorod"},
                   env={key:value})
        self.assertEqual(checklist["account_count"],3)
        self.assertFalse(checklist["credentials_included"])
        self.assertFalse(checklist["publishing_enabled_by_this_plan"])
        serial=json.dumps(checklist)
        self.assertNotIn(value,serial)
        self.assertNotIn("verified-owner",serial)
        self.assertIn(key,serial)
        self.assertEqual(checklist["provider_identity_read_verified"],0)
        telegram=next(x for x in checklist["items"] if x["provider"]=="telegram")
        self.assertTrue(telegram["credential_configured_privately"])
        self.assertEqual(telegram["next_action"],"read_only_identity_or_scope_check_required")
        self.assertFalse(telegram["publishing_permission_verified"])

    def test_manual_scientific_profile_requires_no_posting_key(self):
        data=build_connection_plan(self.db,brands={"personal"},env={})
        manual=next(x for x in data["items"] if x["provider"]=="researchgate")
        self.assertIsNone(manual["credential_env_name"])
        self.assertFalse(manual["write_adapter_locally_implemented"])
        self.assertEqual(manual["next_action"],"manual_public_profile_only")
        self.assertEqual(data["account_count"],2)
        self.assertNotIn("zomorod",data["brands"])
        self.assertNotIn("urn:li:organization",json.dumps(data))

    def test_offline_untested_accounts_are_not_connected(self):
        output=build_connection_plan(self.db,brands={"zomorod"},env={})
        self.assertEqual(output["account_count"],1)
        self.assertFalse(output["items"][0]["owner_profile_attested"])
        self.assertEqual(output["items"][0]["next_action"],"owner_profile_attestation_required")
        self.assertFalse(output["items"][0]["publishing_permission_verified"])

    def test_brand_outside_scope_rejected(self):
        for b in ({"personal","other"},{""}):
            with self.assertRaises(Blocked):
                build_connection_plan(self.db,brands=b,env={})

if __name__=="__main__":
    unittest.main()
