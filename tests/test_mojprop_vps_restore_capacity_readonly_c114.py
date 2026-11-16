"""C114: synthetic metadata only. Does not contact VPS, cPanel or MariaDB."""
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import mojprop_vps_restore_capacity_readonly_c114 as guard

ROOT = Path(__file__).resolve().parents[1]


def mount(home, separate=0, candidate=0, count=0, complete=True):
    return {
        "classification": "READ_ONLY_MPW_VPS_DISTINCT_LOCAL_MOUNTS",
        "home_free_bytes": home,
        "largest_independent_free_bytes": separate,
        "independent_devices_with_write_hint_and_size_floor": candidate,
        "independent_local_device_count": count,
        "inventory_complete": complete,
    }


class MojPropVpsRestoreCapacityTests(unittest.TestCase):
    def test_01_exact_minimum_is_only_a_lower_bound(self):
        self.assertEqual(guard.MIN_RESTORE_LOWER_BOUND // guard.MIB, 16640)
        self.assertEqual(guard.MIN_KNOWN_DB_LOWER_BOUND, 8 * guard.GIB)

    def test_02_home_under_16gib_fails_lower_bound(self):
        r = guard.classify_mounts(mount(2 * guard.GIB), True, True)
        self.assertFalse(r["home_above_minimum_screen"])
        self.assertEqual(r["screen_result"], "no_known_location_meets_minimum")

    def test_03_exact_16gib_plus_headroom_is_still_not_enough(self):
        r = guard.classify_mounts(mount(guard.MIN_RESTORE_LOWER_BOUND), True, True)
        self.assertFalse(r["home_above_minimum_screen"])

    def test_04_home_above_floor_still_never_proves_restore(self):
        r = guard.classify_mounts(mount(20 * guard.GIB), True, True)
        self.assertTrue(r["home_above_minimum_screen"])
        self.assertEqual(r["screen_result"], "at_least_one_size_candidate_unproven")
        self.assertFalse(r["restore_destination_verified"])
        self.assertFalse(r["production_release_authorized"])

    def test_05_independent_40gib_screen_is_separate_device(self):
        r = guard.classify_mounts(
            mount(1 * guard.GIB, separate=45 * guard.GIB, candidate=1, count=1),
            True, True)
        self.assertFalse(r["home_above_minimum_screen"])
        self.assertTrue(r["independent_local_above_minimum_screen"])
        self.assertTrue(r["independent_40gib_candidate_with_write_hint"])
        self.assertFalse(r["restoration_test_performed"])

    def test_06_an_independent_size_hint_is_not_writable_proof(self):
        r = guard.classify_mounts(
            mount(2 * guard.GIB, separate=35 * guard.GIB, candidate=0, count=1),
            True, True)
        self.assertTrue(r["independent_local_above_minimum_screen"])
        self.assertFalse(r["independent_40gib_candidate_with_write_hint"])
        self.assertFalse(r["restore_destination_verified"])

    def test_07_incomplete_mount_inventory_fails_closed(self):
        r = guard.classify_mounts(
            mount(50 * guard.GIB, separate=50 * guard.GIB, candidate=1,
                  count=1, complete=False), True, True)
        self.assertFalse(r["home_above_minimum_screen"])
        self.assertEqual(r["screen_result"], "incomplete_mount_inventory")

    def test_08_unknown_runner_or_wrong_factory_cannot_use_mounts(self):
        data = mount(50 * guard.GIB)
        for owner, factory in ((False, True), (True, False), (False, False)):
            with self.subTest(owner=owner, factory=factory):
                r = guard.classify_mounts(data, owner, factory)
                self.assertEqual(r["screen_result"], "unverified_context")
                self.assertFalse(r["home_above_minimum_screen"])

    def test_09_python_bool_is_not_a_valid_byte_count(self):
        r = guard.classify_mounts(mount(True), True, True)
        self.assertEqual(r["screen_result"], "unverified_mount_metadata")
        self.assertFalse(r["home_above_minimum_screen"])

    def test_10_unbounded_independent_hint_not_accepted(self):
        r = guard.classify_mounts(mount(1, separate=-1), True, True)
        self.assertEqual(r["screen_result"], "unverified_mount_metadata")

    def test_11_malformed_candidates_cannot_create_a_green_status(self):
        r = guard.classify_mounts(mount(1, separate=45 * guard.GIB,
                                         candidate=2, count=1), True, True)
        self.assertEqual(r["screen_result"], "unverified_mount_metadata")
        self.assertFalse(r["independent_40gib_candidate_with_write_hint"])

    def test_12_bounded_buckets_are_not_exact_bytes(self):
        self.assertEqual(guard.bounded_gib(0), "0-2")
        self.assertEqual(guard.bounded_gib(3 * guard.GIB), "2-4")
        self.assertEqual(guard.bounded_gib(9 * guard.GIB), "8-16")
        self.assertEqual(guard.bounded_gib(41 * guard.GIB), ">=40")
        self.assertEqual(guard.bounded_gib(True), "unknown")

    def test_13_report_never_contains_customer_or_private_mount_paths(self):
        r = guard.classify_mounts(mount(2 * guard.GIB, separate=42 * guard.GIB,
                                         candidate=1, count=1), True, True)
        dumped = json.dumps(r)
        for path in ("/home/githubops", "/mnt/", "/dev/", "database_password",
                     "factory-runtime"):
            self.assertNotIn(path, dumped)

    def test_14_all_operation_and_finance_flags_are_false_even_for_40gib(self):
        r = guard.classify_mounts(mount(100 * guard.GIB, 90 * guard.GIB,
                                         candidate=1, count=1), True, True)
        for flag in ("restore_destination_verified", "restoration_test_performed",
                     "encryption_and_key_recovery_verified",
                     "tenant_or_process_isolation_verified",
                     "live_services_modified", "database_or_customer_bytes_read",
                     "files_created_or_deleted", "production_release_authorized",
                     "customer_payment_collected"):
            self.assertFalse(r[flag])

    def test_15_wrong_factory_owner_does_not_collect_mount_metadata(self):
        with patch.object(guard.pwd, "getpwuid",
                          return_value=SimpleNamespace(pw_name="not-githubops")), patch.object(
                guard, "inspect", side_effect=AssertionError("MUST NOT RUN")):
            r = guard.run()
        self.assertFalse(r["owner_verified"])
        self.assertEqual(r["screen_result"], "unverified_context")

    def test_16_source_is_local_metadata_only_with_no_write_path(self):
        source = (ROOT / "scripts/mojprop_vps_restore_capacity_readonly_c114.py").read_text()
        for forbidden in ("requests.post(", "subprocess.run(", "os.system(",
                          ".unlink(", ".rmdir(", ".mkdir(", "shutil.copy",
                          ".write_bytes(", ".write_text(", "execute_sql",
                          "mariadb-dump", "mysqldump", "sendrawtransaction"):
            self.assertNotIn(forbidden, source)
        self.assertIn("from scripts.mpw_vps_mount_capacity_readonly_20261105 import inspect", source)


if __name__ == "__main__":
    unittest.main()
