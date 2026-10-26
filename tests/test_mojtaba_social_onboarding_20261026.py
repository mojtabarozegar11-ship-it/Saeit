"""Atomic, offline, privacy-safe onboarding of genuine owner-provided profiles."""
from pathlib import Path
import tempfile
import unittest

from social_hub.adapters import Blocked
from social_hub.store import Store
from social_hub.onboarding import validate_manifest,preview,register

def manifest(accounts):
    return {"schema_version":1, "owner_confirmed":True, "accounts":accounts}

SAMPLE = [
    {"brand":"personal","platform":"telegram","destination":"@verifiedsample",
     "public_url":"https://t.me/verifiedsample"},
    {"brand":"zomorod","platform":"linkedin","destination":"urn:li:organization:123456",
     "public_url":"https://www.linkedin.com/company/sample-org/"},
    {"brand":"mojplaywin","platform":"researchgate","destination":"sampleowner",
     "public_url":"https://www.researchgate.net/profile/Sample-Owner"},
]

class OwnerManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(str(Path(self.tmp.name)/"social.sqlite"))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_owner_preview_does_not_create_or_connect(self):
        result=preview(self.store,manifest(SAMPLE))
        self.assertEqual(len(result["to_register"]),3)
        self.assertFalse(result["would_send_posts"])
        self.assertFalse(result["would_connect_apis"])
        self.assertEqual(self.store.summary()["accounts"],0)

    def test_atomic_import_and_idempotence(self):
        result=register(self.store,manifest(SAMPLE),actor="django:42")
        self.assertEqual(len(result["registered"]),3)
        self.assertEqual(result["connected"],0)
        self.assertEqual(result["published"],0)
        self.assertEqual(self.store.summary()["verified_accounts"],0)
        self.assertTrue(all(a["verified"]==0 for a in self.store.accounts()))
        self.assertEqual(len({a["token_env"] for a in self.store.accounts()}),3)
        self.assertEqual(sum(a["platform"]=="researchgate" for a in self.store.accounts()),1)
        again=register(self.store,manifest(SAMPLE),actor="django:42")
        self.assertEqual(len(again["registered"]),0)
        self.assertEqual(again["previously_registered"],3)

    def test_conflicting_registered_url_aborts_entire_batch(self):
        register(self.store,manifest(SAMPLE[:1]),actor="django:42")
        conflict={**SAMPLE[0],"public_url":"https://t.me/different_handle"}
        with self.assertRaises(Blocked):
            register(self.store,manifest([SAMPLE[1],conflict]),actor="django:42")
        self.assertEqual(self.store.summary()["accounts"],1)
        self.assertIsNone(self.store.db.execute(
            "SELECT id FROM accounts WHERE platform='linkedin'").fetchone())

    def test_reject_api_key_or_password_fields_without_partial_writes(self):
        bad={**SAMPLE[0],"token":"sensitive_fake_value"}
        with self.assertRaises(Blocked):
            register(self.store,manifest([SAMPLE[1],bad]),actor="django:42")
        self.assertEqual(self.store.summary()["accounts"],0)

    def test_restricted_handle_phishing_and_unsafe_schemes_blocked(self):
        for public_url in [
            "https://www.instagram.com/dr.mojtaba.rozegar/",
            "https://evil.example/official",
            "http://t.me/verifiedsample",
            "https://t.me.evil.example/verifiedsample",
            "https://t.me/verifiedsample?access_token=secret",
            "https://t.me:444/verifiedsample",
        ]:
            bad=[{**SAMPLE[0],"public_url":public_url}]
            with self.assertRaises(Blocked, msg=public_url):
                validate_manifest(manifest(bad))

    def test_missing_owner_confirmation_and_duplicate_abort(self):
        with self.assertRaises(Blocked):
            validate_manifest({"schema_version":1,"owner_confirmed":False,"accounts":SAMPLE})
        with self.assertRaises(Blocked):
            validate_manifest(manifest([SAMPLE[0],SAMPLE[0]]))
        with self.assertRaises(Blocked):
            validate_manifest({"schema_version":1,"owner_confirmed":True,"accounts":SAMPLE,"password":"dummy"})

    def test_mastodon_url_must_match_declared_instance(self):
        good={"brand":"personal","platform":"mastodon","destination":"@user@mastodon.social",
              "instance":"https://mastodon.social",
              "public_url":"https://mastodon.social/@user"}
        self.assertEqual(validate_manifest(manifest([good]))[0]["instance"],"https://mastodon.social")
        with self.assertRaises(Blocked):
            validate_manifest(manifest([{**good,"public_url":"https://different.social/@user"}]))
        with self.assertRaises(Blocked):
            validate_manifest(manifest([{**good,"instance":"http://127.0.0.1"}]))

    def test_empty_batch_is_valid_no_network_no_posts(self):
        result=register(self.store,manifest([]),actor="owner-cli:manual")
        self.assertEqual(result["registered"],[])
        self.assertEqual(self.store.summary()["accounts"],0)

    def test_privileged_actor_required(self):
        with self.assertRaises(Blocked):
            register(self.store,manifest(SAMPLE),actor="anonymous")
        self.assertEqual(self.store.summary()["accounts"],0)

if __name__=="__main__":
    unittest.main()
