"""Network-free official API identity-check contracts: identity != permission to publish.

Never connect to real social accounts or put credentials in test logs.
"""
from __future__ import annotations
from pathlib import Path
import tempfile
import unittest

from social_hub.adapters import Blocked, Uncertain, Response
from social_hub.diagnostics import inspect, record_one, SUPPORTED
from social_hub.service import connection_status
from social_hub.store import Store

TG_TOKEN="123456789:" + "A"*32

def account(platform, destination, **extras):
    out={"brand":"personal","platform":platform,"verified":True,
         "destination":destination}
    out.update(extras)
    return out

class Mocks:
    def __init__(self,*responses):
        self.calls=[]
        self.replies=list(responses)
    def __call__(self,method,url,body,headers):
        self.calls.append((method,url,body,headers))
        if method != "GET" or body is not None:
            raise AssertionError("A read-only test must NEVER send a POST, payload, or message")
        if not self.replies:
            raise AssertionError("Mock response exhausted")
        return Response(200,self.replies.pop(0),{})

class ReadOnlyOfficialAPIContracts(unittest.TestCase):
    def test_supported_providers_declared(self):
        self.assertGreaterEqual(len(SUPPORTED),12)
        self.assertNotIn("researchgate",SUPPORTED)
        self.assertNotIn("google_scholar",SUPPORTED)

    def test_telegram_authenticates_real_bot_channel_and_post_admin(self):
        mock=Mocks(
            {"ok":True,"result":{"id":123456789,"is_bot":True,"username":"SampleBot"}},
            {"ok":True,"result":{"id":-1001234567890,"type":"channel","username":"TestChannel"}},
            {"ok":True,"result":[{"user":{"id":123456789},"status":"administrator",
                                   "can_post_messages":True}]},
        )
        result=inspect(account("telegram","@TestChannel"),TG_TOKEN,transport=mock)
        self.assertEqual(result.status,"identity_verified")
        self.assertEqual(result.capability,"channel_admin")
        self.assertEqual(len(mock.calls),3)
        self.assertTrue(all(c[0]=="GET" for c in mock.calls))
        self.assertNotIn("sendMessage"," ".join(c[1] for c in mock.calls))

    def test_telegram_requires_true_admin_and_matching_destination(self):
        replies=[
            {"ok":True,"result":{"id":123456789,"is_bot":True}},
            {"ok":True,"result":{"id":-1001234567890,"type":"channel","username":"TestChannel"}},
            {"ok":True,"result":[{"user":{"id":123456789},"status":"member"}]},
        ]
        with self.assertRaises(Blocked):
            inspect(account("telegram","@TestChannel"),TG_TOKEN,transport=Mocks(*replies))
        with self.assertRaises(Blocked):
            inspect(account("telegram","@WrongChannel"),TG_TOKEN,transport=Mocks(*replies))

    def test_discord_bot_token_plus_channel_is_limited_without_permission_resolution(self):
        mock=Mocks({"id":"987654321012345678","bot":True},
                   {"id":"123456789012345678","type":0})
        result=inspect(account("discord","123456789012345678"),
                       "fake-bot-token-for-testing",transport=mock)
        self.assertEqual(result.status,"credential_valid_only")
        self.assertEqual(result.note_code,"channel_access_not_proof_of_send_permission")
        self.assertTrue(all(c[3]["Authorization"].startswith("Bot ") for c in mock.calls))

    def test_youtube_channel_mine_identity_binding(self):
        channel="UC"+"a"*22
        mock=Mocks({"items":[{"id":channel}]})
        result=inspect(account("youtube",channel),"test-token",transport=mock)
        self.assertEqual(result.status,"identity_verified")
        self.assertIn("mine=true",mock.calls[0][1])
        with self.assertRaises(Blocked):
            inspect(account("youtube","UC"+"z"*22),"test-token",
                    transport=Mocks({"items":[{"id":channel}]}))

    def test_mastodon_requires_explicit_origin_and_matching_username(self):
        a=account("mastodon","@real@mastodon.social",instance="https://mastodon.social")
        blocked=Mocks({"id":"999","username":"real"})
        with self.assertRaises(Blocked):
            inspect(a,"test-token",transport=blocked,allowed_instances=())
        self.assertFalse(blocked.calls)
        passed=Mocks({"id":"999","username":"real"})
        result=inspect(a,"test-token",transport=passed,
                       allowed_instances=("https://mastodon.social",))
        self.assertEqual(result.status,"identity_verified")
        self.assertEqual(len(passed.calls),1)
        with self.assertRaises(Blocked):
            inspect(a,"test-token",transport=Mocks({"id":"999","username":"other"}),
                    allowed_instances=("https://mastodon.social",))
        with self.assertRaises(Blocked):
            inspect(account("mastodon","@real",instance="https://127.0.0.1"),
                    "test-token",transport=Mocks(),allowed_instances=("https://127.0.0.1",))

    def test_bluesky_x_instagram_tiktok_account_identity_checks(self):
        cases=[
            ("bluesky","did:plc:sample",{"did":"did:plc:sample","handle":"sample.bsky.social"}),
            ("x","135790246",{"data":{"id":"135790246"}}),
            ("instagram","123456789",{"id":"123456789","username":"sample"}),
            ("tiktok","tiktok-owned-id",{"data":{"user":{"open_id":"tiktok-owned-id"}}}),
            ("facebook_pages","102345678",{"id":"102345678"}),
            ("whatsapp_business","102345678",{"id":"102345678","display_phone_number":"+12345678"}),
        ]
        for platform,dest,payload in cases:
            with self.subTest(platform=platform):
                mock=Mocks(payload)
                result=inspect(account(platform,dest),"test-token",transport=mock)
                self.assertEqual(result.status,"identity_verified")
                self.assertEqual(len(mock.calls),1)
                self.assertEqual(mock.calls[0][0],"GET")

    def test_reddit_linkedin_github_pinterest_do_not_fake_posting_rights(self):
        cases=[
            ("reddit","sampleforum",{"name":"authenticated_person"}),
            ("linkedin","urn:li:organization:123456",{"sub":"linkedin-person-id"}),
            ("github_releases","owner/repo",{"login":"sampleowner"}),
            ("pinterest","123456789",{"username":"sampleowner"}),
        ]
        for platform,dest,payload in cases:
            with self.subTest(platform=platform):
                result=inspect(account(platform,dest),"test-token",transport=Mocks(payload))
                self.assertEqual(result.status,"credential_valid_only")

    def test_restricted_and_unverified_not_probed(self):
        fake=Mocks()
        with self.assertRaises(Blocked):
            inspect(account("instagram","dr.mojtaba.rozegar"),
                    "test-token",transport=fake)
        with self.assertRaises(Blocked):
            inspect(account("x","1234",verified=False),
                    "test-token",transport=fake)
        with self.assertRaises(Blocked):
            inspect(account("google_scholar","some_handle"),"test-token",transport=fake)
        self.assertEqual(fake.calls,[])

    def test_no_token_or_provider_body_in_errors(self):
        mock=Mocks({"data":{"id":"OTHER_USER"}})
        with self.assertRaises(Blocked) as caught:
            inspect(account("x","123456789"),"an-extremely-private-token",transport=mock)
        self.assertNotIn("an-extremely-private-token",str(caught.exception))
        self.assertNotIn("OTHER_USER",str(caught.exception))

class ProbeLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(str(Path(self.tmp.name)/"social.sqlite"))
        self.aid=self.store.add_account(brand="personal",platform_key="telegram",
                                        destination="@SampleOwner",
                                        public_url="https://t.me/SampleOwner",
                                        actor="owner")
        self.store.verify_account(self.aid,proof="authenticated-owner-evidence-123456",actor="owner")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def token_env(self):
        return {self.store.account(self.aid)["token_env"]:TG_TOKEN}

    def test_token_is_never_stored_and_read_only_receipt_is_auditable(self):
        replies=Mocks(
            {"ok":True,"result":{"id":123456789,"is_bot":True}},
            {"ok":True,"result":{"id":-1001234567890,"type":"channel","username":"SampleOwner"}},
            {"ok":True,"result":[{"user":{"id":123456789},"status":"creator"}]},
        )
        report=record_one(self.store,self.aid,env=self.token_env(),transport=replies)
        self.assertTrue(report["provider_identity_verified"])
        self.assertFalse(report["publishing_scope_verified"])
        check=self.store.api_check(self.aid)
        self.assertEqual(check["state"],"identity_verified")
        self.assertEqual(check["provider_identity"],"123456789")
        self.assertNotIn(TG_TOKEN,str(check))
        status=connection_status(self.store,env=self.token_env())[0]
        self.assertTrue(status["provider_verified"])
        self.assertFalse(status["connected"])
        self.assertEqual(status["provider_check_state"],"identity_verified")
        self.assertNotIn(TG_TOKEN,str(status))
        self.assertEqual(len(replies.calls),3)
        self.assertEqual(self.store.summary()["states"]["published"],0)

    def test_failed_probe_records_generic_error_and_blocks_fast_repeat(self):
        mock=Mocks({"ok":False,"description":"TOKEN_OR_PRIVATE_REMOTE_SECRET"})
        result=record_one(self.store,self.aid,env=self.token_env(),transport=mock)
        self.assertEqual(result["status"],"failed")
        self.assertEqual(result["note_code"],"read_only_provider_verification_failed")
        self.assertNotIn("TOKEN_OR_PRIVATE_REMOTE_SECRET",str(result))
        self.assertNotIn(TG_TOKEN,str(self.store.api_check(self.aid)))
        with self.assertRaises(Blocked):
            record_one(self.store,self.aid,env=self.token_env(),transport=Mocks())
        self.assertEqual(self.store.summary()["states"]["published"],0)

    def test_unconfigured_token_fails_before_io_and_db_update(self):
        fake=Mocks()
        with self.assertRaises(Blocked):
            record_one(self.store,self.aid,env={},transport=fake)
        self.assertFalse(fake.calls)
        self.assertIsNone(self.store.api_check(self.aid))

    def test_unattested_account_no_api_verification(self):
        other=self.store.add_account(brand="mojplaywin",platform_key="discord",
            destination="123456789012345678",actor="owner")
        with self.assertRaises(Blocked):
            record_one(self.store,other,env={
                self.store.account(other)["token_env"]:"12345botsecret"},transport=Mocks())
        self.assertIsNone(self.store.api_check(other))

    def test_account_suspension_revokes_public_link_and_cancels_approved_queue(self):
        from social_hub.public_links import official_links
        from social_hub.service import run_one
        self.assertEqual(official_links(self.store)["total"],1)
        pid=self.store.draft(account_id=self.aid,content={"text":"Approved; do not send"},
                             actor="staff")
        self.store.approve(pid,actor="owner")
        self.store.record_api_check(self.aid,status="identity_verified",identity="123456789",
                                    note="bot_and_channel_admin_checked",actor="owner")
        outcome=self.store.suspend_account(self.aid,actor="owner")
        self.assertEqual(outcome["approved_posts_cancelled"],1)
        self.assertTrue(outcome["provider_token_revocation_required"])
        self.assertEqual(self.store.post(pid)["state"],"cancelled")
        self.assertEqual(self.store.account(self.aid)["verified"],0)
        self.assertEqual(official_links(self.store)["total"],0)
        self.assertIsNone(self.store.api_check(self.aid))
        self.assertTrue(self.store.account(self.aid)["proof"])
        with self.assertRaises(Blocked):
            run_one(self.store,pid,env={**self.token_env(),"MPW_SOCIAL_OUTBOUND_ENABLED":"1"},
                    execute=True,transport=Mocks())

    def test_invalid_status_or_note_cannot_be_written(self):
        with self.assertRaises(Blocked):
            self.store.record_api_check(self.aid,status="published",identity="",note="ok",actor="owner")
        with self.assertRaises(Blocked):
            self.store.record_api_check(self.aid,status="failed",identity="",note=TG_TOKEN,actor="owner")

if __name__ == "__main__":
    unittest.main()
