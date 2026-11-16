"""Offline tests for the owner-only read-only cPanel Quota cause probe."""
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from scripts import mojprop_cpanel_uapi_cause_readonly_c111 as probe

ROOT = Path(__file__).resolve().parents[1]


def completed(body, code=0):
    return SimpleNamespace(stdout=body, stderr="PRIVATE SECRET MUST NOT LEAK",
                           returncode=code)


class MojPropUapiCauseReadOnlyTests(unittest.TestCase):
    def run_case(self, answer, *, code=0):
        command = probe.COMMANDS[0]
        executor = Mock(return_value=completed(answer, code))
        result = probe.classify(command, runner=executor)
        args, kwargs = executor.call_args
        self.assertEqual(args, (list(command),))
        self.assertEqual(kwargs["env"], probe.ENV)
        self.assertTrue(kwargs["capture_output"])
        self.assertFalse(kwargs["check"])
        self.assertEqual(kwargs["timeout"], 12)
        self.assertNotIn("CPANEL_API_TOKEN", kwargs["env"])
        self.assertNotIn("PRIVATE SECRET", json.dumps(result))
        return result

    def test_01_owner_context_is_fixed_and_no_inherited_secret(self):
        self.assertEqual(probe.ENV["HOME"], "/home/zomorod2")
        self.assertEqual(probe.ENV["USER"], "zomorod2")
        self.assertEqual(probe.ENV["LOGNAME"], "zomorod2")
        self.assertEqual(set(probe.ENV), {"HOME", "USER", "LOGNAME", "LC_ALL", "PATH"})

    def test_02_only_two_read_only_quota_methods_are_whitelisted(self):
        self.assertEqual(len(probe.COMMANDS), 2)
        for command in probe.COMMANDS:
            self.assertEqual(command[-2:], ("Quota", "get_quota_info"))
            self.assertEqual(command[0], "/usr/local/cpanel/bin/uapi")
            self.assertNotIn("set_quota", command)
            self.assertNotIn("create", command)
            self.assertNotIn("delete", command)

    def test_03_valid_success_data_is_not_capacity_authorization(self):
        r = self.run_case('{"result":{"status":1,"data":{"megabytes_remain":900}}}')
        self.assertEqual(r["outcome"], "uapi_data_present")
        self.assertTrue(r["uapi_status_ok"])
        self.assertTrue(r["data_object_present"])
        self.assertEqual(r["quota_shape"]["quantities"]["megabytes_remain"], "positive")
        self.assertNotIn("900", json.dumps(r))

    def test_04_status_zero_permission_error_is_sanitized(self):
        r = self.run_case('{"result":{"status":0,"errors":["Permission denied: secret-test-xyz"]}}')
        self.assertEqual(r["outcome"], "uapi_status_denied")
        self.assertEqual(r["error_class"], "permission")
        self.assertNotIn("secret-test", str(r))

    def test_05_unsupported_api_error_is_not_accepted(self):
        r = self.run_case('{"result":{"status":0,"errors":["Unknown module Quota"]}}')
        self.assertEqual(r["error_class"], "unsupported_api")
        self.assertFalse(r["uapi_status_ok"])

    def test_06_json_on_nonzero_exit_is_identified(self):
        r = self.run_case('{"result":{"status":0,"errors":["Access denied"]}}', code=1)
        self.assertEqual(r["outcome"], "nonzero_json")
        self.assertTrue(r["exit_nonzero"])

    def test_07_plaintext_on_nonzero_exit_is_not_logged(self):
        r = self.run_case("PRIVATE SECRET KEY invalid command", code=2)
        self.assertEqual(r["outcome"], "nonzero_nonjson")
        self.assertNotIn("PRIVATE SECRET", str(r))

    def test_08_nonjson_zero_exit_is_not_trusted(self):
        self.assertEqual(self.run_case("Ready")["outcome"], "zero_nonjson")

    def test_09_missing_data_is_distinct_from_valid_status(self):
        self.assertEqual(
            self.run_case('{"result":{"status":1}}')["outcome"],
            "uapi_data_absent",
        )

    def test_10_invalid_json_document_cannot_report_success(self):
        self.assertEqual(self.run_case('["not a quota response"]')["outcome"],
                         "uapi_json_unrecognized")

    def test_11_missing_binary_classification(self):
        runner = Mock(side_effect=FileNotFoundError())
        self.assertEqual(probe.classify(probe.COMMANDS[0], runner=runner)["outcome"],
                         "program_missing")

    def test_12_timeout_classification(self):
        from subprocess import TimeoutExpired
        runner = Mock(side_effect=TimeoutExpired("uapi", 12))
        self.assertEqual(probe.classify(probe.COMMANDS[0], runner=runner)["outcome"],
                         "timeout")

    def test_13_cli_stderr_and_output_are_never_returned(self):
        result = self.run_case('{"result":{"status":0,"errors":["hidden-password"]}}')
        text = json.dumps(result)
        self.assertNotIn("hidden-password", text)
        self.assertNotIn("stderr", text)
        self.assertNotIn("stdout", text)

    def test_14_report_fails_closed_for_site_and_customer(self):
        source = (ROOT / "scripts/mojprop_cpanel_uapi_cause_readonly_c111.py").read_text()
        for key in ("capacity_confirmed", "db_restore_executed",
                    "passenger_isolation_proven", "payment_collected",
                    "production_deploy_authorized"):
            self.assertIn('"' + key + '": False', source)

    def test_15_forbid_write_or_third_party_network_invocations(self):
        source = (ROOT / "scripts/mojprop_cpanel_uapi_cause_readonly_c111.py").read_text()
        for term in ('requests.post(', 'cursor.execute(', 'objects.create(',
                     'os.system(', 'shell=True', 'shutil.copy', 'urllib.request',
                     'subprocess.Popen(', 'open("wb")', 'sendrawtransaction'):
            self.assertNotIn(term, source)

    def test_16_json_error_with_buyer_data_not_logged(self):
        error = {"result": {"status":0, "errors":["Unrecognized: buyer@example.org 1234"]}}
        result = self.run_case(json.dumps(error), code=1)
        self.assertNotIn("buyer@example.org", json.dumps(result))

    def test_17_alt_binary_candidates_are_exact_restricted_locations(self):
        self.assertEqual(dict(probe.BINARY_CANDIDATES), {
            "cpanel_standard": Path("/usr/local/cpanel/bin/uapi"),
            "usr_local_bin": Path("/usr/local/bin/uapi"),
            "usr_bin": Path("/usr/bin/uapi"),
            "bin": Path("/bin/uapi"),
        })
        self.assertFalse(any("sudo" in str(path) for _, path in probe.BINARY_CANDIDATES))

    def test_18_symlinked_alternative_is_not_executed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            origin = Path(root) / "safe-uapi"
            origin.write_text("only local test fixture")
            origin.chmod(0o700)
            target = Path(root) / "symlink-uapi"
            target.symlink_to(origin)
            self.assertEqual(probe._trusted_candidate(target), (False, False))

    def test_19_regular_nonexecutable_file_is_not_considered_an_api(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "uapi"
            target.write_text("only local test fixture")
            target.chmod(0o600)
            self.assertEqual(probe._trusted_candidate(target), (True, False))

    def test_20_outcome_has_no_host_or_payment_authorization(self):
        source = (ROOT / "scripts/mojprop_cpanel_uapi_cause_readonly_c111.py").read_text()
        self.assertIn('"selected_binary_id"', source)
        self.assertIn('"available_binary_ids"', source)
        self.assertIn('"capacity_confirmed": False', source)
        self.assertIn('"production_deploy_authorized": False', source)
        self.assertIn('"db_restore_executed": False', source)


    def test_21_quota_boolean_and_string_flag_are_not_int_evidence(self):
        self.assertEqual(probe._quota_flag_class(True), "boolean")
        self.assertEqual(probe._quota_flag_class("1"), "string_1")
        self.assertEqual(probe._quota_flag_class(0), "int_0")
        self.assertEqual(probe._quota_flag_class(1), "int_1")

    def test_22_quota_report_discloses_only_bounded_state(self):
        response = {"result": {"status": 1, "data": {
            "under_quota_overall": 1,
            "under_megabyte_limit": "1",
            "under_inode_limit": 0,
            "megabyte_limit": 123456,
            "megabytes_remain": 12345,
            "inode_limit": 50000,
            "inodes_remain": 45000,
            "customer_email": "buyer@private.example",
        }}}
        result = self.run_case(json.dumps(response))
        shape = result["quota_shape"]
        self.assertEqual(shape["flags"]["under_quota_overall"], "int_1")
        self.assertEqual(shape["flags"]["under_megabyte_limit"], "string_1")
        self.assertEqual(shape["flags"]["under_inode_limit"], "int_0")
        self.assertEqual(shape["quantities"]["megabyte_limit"], "positive")
        for value in ("123456", "12345", "50000", "45000", "buyer@private.example"):
            self.assertNotIn(value, json.dumps(result))

    def test_23_missing_quota_fields_never_look_like_under_limit(self):
        result = self.run_case('{"result":{"status":1,"data":{}}}')
        self.assertTrue(all(v == "missing" for v in result["quota_shape"]["flags"].values()))
        self.assertTrue(all(v == "missing" for v in result["quota_shape"]["quantities"].values()))

    def test_24_untrusted_values_remain_scalar_classes(self):
        result = self.run_case('{"result":{"status":1,"data":{'
                               '"under_inode_limit":{"secret":"x"},'
                               '"megabyte_limit":"NaN",'
                               '"inodes_remain":-1}}}')
        self.assertEqual(result["quota_shape"]["flags"]["under_inode_limit"], "other")
        self.assertEqual(result["quota_shape"]["quantities"]["megabyte_limit"], "invalid")
        self.assertEqual(result["quota_shape"]["quantities"]["inodes_remain"], "negative")
        self.assertNotIn('"secret"', json.dumps(result))


if __name__ == "__main__":
    unittest.main()
