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
                          "shell=True", "shutil.copy", "open(\"wb\")",
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

    def test_quota_is_fixed_read_only_cli_not_shell(self):
        text = (ROOT / "scripts/mojprop_full_restore_capacity_readonly_c94.py").read_text()
        self.assertIn('["quota", "-wvu", ACCOUNT]', text)
        self.assertIn("timeout=6, check=True", text)
        self.assertNotIn("shell=True", text)

    def test_exact_quota_result_and_invalid_report_fail_closed(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from scripts import mojprop_full_restore_capacity_readonly_c94 as mod
        goodfs = SimpleNamespace(f_bavail=2_000_000,
                                 f_frsize=4096, f_favail=1000)
        good = SimpleNamespace(stdout="/dev/device 100 900000 1000000 1 1000 1500\n")
        bad = SimpleNamespace(stdout="/dev/device 100* 900000 1000000 1 1000 1500\n")
        with patch.object(mod.os, "open", return_value=10), \
             patch.object(mod.os, "fstatvfs", return_value=goodfs), \
             patch.object(mod.os, "close"), \
             patch("subprocess.run", return_value=good) as run:
            self.assertTrue(mod._quota_checked(1024 * 1024))
            self.assertEqual(run.call_args.args[0], ["quota", "-wvu", mod.ACCOUNT])
        with patch.object(mod.os, "open", return_value=10), \
             patch.object(mod.os, "fstatvfs", return_value=goodfs), \
             patch.object(mod.os, "close"), \
             patch("subprocess.run", return_value=bad):
            self.assertFalse(mod._quota_checked(1024 * 1024))

    def test_quota_program_missing_is_unknown_not_approved(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from scripts import mojprop_full_restore_capacity_readonly_c94 as mod
        fs = SimpleNamespace(f_bavail=2000000, f_frsize=4096, f_favail=1000)
        with patch.object(mod.os, "open", return_value=10), patch.object(mod.os, "fstatvfs", return_value=fs), patch.object(mod.os, "close"), patch("subprocess.run", side_effect=FileNotFoundError):
            allowed, reason = mod._quota_result(1024**2)
            self.assertFalse(allowed)
            self.assertEqual(reason, "quota_program_unavailable")

    def test_invalid_quota_record_reports_precise_blocker_without_leak(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from scripts import mojprop_full_restore_capacity_readonly_c94 as mod
        fs = SimpleNamespace(f_bavail=2000000, f_frsize=4096, f_favail=1000)
        result = SimpleNamespace(stdout="/dev/sda 20* 100 200 1 100 200" + chr(10))
        with patch.object(mod.os, "open", return_value=10), patch.object(mod.os, "fstatvfs", return_value=fs), patch.object(mod.os, "close"), patch("subprocess.run", return_value=result):
            allowed, reason = mod._quota_result(1024**2)
            self.assertFalse(allowed)
            self.assertEqual(reason, "quota_format_unrecognized")
            self.assertNotIn("/dev/", reason)

    def test_no_volume_entry_is_distinct_from_approved_quota(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from scripts import mojprop_full_restore_capacity_readonly_c94 as mod
        fs = SimpleNamespace(f_bavail=2000000, f_frsize=4096, f_favail=1000)
        result = SimpleNamespace(stdout="no fixed quota applied" + chr(10))
        with patch.object(mod.os, "open", return_value=10), patch.object(mod.os, "fstatvfs", return_value=fs), patch.object(mod.os, "close"), patch("subprocess.run", return_value=result):
            allowed, reason = mod._quota_result(1024**2)
            self.assertFalse(allowed)
            self.assertEqual(reason, "quota_volume_not_reported")

    def test_official_cpanel_uapi_quota_good_does_not_claim_restore(self):
        from scripts.mojprop_full_restore_capacity_readonly_c94 import _cpanel_quota_data_adequate
        data = {"result": {"status": 1, "data": {
            "under_quota_overall": 1, "under_megabyte_limit": 1,
            "under_inode_limit": 1, "megabyte_limit": "900",
            "megabytes_remain": "500", "inode_limit": 10000,
            "inodes_remain": 9000,
        }}}
        valid, reason = _cpanel_quota_data_adequate(data, 200_000_000)
        self.assertTrue(valid)
        self.assertEqual(reason, "cpanel_uapi_quota_verified")
        return data

    def test_cpanel_uapi_quota_unlimited_or_disabled_is_not_proof(self):
        from scripts.mojprop_full_restore_capacity_readonly_c94 import _cpanel_quota_data_adequate
        d = {"result": {"status": 1, "data": {
            "under_quota_overall": 1, "under_megabyte_limit": 1,
            "under_inode_limit": 1, "megabyte_limit": 0,
            "megabytes_remain": 0, "inode_limit": 0, "inodes_remain": 0,
        }}}
        valid, reason = _cpanel_quota_data_adequate(d, 1000)
        self.assertFalse(valid)
        self.assertEqual(reason, "cpanel_uapi_unlimited_or_disabled_unproven")

    def test_cpanel_uapi_quota_small_or_malformed_remains_closed(self):
        from scripts.mojprop_full_restore_capacity_readonly_c94 import _cpanel_quota_data_adequate
        basis = {"under_quota_overall": 1, "under_megabyte_limit": 1,
                 "under_inode_limit": 1, "megabyte_limit": 900,
                 "megabytes_remain": 100, "inode_limit": 10000,
                 "inodes_remain": 9000}
        for delta in ({}, {"megabytes_remain": "NaN"},
                      {"megabytes_remain": -1},
                      {"under_inode_limit": "1"},
                      {"inodes_remain": -1}):
            with self.subTest(delta=delta):
                d = dict(basis, **delta)
                good, reason = _cpanel_quota_data_adequate(
                    {"result": {"status": 1, "data": d}}, 200_000_000
                )
                self.assertFalse(good)

    def test_cpanel_uapi_fixed_read_only_method(self):
        text = (ROOT / "scripts/mojprop_full_restore_capacity_readonly_c94.py").read_text()
        self.assertIn('"Quota", "get_quota_info"', text)
        self.assertIn('"/usr/local/cpanel/bin/uapi"', text)
        self.assertIn('check=True, timeout=12', text)
        self.assertNotIn('"set_quota"', text)
        self.assertNotIn('"create"', text)


if __name__ == "__main__":
    unittest.main()
