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

    def test_04_coarse_threshold_evidence_is_bounded(self):
        self.assertEqual(probe.threshold_flags(16 * 1024**3), {
            "at_least_16gib": True,
            "at_least_32gib": False,
            "at_least_40gib": False,
        })
        self.assertFalse(any(probe.threshold_flags(None).values()))

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
                state, band = probe.category_usage(path, runner=run)
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


    def test_15_cpanel_json_float_megabytes_match_c94_contract(self):
        doc = {"result":{"status":1,"data":{
            "under_quota_overall":"1","under_megabyte_limit":"1",
            "under_inode_limit":"1","megabyte_limit":700.0,
            "megabytes_remain":500.0}}}
        with patch.object(probe.subprocess, "run", return_value=SimpleNamespace(
                stdout=json.dumps(doc))):
            self.assertEqual(probe._quota_bytes(), 500_000_000)

    def test_16_staged_probe_identifies_db_vs_quota_without_raw_values(self):
        source = (ROOT / "scripts/mojprop_quota_gap_inventory_readonly_c113.py").read_text()
        self.assertIn('result["probe_stage"] = "db_metadata"', source)
        self.assertIn('result["probe_stage"] = "uapi_quota"', source)
        self.assertIn('result["probe_stage"] = "completed"', source)
        self.assertIn('"production_deploy_authorized": False', source)


    def test_17_cpanel_backup_listing_is_bounded_and_never_leaks_names(self):
        payload = {"result": {"status": 1, "data": [
            {"file": "private-personal-customer-data-123.sql.gz", "size": 999}
        ]}}
        with patch.object(probe.subprocess, "run", return_value=SimpleNamespace(
                stdout=json.dumps(payload))) as run:
            result = probe._backup_inventory_readonly()
        self.assertEqual(result["status"], "user_list_nonempty_unverified")
        self.assertEqual(result["count_band"], "1-10")
        self.assertNotIn("private-personal", json.dumps(result))
        self.assertFalse(result["provider_managed_backups_verified"])
        self.assertFalse(result["independent_restore_verified"])
        self.assertEqual(run.call_args.args[0],
                         [probe.UAPI, "--output=json", "Backup", "list_backups"])
        self.assertEqual(run.call_args.kwargs["env"], probe.ENV)
        self.assertTrue(run.call_args.kwargs["check"])

    def test_18_empty_user_backups_must_not_be_reported_as_no_host_backup(self):
        with patch.object(probe.subprocess, "run", return_value=SimpleNamespace(
                stdout=json.dumps({"result": {"status": 1, "data": []}}))):
            result = probe._backup_inventory_readonly()
        self.assertEqual(result["status"], "empty_list_not_host_backup_proof")
        self.assertEqual(result["count_band"], "0")
        self.assertFalse(result["provider_managed_backups_verified"])

    def test_19_fail_closed_on_invalid_backup_metadata_or_api_error(self):
        for response in ('{"result":{"status":0,"data":[]}}',
                         '{"result":{"status":1,"data":["bad"]}}',
                         '{"result":{"status":1,"data":{}}}',
                         '{"result":null}', "not-json"):
            with self.subTest(response=response):
                with patch.object(probe.subprocess, "run",
                                  return_value=SimpleNamespace(stdout=response)):
                    result = probe._backup_inventory_readonly()
                self.assertIn(result["status"],
                              ("feature_unavailable_or_api_failed",
                               "invalid_index", "invalid_response",
                               "invalid_json"))
                self.assertFalse(result["release_authorized"])


    def test_20_jetbackup_index_no_cli_is_unknown_not_no_backup(self):
        with patch.object(probe.Path, "is_file", return_value=False):
            outcome = probe._jetbackup_inventory_readonly()
        self.assertEqual(outcome["status"], "cli_unavailable")
        self.assertFalse(outcome["provider_backup_restorability_verified"])
        self.assertFalse(outcome["independent_restore_verified"])

    def test_21_jetbackup_listing_requires_correct_tenant_and_never_logs_data(self):
        response = {"success": 1, "data": {"backups": [
            {"account": probe.OWNER, "name": "private-data-do-not-log",
             "created": "2026-11-16T00:00:00Z", "size": 1234}]}}
        with patch.object(probe.Path, "is_file", return_value=True):
            with patch.object(probe.Path, "is_symlink", return_value=False):
                with patch.object(probe.subprocess, "run",
                                  return_value=SimpleNamespace(
                                      stdout=json.dumps(response))) as call:
                    outcome = probe._jetbackup_inventory_readonly()
        self.assertEqual(outcome["status"], "account_full_backups_listed_unverified")
        self.assertEqual(outcome["count_band"], "1-10")
        self.assertNotIn("private-data", json.dumps(outcome))
        self.assertEqual(call.call_args.args[0][1:],
                         ["-F", "listBackups", "-D", "type=1&contains=511",
                          "-O", "json"])
        self.assertFalse(outcome["provider_backup_restorability_verified"])
        response["data"]["backups"][0]["account"] = "another-tenant"
        with patch.object(probe.Path, "is_file", return_value=True):
            with patch.object(probe.Path, "is_symlink", return_value=False):
                with patch.object(probe.subprocess, "run",
                                  return_value=SimpleNamespace(
                                      stdout=json.dumps(response))):
                    denied = probe._jetbackup_inventory_readonly()
        self.assertEqual(denied["status"], "unverified_account_scope")
        self.assertEqual(denied["count_band"], "unknown")


if __name__ == "__main__":
    unittest.main()
