"""Regression tests: allocation share cannot be negative or nonintegral."""
import unittest
from unittest.mock import patch

from scripts import audit_moj_asset_allocations as a


class AllocationWeightGuardTests(unittest.TestCase):
    def test_all_51_proposals_reconcile_to_exact_supply(self):
        program = a.audit()
        self.assertEqual(len(program["assets"]), 51)
        for asset in program["assets"].values():
            self.assertEqual(sum(int(v) for v in asset["allocation"].values()),
                             int(asset["supply"]))
            self.assertTrue(all(int(v) >= 0 for v in asset["allocation"].values()))
            self.assertFalse(asset["issued"])
            self.assertFalse(asset["liquidity_funded"])
        self.assertEqual(program["assets"]["mojoner"]["supply"], "24567856")

    def test_negative_weight_rejected_even_if_total_is_10000(self):
        invalid = dict(a.ALLOCATION_BPS)
        invalid["game_rewards"] = -1
        invalid["player_ecosystem_reserve"] += 3001
        with patch.dict(a.ALLOCATION_BPS, invalid, clear=True):
            with self.assertRaisesRegex(ValueError, "allocation_weight_invalid"):
                a.allocation_for_supply(24_567_856)

    def test_boolean_and_float_weights_rejected(self):
        for bad in (True, 1500.0, "1500", None):
            with self.subTest(bad=bad), patch.dict(a.ALLOCATION_BPS, {"unfunded_liquidity_reserve": bad}):
                with self.assertRaisesRegex(ValueError, "allocation_weight_invalid"):
                    a.allocation_for_supply(24_567_856)

    def test_extraneous_and_missing_category_rejected(self):
        for invalid in ({**a.ALLOCATION_BPS, "unexpected": 0},
                        {k:v for k,v in a.ALLOCATION_BPS.items() if k != "game_rewards"}):
            with patch.dict(a.ALLOCATION_BPS, invalid, clear=True):
                with self.assertRaisesRegex(ValueError, "allocation_categories_invalid"):
                    a.allocation_for_supply(24_567_856)

    def test_supply_type_and_sign_are_enforced(self):
        for bad in (0, -1, True, 1.0, "24567856"):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "invalid_supply"):
                a.allocation_for_supply(bad)

    def test_balanced_rounding_never_mints_extra_units(self):
        for count in (1, 2, 3, 99, 100_000_000_000, 10_000_000_000_000):
            allocation = a.allocation_for_supply(count)
            self.assertEqual(sum(allocation.values()), count)
            self.assertTrue(all(0 <= x <= count for x in allocation.values()))


if __name__ == "__main__":
    unittest.main()
