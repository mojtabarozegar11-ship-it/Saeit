"""Offline owner-only credential provisioning tests; no real tokens or HTTP."""
from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import sys

from social_hub.adapters import Blocked
from social_hub.catalog import platform
from social_hub.connection_plan import build_connection_plan
from social_hub.credential_vault import (
    _vault, credential_for, has_credential, import_batch, plan_import,
    disconnect_batch, load_private_import, create_private_template, default_private_vault_path,
)
from social_hub.service import connection_status
from social_hub.store import Store

FAKE_A="fake-token-for-telegram-owner-only"
FAKE_B="fake-token-for-discord-owner-only"
REPLACEMENT="fake-token-ROTATED-123456"

class PrivateCredentialVaultTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.private=Path(self.temp.name)
        self.store=Store(str(self.private/"social.sqlite"))
        self.vault=str(self.private/"social-auth-private.json")
        self.accounts=[]
        for brand,key,destination,url in (
            ("personal","telegram","@VerifiedOwner","https://t.me/VerifiedOwner"),
            ("zomorod","discord","123456789012345678",""),
        ):
            aid=self.store.add_account(brand=brand,platform_key=key,
                destination=destination,public_url=url,actor="owner")
            self.store.verify_account(aid,proof="verified-owner-platform-access-1234",actor="owner")
            self.accounts.append(aid)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def manifest(self,a=FAKE_A,b=FAKE_B):
        return {"schema_version":1,"owner_confirmed":True,"credentials":[
            {"account_id":self.accounts[0],"token":a},
            {"account_id":self.accounts[1],"token":b},
        ]}

    def test_single_atomic_batch_stages_both_brands_without_network_or_publish(self):
        plan=plan_import(self.store,self.manifest(),vault_file=self.vault,env={})
        self.assertEqual(plan["accounts"],2)
        self.assertEqual(plan["new_credentials"],2)
        self.assertFalse(plan["outbound_enabled"])
        self.assertFalse(plan["tokens_returned"])
        self.assertFalse(Path(self.vault).exists())
        result=import_batch(self.store,self.manifest(),vault_file=self.vault,
                            actor="owner-cli:bulk",env={})
        self.assertEqual(result["status"],"private_credentials_staged")
        self.assertEqual(result["new_credentials"],2)
        self.assertFalse(result["provider_authorizations_completed"])
        self.assertEqual(Path(self.vault).stat().st_mode & 0o777,0o600)
        self.assertEqual(Path(self.vault+".lock").stat().st_mode & 0o777,0o600)
        env={"MPW_SOCIAL_CREDENTIAL_VAULT":self.vault}
        first=self.store.account(self.accounts[0])
        second=self.store.account(self.accounts[1])
        self.assertEqual(credential_for(first,env=env),FAKE_A)
        self.assertEqual(credential_for(second,env=env),FAKE_B)
        displayed=connection_status(self.store,env=env)
        self.assertEqual(len(displayed),2)
        self.assertTrue(all(x["token_present"] for x in displayed))
        self.assertFalse(any(x["connected"] or x["provider_verified"] or
                             x["publishing_scope_verified"] for x in displayed))
        plan=build_connection_plan(self.store,brands={"personal","zomorod"},env=env)
        public=str(result)+str(plan)+str(displayed)
        self.assertNotIn(FAKE_A,public)
        self.assertNotIn(FAKE_B,public)
        self.assertFalse(plan["publishing_enabled_by_this_plan"])
        self.assertEqual(self.store.summary()["states"]["published"],0)
        audit=" ".join(str(dict(r)) for r in self.store.db.execute(
            "SELECT detail,event FROM events"))
        self.assertNotIn(FAKE_A,audit)
        self.assertNotIn(FAKE_B,audit)

    def test_invalid_batch_has_no_partial_secrets(self):
        good=self.manifest()
        bad={"schema_version":1,"owner_confirmed":True,"credentials":[
            good["credentials"][0],
            {"account_id":"a"*32,"token":FAKE_B},
        ]}
        with self.assertRaises(Blocked):
            import_batch(self.store,bad,vault_file=self.vault,env={},
                         actor="owner-cli:bulk")
        self.assertFalse(Path(self.vault).exists())
        self.assertIsNone(self.store.api_check(self.accounts[0]))
        with self.assertRaises(Blocked):
            import_batch(self.store,{"schema_version":1,"owner_confirmed":False,
                         "credentials":good["credentials"]},
                         vault_file=self.vault,env={},actor="owner-cli:bulk")

    def test_rotation_requires_explicit_override_and_invalidates_cached_auth(self):
        import_batch(self.store,self.manifest(),vault_file=self.vault,
                     actor="owner-cli:bulk",env={})
        self.store.record_api_check(self.accounts[0],status="identity_verified",
              identity="123456789",note="bot_and_channel_admin_checked",actor="owner")
        before=Path(self.vault).read_bytes()
        with self.assertRaises(Blocked):
            import_batch(self.store,self.manifest(a=REPLACEMENT),vault_file=self.vault,
                         actor="owner-cli:bulk",env={},replace=False)
        self.assertEqual(Path(self.vault).read_bytes(),before)
        self.assertIsNotNone(self.store.api_check(self.accounts[0]))
        rotated=import_batch(self.store,self.manifest(a=REPLACEMENT),
                   vault_file=self.vault,actor="owner-cli:bulk",env={},replace=True)
        self.assertEqual(rotated["rotations"],2)
        self.assertEqual(credential_for(self.store.account(self.accounts[0]),
                          vault_file=self.vault,env={}),REPLACEMENT)
        self.assertIsNone(self.store.api_check(self.accounts[0]))
        self.assertNotIn(REPLACEMENT,str(rotated))

    def test_no_duplicate_identity_or_environment_token_ambiguity(self):
        duplicate=self.manifest()
        duplicate["credentials"].append(duplicate["credentials"][0])
        with self.assertRaises(Blocked):
            plan_import(self.store,duplicate,vault_file=self.vault,env={})
        alias=self.store.account(self.accounts[0])["token_env"]
        with self.assertRaises(Blocked):
            plan_import(self.store,self.manifest(),vault_file=self.vault,
                        env={alias:FAKE_A})
        import_batch(self.store,self.manifest(),vault_file=self.vault,
                     actor="owner-cli:bulk",env={})
        with self.assertRaises(Blocked):
            credential_for(self.store.account(self.accounts[0]),
                           env={alias:FAKE_B,"MPW_SOCIAL_CREDENTIAL_VAULT":self.vault})

    def test_unverified_or_manual_profiles_cannot_be_provisioned(self):
        unverified=self.store.add_account(brand="mojplaywin",platform_key="youtube",
                        destination="UC"+"a"*22,actor="owner")
        data={"schema_version":1,"owner_confirmed":True,"credentials":[
            {"account_id":unverified,"token":FAKE_A}]}
        with self.assertRaises(Blocked):
            plan_import(self.store,data,vault_file=self.vault,env={})
        manual=self.store.add_account(brand="personal",platform_key="researchgate",
                       destination="scientistowner",
                       public_url="https://www.researchgate.net/profile/Scientist-Owner",
                       actor="owner")
        self.store.verify_account(manual,proof="verified-research-profile-123456",actor="owner")
        data["credentials"][0]["account_id"]=manual
        with self.assertRaises(Blocked):
            plan_import(self.store,data,vault_file=self.vault,env={})
        with self.assertRaises(Blocked):
            import_batch(self.store,self.manifest(),vault_file=self.vault,
                         actor="anonymous",env={})

    def test_unsafe_directory_file_symlink_or_input_file_blocked(self):
        self.private.chmod(0o755)
        with self.assertRaises(Blocked):
            plan_import(self.store,self.manifest(),vault_file=self.vault,env={})
        self.private.chmod(0o700)
        input_path=self.private/"manifest.json"
        input_path.write_text(json.dumps(self.manifest()),encoding="utf-8")
        input_path.chmod(0o644)
        with self.assertRaises(Blocked):
            load_private_import(str(input_path))
        input_path.chmod(0o600)
        self.assertEqual(len(load_private_import(str(input_path))["credentials"]),2)
        target=self.private/"permitted-dummy-file.json"
        target.write_text("{}",encoding="utf-8")
        target.chmod(0o600)
        Path(self.vault).symlink_to(target)
        with self.assertRaises(Blocked):
            plan_import(self.store,self.manifest(),vault_file=self.vault,env={})
        Path(self.vault).unlink()

    def test_installed_personal_site_defaults_to_existing_private_db_folder(self):
        default=str(self.private/"provider-api-vault.json")
        private_module=SimpleNamespace(PRIVATE_DB=str(self.private/"social.sqlite"))
        with patch.dict(sys.modules,{"social_hub.site_config":private_module}):
            self.assertEqual(default_private_vault_path(),default)
            import_batch(self.store,self.manifest(),vault_file=default,env={},
                         actor="owner-cli:bulk")
            first=credential_for(self.store.account(self.accounts[0]),env={})
            self.assertEqual(first,FAKE_A)
            report=connection_status(self.store,env={})
            self.assertTrue(all(item["token_present"] for item in report))
            self.assertFalse(any(item["connected"] for item in report))
        blocked=self.private/"public_html"
        blocked.mkdir(mode=0o700)
        with patch.dict(sys.modules,{"social_hub.site_config":
             SimpleNamespace(PRIVATE_DB=str(blocked/"social.sqlite"))}):
            with self.assertRaises(Blocked):
                default_private_vault_path()

    def test_owner_gets_only_real_account_ids_in_private_blank_input_template(self):
        target=self.private/"one-stage-input.json"
        result=create_private_template(self.store,str(target))
        self.assertEqual(result["account_count"],2)
        self.assertFalse(result["credentials_included"])
        self.assertEqual(target.stat().st_mode & 0o777,0o600)
        manifest=load_private_import(str(target))
        self.assertEqual({v["account_id"] for v in manifest["credentials"]},
                         set(self.accounts))
        self.assertTrue(all(row["token"]=="" for row in manifest["credentials"]))
        with self.assertRaises(Blocked):
            import_batch(self.store,manifest,vault_file=self.vault,env={},
                         actor="owner-cli:bulk")
        self.assertFalse(Path(self.vault).exists())
        with self.assertRaises(Blocked):
            create_private_template(self.store,str(target))

    def test_local_revocation_clears_token_and_cached_probe_but_keeps_public_profile(self):
        import_batch(self.store,self.manifest(),vault_file=self.vault,
                     actor="owner-cli:bulk",env={})
        self.store.record_api_check(self.accounts[0],status="identity_verified",
                   identity="123456789",note="bot_and_channel_admin_checked",actor="owner")
        removed=disconnect_batch(self.store,[self.accounts[0]],vault_file=self.vault,
                                 actor="owner-cli:revoke")
        self.assertEqual(removed["local_credentials_removed"],1)
        self.assertTrue(removed["provider_side_revocation_required"])
        self.assertIsNone(self.store.api_check(self.accounts[0]))
        self.assertEqual(self.store.account(self.accounts[0])["verified"],1)
        self.assertFalse(has_credential(self.store.account(self.accounts[0]),
                                       vault_file=self.vault,env={}))
        self.assertTrue(has_credential(self.store.account(self.accounts[1]),
                                      vault_file=self.vault,env={}))
        self.assertNotIn(FAKE_A,str(removed))

    def test_manifests_never_allow_extra_keys_and_placeholders_as_secrets(self):
        m=self.manifest()
        m["credentials"][0]["refresh_token"]="unsafe-extra-field"
        with self.assertRaises(Blocked):
            plan_import(self.store,m,vault_file=self.vault,env={})
        m=self.manifest(a="has a space")
        with self.assertRaises(Blocked):
            plan_import(self.store,m,vault_file=self.vault,env={})

if __name__=="__main__":
    unittest.main()
