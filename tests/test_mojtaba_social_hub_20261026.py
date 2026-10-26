"""No-network regression for all API adapters, safety and durable queue."""
from __future__ import annotations
from pathlib import Path
import os
import tempfile
import unittest

from social_hub.adapters import send, Response, Blocked, Uncertain
from social_hub.catalog import PLATFORMS, catalogue
from social_hub.store import Store
from social_hub.service import connection_status, run_one
from social_hub.youtube import upload_video, checked_file

def account(platform="telegram", destination="-1001234567890", **extras):
    return {"platform":platform, "destination":destination, "brand":"personal","verified":True,**extras}

def respond(*replies):
    calls = []
    def transport(method,url,body,headers):
        calls.append((method,url,body,headers))
        if not replies:
            raise AssertionError("Missing mock API responses")
        return replies[len(calls)-1]
    return transport,calls

def ok(payload, headers=None, status=200):
    return Response(status,payload,headers or {})

class PlatformAdapterTests(unittest.TestCase):
    def test_catalog_has_distinct_modes_and_all_core_networks(self):
        self.assertGreaterEqual(len(catalogue()),40)
        for name in ("telegram","discord","instagram","youtube","tiktok","linkedin",
                     "facebook_pages","threads","pinterest","x","reddit","bluesky",
                     "mastodon","google_business_profile","whatsapp_business",
                     "zenodo","github_releases","orcid","researchgate","alibaba","steam"):
            self.assertIn(name,PLATFORMS)
        self.assertEqual(PLATFORMS["researchgate"].capability,"manual")
        self.assertFalse(PLATFORMS["researchgate"].sendable)
        self.assertEqual(PLATFORMS["orcid"].capability,"read_only")

    def test_no_unverified_or_restricted_handles(self):
        mock,_=respond(ok({"ok":True,"result":{"message_id":1}}))
        with self.assertRaises(Blocked):
            send(account(verified=False),{"text":"Hello"},"token",mock)
        with self.assertRaises(Blocked):
            send(account(),{"text":"Please visit dr.mojtaba.rozegar"},"123456789:"+"A"*30,mock)
        with self.assertRaises(Blocked):
            send(account("researchgate","x"),{"text":"Hello"},"abcdefg",mock)

    def test_telegram_returns_real_remote_id(self):
        mock,calls=respond(ok({"ok":True,"result":{"message_id":42}}))
        result=send(account(),{"text":"Research update"},"123456789:"+"A"*30,mock)
        self.assertEqual((result.state,result.remote_id),("published","42"))
        self.assertEqual(calls[0][2]["chat_id"],"-1001234567890")

    def test_discord_no_mention_broadcast(self):
        mock,calls=respond(ok({"id":"123456789012345678"}))
        send(account("discord","123456789012345678"),{"text":"@everyone update"},"token-123456",mock)
        self.assertEqual(calls[0][2]["allowed_mentions"],{"parse":[]})

    def test_x_text_and_linkedin_api_contract(self):
        m,c=respond(ok({"data":{"id":"7788"}}))
        result=send(account("x","123456"),{"text":"Hello"},"secret-token",m)
        self.assertEqual(result.remote_id,"7788")
        self.assertTrue(c[0][1].endswith("/2/tweets"))
        m,c=respond(ok({},{"x-restli-id":"urn:li:share:222"},201))
        result=send(account("linkedin","urn:li:organization:12345"),{"text":"Hello"},"token-123456",m)
        self.assertEqual(result.remote_id,"urn:li:share:222")
        self.assertIn("Linkedin-Version",c[0][3])

    def test_facebook_threads_two_stage(self):
        m,c=respond(ok({"id":"page_post_44"}))
        self.assertEqual(send(account("facebook_pages","123456"),{"text":"Hello"},"tokenabc",m).remote_id,"page_post_44")
        m,c=respond(ok({"id":"container123"}),ok({"id":"thread123"}))
        self.assertEqual(send(account("threads","123456"),{"text":"Hello"},"tokenabc",m).remote_id,"thread123")
        self.assertEqual(len(c),2)

    def test_bluesky_mastodon(self):
        m,c=respond(ok({"uri":"at://did:plc:example/app.bsky.feed.post/1"}))
        self.assertTrue(send(account("bluesky","did:plc:abcde"),{"text":"Hello"},"tokenabc",m).remote_id.startswith("at://"))
        m,c=respond(ok({"id":"123"}))
        self.assertEqual(send(account("mastodon","myhandle",instance="https://mastodon.social"),
                              {"text":"Hello","idempotency_key":"stable-abc"},"tokenabc",m).remote_id,"123")
        with self.assertRaises(Blocked):
            send(account("mastodon","myhandle",instance="http://localhost:8080"),{"text":"Hello"},"tokenabc",m)

    def test_google_business_reddit_pinterest(self):
        m,c=respond(ok({"name":"accounts/123/locations/456/localPosts/789"}))
        self.assertIn("localPosts",send(account("google_business_profile","accounts/123/locations/456"),
            {"text":"Farm research news"},"token123",m).remote_id)
        m,c=respond(ok({"json":{"data":{"name":"t3_123"},"errors":[]}}))
        self.assertEqual(send(account("reddit","testforum"),{"title":"Useful article","text":"Farm evidence"},
                              "token123",m).remote_id,"t3_123")
        m,c=respond(ok({"id":"777"}))
        x=send(account("pinterest","123456"),{"title":"Digital book","text":"Professional guide",
            "image_url":"https://mojplaywin.com/media/guide.jpg"},"token123",m)
        self.assertEqual(x.remote_id,"777")
        self.assertEqual(c[0][2]["media_source"]["source_type"],"image_url")
        with self.assertRaises(Blocked):
            send(account("pinterest","123456"),{"title":"x","text":"hello",
                 "image_url":"https://attacker.example/image.jpg"},"token123",m)

    def test_instagram_two_stage_verified_media_only(self):
        m,c=respond(ok({"id":"container789"}),ok({"id":"post123"}))
        out=send(account("instagram","123456"),{"text":"My professional study",
            "image_url":"https://mojplaywin.com/media/photo.jpg"},"token123",m)
        self.assertEqual(out.remote_id,"post123")
        self.assertEqual(len(c),2)

    def test_tiktok_explicit_consent_and_submitted_state(self):
        info=ok({"data":{"privacy_level_options":["SELF_ONLY"]},"error":{"code":"ok"}})
        init=ok({"data":{"publish_id":"v_pub_demo"},"error":{"code":"ok"}})
        m,c=respond(info,init)
        body={"text":"Video demo","video_url":"https://mojplaywin.com/media/clip.mp4",
              "creator_confirmed":True,"explicit_consent":True,
              "privacy_level":"SELF_ONLY",
              "disable_comment":True,"disable_duet":True,"disable_stitch":True}
        result=send(account("tiktok","user-open-id"),body,"token123",m)
        self.assertEqual(result.state,"submitted")
        self.assertEqual(result.remote_id,"v_pub_demo")
        self.assertEqual(len(c),2)
        with self.assertRaises(Blocked):
            send(account("tiktok","user-open-id"),{**body,"explicit_consent":False},"token123",m)

    def test_whatsapp_optin_and_scholarly_draft(self):
        m,c=respond(ok({"messages":[{"id":"wamid.123"}]}))
        x=send(account("whatsapp_business","123456"),{
            "recipient":"491234567890","consent_recorded":True,"template":"hello_world","language":"en_US"},
            "token123",m)
        self.assertEqual(x.state,"submitted")
        with self.assertRaises(Blocked):
            send(account("whatsapp_business","123456"),{
                "recipient":"491234567890","template":"hello_world"},"token123",m)
        m,c=respond(ok({"id":555}))
        x=send(account("zenodo","deposit"),{
            "publish":False,"title":"A scientific record","text":"Research metadata for preprint",
            "creators":[{"name":"Verified Author"}]},"token123",m)
        self.assertEqual(x.state,"draft_created")
        self.assertEqual(x.remote_id,"555")
        self.assertFalse(c[0][2].get("publish",False))

    def test_github_release_never_published(self):
        m,c=respond(ok({"id":454545}))
        x=send(account("github_releases","owner/safe_repo"),
            {"tag":"v1.0.0","title":"Safe draft","text":"Documented change"},"token123",m)
        self.assertEqual(x.state,"draft_created")
        self.assertTrue(c[0][2]["draft"])

    def test_youtube_private_video_bytes_and_host_checks(self):
        with tempfile.TemporaryDirectory() as root:
            video=Path(root)/"video.mp4"
            video.write_bytes(b"\x00\x00\x00\x14ftypisomdata")
            def transport(method,url,body,headers):
                if method=="POST":
                    return ok({},{"Location":"https://www.googleapis.com/upload/youtube/v3/videos?upload_id=sample"})
                self.assertEqual(method,"PUT")
                self.assertTrue(body.startswith(b"\x00\x00"))
                self.assertIn("Content-Range",headers)
                return ok({"id":"TestVid_123"})
            result=upload_video(account("youtube","UC123456789"),
                {"title":"My video","text":"Verified demo","media_path":"video.mp4",
                 "privacy":"private","made_for_kids":False},
                "token123",transport,media_root=root)
            self.assertEqual(result.remote_id,"TestVid_123")
            with self.assertRaises(Blocked):
                checked_file(root,"../../outside.mp4")

class DurableQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Store(str(Path(self.tmp.name)/"social.sqlite"))
        self.aid=self.db.add_account(brand="personal",platform_key="telegram",
                  destination="-1001234567890", actor="owner")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_default_is_unverified_without_token(self):
        self.assertEqual(self.db.accounts()[0]["verified"],0)
        self.assertFalse(connection_status(self.db,env={})[0]["connected"])
        self.assertEqual(self.db.summary()["verified_accounts"],0)

    def test_approval_blocks_unverified(self):
        pid=self.db.draft(account_id=self.aid,content={"text":"Hello"},actor="staff")
        with self.assertRaises(Blocked):
            self.db.approve(pid,"owner")
        self.assertEqual(self.db.post(pid)["state"],"draft")

    def test_approval_and_worker_receipt_and_no_retry(self):
        self.db.verify_account(self.aid,proof="api-proof-authorized-12345",actor="owner")
        pid=self.db.draft(account_id=self.aid,content={"text":"Hello"},actor="staff")
        self.db.approve(pid,"owner")
        env={self.db.account(self.aid)["token_env"]:"123456789:"+"A"*30,
             "MPW_SOCIAL_OUTBOUND_ENABLED":"1"}
        mock,calls=respond(ok({"ok":True,"result":{"message_id":88}}))
        with self.assertRaises(Blocked):
            run_one(self.db,pid,env=env,transport=mock,execute=False)
        self.assertEqual(len(calls),0)
        result=run_one(self.db,pid,env=env,transport=mock,execute=True)
        self.assertEqual(result["state"],"published")
        self.assertEqual(result["remote_id"],"88")
        self.assertEqual(len(calls),1)
        with self.assertRaises(Blocked):
            run_one(self.db,pid,env=env,transport=mock,execute=True)
        self.assertEqual(len(calls),1)

    def test_ambiguous_failure_requires_manual_review(self):
        self.db.verify_account(self.aid,proof="api-proof-authorized-12345",actor="owner")
        pid=self.db.draft(account_id=self.aid,content={"text":"Hello"},actor="staff")
        self.db.approve(pid,"owner")
        env={self.db.account(self.aid)["token_env"]:"123456789:"+"A"*30,
             "MPW_SOCIAL_OUTBOUND_ENABLED":"1"}
        with self.assertRaises(Uncertain):
            run_one(self.db,pid,env=env,execute=True,
                transport=lambda *args: (_ for _ in ()).throw(TimeoutError()))
        self.assertEqual(self.db.post(pid)["state"],"needs_review")

    def test_schedule_timezone_and_cancel(self):
        with self.assertRaises(Blocked):
            self.db.draft(account_id=self.aid,content={"text":"Hello"},
                          schedule_at="2026-12-01T05:00:00",actor="staff")
        pid=self.db.draft(account_id=self.aid,content={"text":"Hello"},actor="staff")
        self.db.revoke(pid,"owner")
        self.assertEqual(self.db.post(pid)["state"],"cancelled")

    def test_forbid_restricted_handle(self):
        with self.assertRaises(Blocked):
            self.db.add_account(brand="personal",platform_key="instagram",
                destination="dr.mojtaba.rozegar",actor="owner")
        with self.assertRaises(Blocked):
            self.db.draft(account_id=self.aid,content={"text":"Mention dr.mojtaba.rozegar"},
                          actor="staff")

    def test_reject_world_readable_database(self):
        with tempfile.TemporaryDirectory() as root:
            os.chmod(root,0o755)
            open_db=Path(root)/"unsafe.sqlite"
            with self.assertRaises(Blocked):
                Store(str(open_db))

if __name__ == "__main__":
    unittest.main()
