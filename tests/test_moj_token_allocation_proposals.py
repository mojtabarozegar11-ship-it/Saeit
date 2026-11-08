"""No proposed token allocation can exceed its fixed whole-token supply."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from moj_token_allocation_proposals import ALLOCATION_BPS, candidate_allocations


class CandidateAllocationTests(unittest.TestCase):
    def test_all_51_assets_preserve_exact_supply(self):
        result = candidate_allocations()
        self.assertEqual(len(result), 51)
        for name, row in result.items():
            with self.subTest(name=name):
                self.assertEqual(sum(map(int, row["allocations_tokens"].values())),
                                 int(row["total_supply_tokens"]))
                self.assertFalse(row["market_liquidity_committed"])
                self.assertFalse(row["player_rewards_transferable"])

    def test_mojoner_exact_total_and_whole_units(self):
        row = candidate_allocations()["mojoner"]
        self.assertEqual(int(row["total_supply_tokens"]), 24567856)
        self.assertTrue(all(int(v) >= 0 for v in row["allocations_tokens"].values()))

    def test_basis_points_are_complete(self):
        self.assertEqual(sum(ALLOCATION_BPS.values()), 10000)

    def test_invalid_weight_cannot_hide_inside_100_percent_total(self):
        sample = dict(ALLOCATION_BPS)
        sample["game_rewards"] = -1
        sample["player_ecosystem_reserve"] += 3001
        with patch.dict(ALLOCATION_BPS, sample, clear=True):
            with self.assertRaisesRegex(ValueError, "allocation_weight_invalid"):
                candidate_allocations()

    def test_invalid_weight_type_rejected(self):
        for bad in (True, 3000.0, "3000", None):
            with self.subTest(bad=bad):
                with patch.dict(ALLOCATION_BPS, {"game_rewards": bad}):
                    with self.assertRaisesRegex(ValueError, "allocation_weight_invalid"):
                        candidate_allocations()

    def test_missing_and_extra_allocations_rejected(self):
        missing = {key: value for key, value in ALLOCATION_BPS.items()
                   if key != "security_and_contingency"}
        extra = {**ALLOCATION_BPS, "unapproved": 0}
        for invalid in (missing, extra):
            with patch.dict(ALLOCATION_BPS, invalid, clear=True):
                with self.assertRaisesRegex(ValueError, "allocation_categories_invalid"):
                    candidate_allocations()


if __name__ == "__main__":
    unittest.main()
