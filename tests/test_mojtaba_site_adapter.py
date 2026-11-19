import json
import unittest
from ava_core import MojtabaBot
from ava_core.capabilities import ActionRequest
from core.mojtaba_site_adapter import site_capability
from mojtaba_identity import BOT_ID

class SiteAdapterTests(unittest.TestCase):
    def setUp(self):
        self.urls = []
        def transport(url):
            self.urls.append(url)
            return 200, "text/html", b"<html><head><title>site</title></head><body><h1>page</h1></body></html>"
        self.cap = site_capability(transport=transport)

    def bot(self, authorize=None):
        return MojtabaBot(owner_id="owner-1", brain=lambda _: "ok",
                          propose_goals=lambda _: (), capabilities=(self.cap,),
                          authorize_action=authorize)

    def req(self, operation, request_id="r1", owner="owner-1", arguments=None):
        return ActionRequest(request_id, owner, "site_observability", operation, arguments or {})

    def test_inventory_has_canonical_identity_and_no_network(self):
        bot = self.bot()
        receipt = bot.execute_action(self.req("inventory"))
        self.assertEqual(bot.bot_name, BOT_ID)
        self.assertEqual(json.loads(receipt.result.detail)["canonical_bot"], BOT_ID)
        self.assertEqual(self.urls, [])

    def test_network_requires_independent_authorization(self):
        with self.assertRaises(PermissionError):
            self.bot().execute_action(self.req("observe_public"))
        self.assertEqual(self.urls, [])

    def test_authorized_monitor_runs_fourteen_fixed_routes(self):
        bot = self.bot(lambda owner, request, op: op.effect == "read")
        receipt = bot.execute_action(self.req("observe_public"))
        self.assertEqual(len(self.urls), 14)
        self.assertTrue(receipt.result.success)
        self.assertFalse(receipt.independently_verified)
        self.assertFalse(json.loads(receipt.result.detail)["automatic_site_cleanup"])

    def test_owner_mismatch_denied(self):
        with self.assertRaises(PermissionError):
            self.bot().execute_action(self.req("inventory", owner="other-owner"))

    def test_replay_denied(self):
        bot = self.bot()
        request = self.req("inventory")
        bot.execute_action(request)
        with self.assertRaises(PermissionError):
            bot.execute_action(request)

    def test_override_target_denied(self):
        with self.assertRaises(ValueError):
            self.bot(lambda *_: True).execute_action(self.req("observe_public", arguments={"url":"https://example.org"}))
        self.assertEqual(self.urls, [])
