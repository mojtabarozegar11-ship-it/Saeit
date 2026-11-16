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
        self.assertNotIn("megabytes_remain", str(r))

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

if __name__ == "__main__":
    unittest.main()
