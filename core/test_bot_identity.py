"""Tests for unified identity without touching live agent or worker records."""

import unittest

from core.bot_identity import BOT_ID, BOT_NAME, canonical_bot_id, enforce_single_top_level_bot
from core.master_agent_capability_pack import MASTER_AGENT_CAPABILITY_PACK, capability_pack_prompt


class SingleBotIdentityTests(unittest.TestCase):
    def test_canonical_name_is_exact(self):
        self.assertEqual(BOT_NAME, "Mojtaba.bot.ai")
        self.assertEqual(BOT_ID, "mojtaba.bot.ai")

    def test_canonical_name_resolves(self):
        self.assertEqual(canonical_bot_id("Mojtaba.bot.ai"), BOT_ID)

    def test_legacy_public_name_resolves(self):
        self.assertEqual(canonical_bot_id("Mojtaba.bot"), BOT_ID)

    def test_case_and_whitespace_normalized(self):
        self.assertEqual(canonical_bot_id("  MOJTABA.BOT.AI  "), BOT_ID)

    def test_second_top_level_bot_rejected(self):
        with self.assertRaises(ValueError):
            enforce_single_top_level_bot(["Mojtaba.bot.ai", "another.bot"])

    def test_duplicate_top_level_bot_rejected(self):
        with self.assertRaises(ValueError):
            enforce_single_top_level_bot([BOT_NAME, BOT_NAME])

    def test_empty_top_level_registry_rejected(self):
        with self.assertRaises(ValueError):
            enforce_single_top_level_bot([])

    def test_internal_worker_not_treated_as_another_bot(self):
        with self.assertRaises(ValueError):
            canonical_bot_id("economic-master-agent")

    def test_single_registry_accepted(self):
        self.assertEqual(enforce_single_top_level_bot(["Mojtaba.bot.ai"]), BOT_ID)

    def test_master_charter_uses_same_identity(self):
        self.assertEqual(MASTER_AGENT_CAPABILITY_PACK["bot_id"], BOT_ID)
        self.assertIn(BOT_NAME, capability_pack_prompt())


if __name__ == "__main__":
    unittest.main()
