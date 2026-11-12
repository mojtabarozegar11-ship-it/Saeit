import unittest

from ava_core.identity import BOT_ID
from command_center.catalog import MODULES, AGENT_SETTINGS, localized
from command_center.unified_identity import identity_snapshot, public_bot_identity


class UnifiedIdentityTests(unittest.TestCase):
    def test_only_one_public_bot_in_navigation(self):
        self.assertEqual(BOT_ID, "mojtaba.bot.ai")
        self.assertEqual(len(MODULES), 17)
        ids = [row[0] for row in MODULES]
        self.assertEqual(ids.count("unified_bot"), 1)
        self.assertNotIn("master", ids)
        self.assertNotIn("agents", ids)
        self.assertNotIn("bots", ids)
        self.assertEqual(len(localized(MODULES, "fa")), 17)
        self.assertEqual(len(localized(AGENT_SETTINGS, "en")), 10)

    def test_public_envelope_is_shared_with_module_directory(self):
        header = public_bot_identity()
        self.assertEqual(header["identity"], BOT_ID)
        self.assertEqual(header["identity_count"], 1)
        self.assertIsNone(header["runtime_verified"])
        self.assertEqual(header["integration_state"], "unverified")
        self.assertEqual(identity_snapshot([], 0)["bot"], header)

    def test_dashboard_uses_canonical_bot_identity_context(self):
        from pathlib import Path
        path = Path(__file__).resolve().parents[1] / "templates" / "command_center" / "dashboard.html"
        template = path.read_text(encoding="utf-8")
        self.assertNotIn("mojtaba.bot.ai", template)
        self.assertIn("{{ bot_identity }}", template)
        self.assertIn("{{ bot_identity|escapejs }}", template)
        self.assertIn("data?.bot?.identity!==publicBotId", template)

    def test_source_rows_are_not_claimed_as_new_bots(self):
        raw = [{"id": 9, "code": "trading-legacy", "name": "Old robot",
                "mission": "Trade", "risk_level": "high", "active": True}]
        snapshot = identity_snapshot(raw, 1)
        self.assertEqual(snapshot["bot"]["identity_count"], 1)
        self.assertEqual(snapshot["bot"]["identity"], BOT_ID)
        self.assertIsNone(snapshot["bot"]["runtime_verified"])
        self.assertEqual(snapshot["modules"][0]["module_code"], "trading-legacy")
        self.assertEqual(snapshot["modules"][0]["source_name"], "Old robot")
        self.assertIsNone(snapshot["modules"][0]["integration_verified"])
        self.assertNotIn("agents", snapshot)

    def test_pagination_and_no_registered_modules(self):
        self.assertTrue(identity_snapshot([], 201)["truncated"])
        self.assertFalse(identity_snapshot([], 0)["truncated"])
        rows = [{"id": 2, "code": "writer", "name": "Old writer",
                 "mission": "Write", "risk_level": "low", "active": True}]
        first = identity_snapshot(rows, 2)
        self.assertEqual(first["next_offset"], 1)
        last = identity_snapshot(rows, 2, offset=1)
        self.assertIsNone(last["next_offset"])


if __name__ == "__main__":
    unittest.main()
