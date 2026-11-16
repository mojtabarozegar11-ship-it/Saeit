"""No-network tests for owner-only C113 quota gap and disk category audit."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import mojprop_quota_gap_inventory_readonly_c113 as probe

ROOT = Path(__file__).resolve().parents[1]


class MojPropQuotaGapInventoryTests(unittest.TestCase):
    def test_01_empty_quota_gap_bucket_is_zero(self):
        self.assertEqual(probe.bucket_bytes(0), "0")

    def test_02_positive_one_mib_is_reported_as_bucket(self):
        self.assertEqual(probe.bucket_bytes(1), "1-64")
        self.assertEqual(probe.bucket_bytes(64 * 1024**2), "1-64")
        self.assertEqual(probe.bucket_bytes(64 * 1024**2 + 1), "65-256")

    def test_03_large_or_invalid_buckets_are_bounded(self):
        self.assertEqual(probe.bucket_bytes(9000 * 1024**2), ">8192")
        self.assertEqual(probe.bucket_bytes(None), "unknown")
        self.assertEqual(probe.bucket_bytes(True), "unknown")
        self.assertEqual(probe.bucket_bytes(-10), "unknown")

    def test_04_uapi_permitted_call_is_same_owner_read_only(self):
        with patch.object(probe.subprocess, "run", return_value=SimpleNamespace(
                stdout='{"result":{"status":1,"data":{"under_quota_overall":"1",'
                       '"under_megabyte_limit":"1","under_inode_limit":"1",'
                       '"megabyte_limit":"700","megabytes_remain":"500"}}}')) as run:
            free = probe._quota_bytes()
        self.assertEqual(free, 500_000_000)
        self.assertEqual(run.call_args.args[0],
                         ["/usr/bin/uapi", "--output=json", "Quota", "get_quota_info"])
        self.assertEqual(run.call_args.kwargs["env"], probe.ENV)
        self.assertTrue(run.call_args.kwargs["check"])
        self.assertEqual(run.call_args.kwargs["timeout"], 15)
        self.assertNotIn("CPANEL_API_TOKEN", probe.ENV)

    def test_05_invalid_uapi_quota_status_rejected(self):
        invalid = {"result": {"status":1,"data":{
            "under_quota_overall":"0","under_megabyte_limit":"1",
            "under_inode_limit":"1","megabyte_limit":"700",
            "megabytes_remain":"500"}}}
        with patch.object(probe.subprocess, "run", return_value=SimpleNamespace(
                stdout=json.dumps(invalid))):
            with self.assertRaises(ValueError):
                probe._quota_bytes()

    def test_06_missing_or_unlimited_quota_is_not_capacity(self):
        for value in ("0", 0, "NaN"):
            with self.subTest(value=value):
                data = {"result":{"status":1,"data":{
                    "under_quota_overall":1,"under_megabyte_limit":1,
                    "under_inode_limit":1,"megabyte_limit":value,
                    "megabytes_remain":"500"}}}
                with patch.object(probe.subprocess, "run", return_value=SimpleNamespace(
                        stdout=json.dumps(data))):
                    with self.assertRaises(ValueError):
                        probe._quota_bytes()

    def test_07_unknown_or_ambiguous_flag_is_denied(self):
        for value in ("01", "true", True, None):
            with self.subTest(value=value):
                data = {"result":{"status":1,"data":{
                    "under_quota_overall":value,"under_megabyte_limit":"1",
                    "under_inode_limit":"1","megabyte_limit":"700",
                    "megabytes_remain":"500"}}}
                with patch.object(probe.subprocess, "run", return_value=SimpleNamespace(
                        stdout=json.dumps(data))):
                    with self.assertRaises(ValueError):
                        probe._quota_bytes()

    def test_08_du_category_is_bounded_and_path_never_reported(self):
        with tempfile.TemporaryDirectory() as home:
            path = Path(home)
            with patch.object(probe.subprocess, "run",
                              return_value=SimpleNamespace(stdout="10240\t"+str(path)+"\n")) as run:
                state, band = probe.category_usage(path)
            self.assertEqual((state, band), ("counted", "1-64"))
            self.assertEqual(run.call_args.args[0],
                             ["/usr/bin/du", "-sk", "--", str(path)])
            self.assertFalse(run.call_args.kwargs.get("shell", False))

    def test_09_symlink_dir_not_traversed(self):
        with tempfile.TemporaryDirectory() as home:
            path = Path(home)
            target = path / "backups"
            target.symlink_to(path, target_is_directory=True)
            state, band = probe.category_usage(target)
            self.assertEqual((state, band), ("unavailable", "unknown"))

    def test_10_untrusted_du_result_is_unknown(self):
        with tempfile.TemporaryDirectory() as home:
            with patch.object(probe.subprocess, "run",
                              return_value=SimpleNamespace(stdout="not a number")):
                self.assertEqual(probe.category_usage(Path(home),
                                                      runner=probe.subprocess.run),
                                 ("unavailable", "unknown"))

    def test_11_fixed_inventory_has_no_arbitrary_user_path(self):
        self.assertEqual(len(probe.CANDIDATES), 8)
        self.assertEqual(len({p for _, p in probe.CANDIDATES}), 8)
        for label, path in probe.CANDIDATES:
            self.assertGreaterEqual(len(path.relative_to(probe.HOME).parts), 1)
            self.assertFalse(path == probe.HOME)
            self.assertTrue(label.replace("_", "").isalnum())

    def test_12_source_never_writes_or_deletes_files(self):
        text = (ROOT / "scripts/mojprop_quota_gap_inventory_readonly_c113.py").read_text()
        for forbidden in ("shutil.rmtree", ".unlink(", ".write_text(",
                          ".write_bytes(", "shell=True", "requests.post(",
                          "objects.create(", "sendrawtransaction", "os.system("):
            self.assertNotIn(forbidden, text)

    def test_13_contract_denies_unsupported_restore_and_sale(self):
        text = (ROOT / "scripts/mojprop_quota_gap_inventory_readonly_c113.py").read_text()
        for field in ("database_dump_created","isolated_restore_executed",
                      "customer_records_accessed","files_deleted_or_modified",
                      "production_deploy_authorized","payment_collected"):
            self.assertIn('"' + field + '": False', text)

    def test_14_required_capacity_formula_keeps_double_db_and_headroom(self):
        text = (ROOT / "scripts/mojprop_quota_gap_inventory_readonly_c113.py").read_text()
        self.assertIn("needed = 2 * db + HEADROOM", text)
        self.assertEqual(probe.HEADROOM, 256 * 1024**2)


if __name__ == "__main__":
    unittest.main()
