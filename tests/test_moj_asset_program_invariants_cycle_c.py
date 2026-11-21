"""Offline-only regression checks for Mojoner and 50 candidate assets."""
import unittest
from scripts.moj_asset_registry import (
    generate_program, validate_program, offline_release_readiness,
    series_supply, validate_offline_allocations,
)


class AssetProgramRegression(unittest.TestCase):
    def test_owner_fixed_supply_and_no_issuance(self):
        program = generate_program()
        self.assertEqual(len(program["assets"]), 51)
        self.assertEqual(program["assets"][0]["supply_tokens"], "24567856")
        self.assertTrue(all(a["issuance_state"] == "not_issued" for a in program["assets"]))
        self.assertFalse(offline_release_readiness(program)["release_ready"])

    def test_series_endpoints(self):
        self.assertEqual(series_supply(1), 100_000_000_000)
        self.assertEqual(series_supply(50), 10_000_000_000_000)

    def test_forged_revenue_rejected(self):
        program = generate_program()
        program["verified_income"] = "1"
        with self.assertRaisesRegex(ValueError, "unverified_issuance_or_income_claim"):
            validate_program(program)

    def test_allocation_overflow_rejected(self):
        program = generate_program()
        allocations = {a["id"]: {"treasury": a["supply_tokens"]} for a in program["assets"]}
        allocations["mojoner"]["treasury"] = "24567857"
        with self.assertRaisesRegex(ValueError, "allocation_supply_mismatch"):
            validate_offline_allocations(program, allocations)


if __name__ == "__main__":
    unittest.main()
