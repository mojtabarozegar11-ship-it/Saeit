"""Tests for unified identity without touching live agent or worker records."""

import unittest

from core.bot_identity import (
    BOT_ID, BOT_NAME, canonical_bot_id, enforce_single_top_level_bot,
    summarize_internal_agent_registry,
)
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

    def test_multiple_worker_records_still_one_public_bot(self):
        report = summarize_internal_agent_registry([
            {"code": "economic-master-agent", "active": True},
            {"code": "moj_1ro_1", "active": True},
            {"code": "content-director", "active": False},
        ])
        self.assertEqual(report["declared_top_level_bot_count"], 1)
        self.assertEqual(report["django_component_records"], 3)
        self.assertEqual(report["active_django_component_records"], 2)
        self.assertTrue(report["economic_orchestrator_active"])
        self.assertTrue(report["factory_component_active"])
        self.assertFalse(report["runtime_process_topology_attested"])

    def test_absent_orchestrator_is_not_silently_claimed_live(self):
        report = summarize_internal_agent_registry([
            {"code": "content-director", "active": True},
        ])
        self.assertFalse(report["economic_orchestrator_record_present"])
        self.assertFalse(report["economic_orchestrator_active"])

    def test_reject_duplicate_component_code(self):
        with self.assertRaises(ValueError):
            summarize_internal_agent_registry([
                {"code": "worker", "active": True},
                {"code": "worker", "active": False},
            ])

    def test_reject_invalid_component_active_flag(self):
        with self.assertRaises(ValueError):
            summarize_internal_agent_registry([{"code": "worker", "active": 1}])

    def test_empty_component_registry_is_not_live_proof(self):
        report = summarize_internal_agent_registry([])
        self.assertEqual(report["django_component_records"], 0)
        self.assertFalse(report["runtime_process_topology_attested"])


if __name__ == "__main__":
    unittest.main()
