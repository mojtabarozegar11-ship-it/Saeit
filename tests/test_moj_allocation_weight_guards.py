"""Regression tests: allocation share cannot be negative or nonintegral."""
import unittest
from unittest.mock import patch

from scripts import audit_moj_asset_allocations as a
from scripts.moj_token_allocation_proposals import candidate_allocations


class AllocationWeightGuardTests(unittest.TestCase):
    def test_independent_audit_matches_canonical_allocation_categories(self):
        audited = a.audit()["assets"]
        planned = candidate_allocations()
        self.assertEqual(set(audited), set(planned))
        for asset_id, row in audited.items():
            with self.subTest(asset_id=asset_id):
                self.assertEqual(row["allocation"], planned[asset_id]["allocations_tokens"])

    def test_divergent_audit_weights_rejected_even_if_still_sum_to_100_percent(self):
        invalid = dict(a.ALLOCATION_BPS)
        invalid["game_rewards"] += 100
        invalid["security_and_contingency"] -= 100
        with patch.dict(a.ALLOCATION_BPS, invalid, clear=True):
            with self.assertRaisesRegex(ValueError, "allocation_proposal_mismatch"):
                a.audit()

    def test_audit_discloses_unfunded_liquidity_and_unlocked_treasury(self):
        row = a.audit()["assets"]["mojoner"]
        self.assertIn("liquidity_reserve_unfunded", row["allocation"])
        self.assertIn("development_treasury_not_yet_locked", row["allocation"])
        self.assertFalse(row["treasury_timelock_deployed"])
        self.assertFalse(row["treasury_vesting_enforced_onchain"])
        self.assertFalse(row["player_rewards_transferable"])

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
            with self.subTest(bad=bad), patch.dict(a.ALLOCATION_BPS, {"liquidity_reserve_unfunded": bad}):
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
