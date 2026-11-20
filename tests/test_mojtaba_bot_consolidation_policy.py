"""Static policy checks for the mojtaba.bot.ai trader consolidation gate."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "trading" / "MojTradeOmegaXDemoBot.cs"
LEGACY = ROOT / "trading" / "MojTradeDemoBot.cs"
MANIFEST = ROOT / "runtime" / "mojtaba_bot_disposition_sources_v1.json"


class MojtabaBotConsolidationPolicyTests(unittest.TestCase):
    def test_canonical_core_is_guarded(self) -> None:
        source = CANONICAL.read_text(encoding="utf-8")
        self.assertEqual(source.count("class MojtabaBotTradingCoreDemo"), 1)
        self.assertIn("if (Account.IsLive)", source)
        self.assertIn('[Parameter("Enable Demo Trading", DefaultValue = false)]', source)
        self.assertIn("protected override void OnException(Exception exception)", source)
        self.assertEqual(source.count("ExecuteMarketOrder("), 1)

    def test_legacy_root_is_not_canonical(self) -> None:
        source = LEGACY.read_text(encoding="utf-8")
        self.assertNotIn("class MojtabaBotTradingCoreDemo", source)
        self.assertIn("LEGACY RETAINED FOR ROLLBACK EVIDENCE ONLY", source)

    def test_manifest_keeps_deletion_blocked(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        registry = manifest["trader_consolidation_registry"]
        self.assertEqual(manifest["canonical_bot_id"], "mojtaba.bot.ai")
        self.assertEqual(
            registry["activation_policy"],
            "blocked_until_consolidated_and_verified",
        )
        self.assertEqual(
            registry["deletion_policy"],
            "delete_only_after_backup_and_verified_replacement",
        )
        candidate = next(
            item for item in registry["deletion_candidates"]
            if item["path"] == "trading/MojTradeDemoBot.cs"
        )
        self.assertEqual(candidate["current_status"], "retained_blocked")
        self.assertEqual(len(candidate["delete_when"]), 5)
        self.assertIn("No recursive deletion", registry["deletion_scope_rule"])


if __name__ == "__main__":
    unittest.main()
