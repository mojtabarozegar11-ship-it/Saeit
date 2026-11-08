"""No proposed token allocation can exceed its fixed whole-token supply."""
from pathlib import Path
import sys
import unittest
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


if __name__ == "__main__":
    unittest.main()
