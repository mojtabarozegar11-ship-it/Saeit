"""Moj Prop real backup feasibility cannot be fabricated from source-only CI."""
import unittest
from pathlib import Path
from scripts.mojprop_full_restore_capacity_readonly_c94 import HEADROOM, capacity_flags

ROOT = Path(__file__).resolve().parents[1]


class FullRestoreCapacityPreflightTests(unittest.TestCase):
    def test_exact_two_times_db_and_headroom_is_only_capacity_not_restore(self):
        db = 500 * 1024**2
        r = capacity_flags(free_bytes=2 * db + HEADROOM, db_bytes=db,
                           quota_accepted=True)
        self.assertTrue(r["combined_capacity_preflight_passed"])
        for key in ("full_database_dump_taken", "isolated_database_restore_executed",
                    "media_and_app_recovery_proven", "passenger_tenant_isolation_proven",
                    "production_deployment_authorized",
                    "customer_payment_collected_by_probe"):
            self.assertFalse(r[key])

    def test_one_byte_below_minimum_is_not_sufficient(self):
        db = 200 * 1024**2
        r = capacity_flags(free_bytes=2 * db + HEADROOM - 1,
                           db_bytes=db, quota_accepted=True)
        self.assertFalse(r["filesystem_capacity_heuristic_passed"])
        self.assertFalse(r["combined_capacity_preflight_passed"])

    def test_os_free_space_without_owning_account_quota_is_not_enough(self):
        r = capacity_flags(free_bytes=10**10, db_bytes=10**8,
                           quota_accepted=False)
        self.assertTrue(r["filesystem_capacity_heuristic_passed"])
        self.assertFalse(r["combined_capacity_preflight_passed"])

    def test_quota_truthy_string_or_int_does_not_authorize(self):
        for quota in ("yes", "True", 1, [], None):
            with self.subTest(quota=quota):
                r = capacity_flags(free_bytes=10**10, db_bytes=10**8,
                                   quota_accepted=quota)
                self.assertFalse(r["combined_capacity_preflight_passed"])

    def test_missing_database_estimate_is_unknown_not_small(self):
        for bad in (0, -1, None, True, "500", 0.5, 200 * 1024**4):
            with self.subTest(db=bad):
                r = capacity_flags(free_bytes=10**10, db_bytes=bad,
                                   quota_accepted=True)
                self.assertIsNone(r["filesystem_capacity_heuristic_passed"])
                self.assertFalse(r["connected_db_table_size_estimate_available"])
                self.assertFalse(r["combined_capacity_preflight_passed"])

    def test_missing_free_bytes_is_unknown(self):
        for bad in (-1, None, True, "1GB"):
            with self.subTest(free=bad):
                r = capacity_flags(free_bytes=bad, db_bytes=10**8,
                                   quota_accepted=True)
                self.assertIsNone(r["filesystem_capacity_heuristic_passed"])
                self.assertFalse(r["combined_capacity_preflight_passed"])

    def test_live_script_never_writes_backups_payments_or_changes_merchant_flags(self):
        text = (ROOT / "scripts/mojprop_full_restore_capacity_readonly_c94.py").read_text()
        for forbidden in ("objects.create(", ".save(", "requests.post(",
                          "broadcasttransaction", "sendrawtransaction",
                          "subprocess.run(", "shutil.copy", "open(\"wb\")",
                          "MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED=True"):
            self.assertNotIn(forbidden, text)
        self.assertIn("FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()", text)
        self.assertIn("connection.execute_wrapper(select_only)", text)
        self.assertIn("no_host_or_database_writes", text)

    def test_no_restoration_or_release_claim_in_result_contract(self):
        r = capacity_flags(free_bytes=10**10, db_bytes=10**8,
                           quota_accepted=True)
        self.assertFalse(r["isolated_database_restore_executed"])
        self.assertFalse(r["passenger_tenant_isolation_proven"])
        self.assertFalse(r["production_deployment_authorized"])


if __name__ == "__main__":
    unittest.main()
