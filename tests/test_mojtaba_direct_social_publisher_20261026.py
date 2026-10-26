"""Offline contract tests; NEVER send real network requests."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts/mojtaba_direct_social_publisher_20261026.py"
spec = importlib.util.spec_from_file_location("social_publisher", PATH)
pub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pub)


def job(platform="telegram", brand="personal", destination="-1001234567890", **kw):
    value = {
        "job_id": "publish-20261026-test", "brand": brand, "platform": platform,
        "destination": destination, "text": "Research and products: original update",
        "approved": True, "approval_id": "OWNER-20261026-001"
    }
    value.update(kw)
    return value


def env(platform="telegram", brand="personal", destination="-1001234567890"):
    prefix = "MPW_SOCIAL_" + brand.upper() + "_" + platform.upper()
    return {
        prefix + "_VERIFIED_TARGETS": destination,
        prefix + "_TOKEN": ("123456789:" + "A"*35) if platform == "telegram" else "fake-discord-bot-token",
        "MPW_SOCIAL_EXECUTION_ENABLED": "1",
    }


class DirectSocialPublishingTests(unittest.TestCase):
    def test_default_readiness_is_false_and_no_io(self):
        report = pub.readiness(job(), {})
        self.assertFalse(report["can_execute"])
        self.assertFalse(any(report["checks"].values()))
        self.assertEqual(report["mode"], "preview_only")

    def test_brand_target_isolation(self):
        report = pub.readiness(job(brand="zomorod"), env())
        self.assertFalse(report["can_execute"])
        self.assertFalse(report["checks"]["owner_verified_destination"])
        self.assertFalse(report["checks"]["brand_token_configured"])

    def test_disallow_unapproved_and_disabled_gate(self):
        self.assertFalse(pub.readiness(job(approved=False), env())["can_execute"])
        self.assertFalse(pub.readiness(job(approval_id=""), env())["can_execute"])
        config = env()
        config["MPW_SOCIAL_EXECUTION_ENABLED"] = "0"
        self.assertFalse(pub.readiness(job(), config)["can_execute"])

    def test_restricted_profile_and_invalid_destination(self):
        with self.assertRaises(pub.PublicationBlocked):
            pub.readiness(job(text="Promote dr.mojtaba.rozegar"), env())
        with self.assertRaises(pub.PublicationBlocked):
            pub.readiness(job(destination="@x"), env())
        with self.assertRaises(pub.PublicationBlocked):
            pub.readiness(job(platform="discord", destination="https://discord.com"), env())

    def test_no_external_call_when_unapproved(self):
        with tempfile.TemporaryDirectory() as d:
            called = []
            def transport(request):
                called.append(request)
                return 200, b'{"ok":true,"result":{"message_id":1}}'
            with self.assertRaises(pub.PublicationBlocked):
                pub.publish(job(approved=False), ledger_path=Path(d) / "ledger.sqlite",
                            environ=env(), transport=transport)
            self.assertEqual(called, [])
            self.assertFalse((Path(d) / "ledger.sqlite").exists())

    def test_telegram_success_and_idempotent_lock(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "ledger.sqlite"
            requests = []
            def transport(request):
                requests.append(request)
                self.assertEqual(request.get_method(), "POST")
                self.assertEqual(json.loads(request.data)["chat_id"], "-1001234567890")
                return 200, b'{"ok":true,"result":{"message_id":347}}'
            result = pub.publish(job(), ledger_path=ledger, environ=env(), transport=transport)
            self.assertEqual(result["status"], "published")
            self.assertEqual(result["remote_id"], "347")
            with self.assertRaises(pub.PublicationBlocked):
                pub.publish(job(), ledger_path=ledger, environ=env(), transport=transport)
            self.assertEqual(len(requests), 1)

    def test_job_id_reuse_changes_are_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "ledger.sqlite"
            transport = lambda req: (200, b'{"ok":true,"result":{"message_id":1}}')
            pub.publish(job(), ledger_path=ledger, environ=env(), transport=transport)
            with self.assertRaises(pub.PublicationBlocked):
                pub.publish(job(text="changed"), ledger_path=ledger, environ=env(), transport=transport)

    def test_discord_posts_without_mass_mentions(self):
        target = "123456789012345678"
        request_inspect = []
        def transport(req):
            request_inspect.append(req)
            body = json.loads(req.data)
            self.assertEqual(body["allowed_mentions"], {"parse": []})
            self.assertEqual(req.full_url, "https://discord.com/api/v10/channels/" + target + "/messages")
            return 200, b'{"id":"123456789012345679"}'
        with tempfile.TemporaryDirectory() as d:
            result = pub.publish(job(platform="discord", destination=target, brand="mojplaywin"),
                                 ledger_path=Path(d) / "ledger.sqlite",
                                 environ=env("discord", "mojplaywin", target), transport=transport)
        self.assertEqual(result["remote_id"], "123456789012345679")
        self.assertEqual(len(request_inspect), 1)

    def test_ambiguous_response_no_retry(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "ledger.sqlite"
            calls = []
            def failed(req):
                calls.append(req)
                raise TimeoutError()
            with self.assertRaises(pub.PublishUncertain):
                pub.publish(job(), ledger_path=ledger, environ=env(), transport=failed)
            with self.assertRaises(pub.PublicationBlocked):
                pub.publish(job(), ledger_path=ledger, environ=env(), transport=failed)
            self.assertEqual(len(calls), 1)

    def test_private_ledger_storage_required(self):
        with tempfile.TemporaryDirectory() as d:
            import os
            private_dir = Path(d) / "unsafe"
            private_dir.mkdir(mode=0o755)
            os.chmod(private_dir, 0o755)
            with self.assertRaises(pub.PublicationBlocked):
                pub.publish(job(), ledger_path=private_dir / "ledger.sqlite",
                            environ=env(), transport=lambda req: (200, b'{}'))
            self.assertFalse((private_dir / "ledger.sqlite").exists())

    def test_unsupported_platform_is_not_fake_ready(self):
        for platform in ("instagram", "linkedin", "tiktok", "facebook", "researchgate"):
            with self.assertRaises(pub.PublicationBlocked):
                pub.readiness(job(platform=platform), env())


if __name__ == "__main__":
    unittest.main()
