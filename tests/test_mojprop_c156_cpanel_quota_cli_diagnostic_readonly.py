"""C156 adversarial owner-only, no-content API status and quota tests."""
import json
import os
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import mojprop_c156_cpanel_quota_cli_diagnostic_readonly as q


def good_cpapi2():
    return {"cpanelresult":{"module":"StatsBar","func":"stat",
            "event":{"result":1},"data":[
                {"id":"diskusage","count":"25000","max":"20000","units":"MB"},
                {"id":"mysqldiskusage","count":"455","max":"unlimited","units":"MB"},
            ]}}


class ActualCpanelQuotaFallbackTests(unittest.TestCase):
    def test_01_readonly_exact_statsbar_commands(self):
        self.assertEqual(set(q.CALLS),{"uapi_statsbar","cpapi2_statsbar"})
        self.assertEqual(q.CALLS["uapi_statsbar"],
            [q.UAPI,"--output=json","--user=zomorod2","StatsBar","get_stats",
             "display=diskusage|mysqldiskusage"])
        self.assertEqual(q.CALLS["cpapi2_statsbar"][2],"--user=zomorod2")
        self.assertNotIn("setquota",str(q.CALLS).lower())
        self.assertEqual(len(q.CALLS["cpapi2_statsbar"]),12)

    def test_02_current_uapi_readonly_valid_percent(self):
        result=q._parse_response({"result":{"status":1,"data":[
            {"id":"diskusage","count":80,"max":100,"units":"MB"}]}},
            "uapi_statsbar")
        self.assertEqual(result[0],"success_numeric_quota")
        self.assertEqual(result[1]["diskusage"]["percent_used"],80)

    def test_03_legacy_cpapi2_realistic_125_percent_over_quota(self):
        verdict,rows=q._parse_response(good_cpapi2(),"cpapi2_statsbar")
        self.assertEqual(verdict,"success_numeric_quota")
        self.assertEqual(rows["diskusage"]["percent_used"],125)
        self.assertEqual(rows["diskusage"]["unit"],"MB")
        self.assertEqual(rows["mysqldiskusage"]["used"],455)
        self.assertIsNone(rows["mysqldiskusage"]["limit"])

    def test_04_api_error_is_not_assumed_unsupported(self):
        for kind,invalid in (
            ("uapi_statsbar",{"result":{"status":0,"data":[]}}),
            ("cpapi2_statsbar",{"cpanelresult":{"module":"StatsBar","func":"stat",
                                               "event":{"result":0},"data":[]}})):
            self.assertEqual(q._parse_response(invalid,kind)[0],"api_status_failed")

    def test_05_different_provider_envelope_rejected(self):
        for variant in q.CALLS:
            self.assertEqual(q._parse_response({"secret":"not-an-envelope"},variant)[0],
                             "schema_unrecognized")

    def test_06_wrong_module_or_func_prohibited(self):
        for field,value in (("module","Email"),("func","set_quota")):
            msg=good_cpapi2()
            msg["cpanelresult"][field]=value
            self.assertEqual(q._parse_response(msg,"cpapi2_statsbar")[0],
                             "schema_unrecognized")

    def test_07_duplicate_diskusage_is_not_decisive(self):
        m=good_cpapi2()
        m["cpanelresult"]["data"].append(
            {"id":"diskusage","count":1,"max":100,"units":"MB"})
        verdict,d=q._parse_response(m,"cpapi2_statsbar")
        self.assertEqual(verdict,"success_no_matching_quota")
        self.assertFalse(d["diskusage"]["found"])

    def test_08_no_units_cannot_set_quota(self):
        x=q._safe_stat({"id":"diskusage","count":100,"max":200},"diskusage")
        self.assertFalse(x["found"])

    def test_09_negative_nan_inf_and_boolean_values_denied(self):
        for value in (True,-1,float("nan"),float("inf"),"Infinity","NaN",
                      "1,000","-100"):
            self.assertIsNone(q._numeric(value))

    def test_10_unlimited_max_stays_unknown(self):
        row=q._safe_stat({"id":"diskusage","count":"25000",
                          "max":"unlimited","units":"MB"},"diskusage")
        self.assertTrue(row["found"])
        self.assertIsNone(row["percent_used"])
        self.assertIsNone(row["limit"])

    def test_11_source_secrets_not_projected_from_api2_response(self):
        msg=good_cpapi2()
        msg["cpanelresult"]["password"]="supersecret"
        msg["cpanelresult"]["data"][0]["file"]="/home/private"
        output=str(q._parse_response(msg,"cpapi2_statsbar"))
        self.assertNotIn("supersecret",output)
        self.assertNotIn("/home/private",output)

    def test_12_missing_binary_does_not_execute_anything(self):
        with patch.object(q.os,"lstat",side_effect=FileNotFoundError), \
             patch.object(q.subprocess,"run") as run:
            data=q._one("cpapi2_statsbar")
        run.assert_not_called()
        self.assertEqual(data["diagnostic"],"binary_missing")

    def test_13_non_executable_binary_disallowed(self):
        with patch.object(q.os,"lstat",return_value=SimpleNamespace(
                          st_mode=stat.S_IFREG | 0o600)), \
             patch.object(q.os,"access",return_value=False), \
             patch.object(q.subprocess,"run") as run:
            data=q._one("cpapi2_statsbar")
        run.assert_not_called()
        self.assertEqual(data["diagnostic"],"binary_not_regular_or_executable")

    def test_14_nonzero_exit_classified_without_stderr_leak(self):
        msg=b"password=very-secret-host-error"
        with patch.object(q.os,"lstat",return_value=SimpleNamespace(
                          st_mode=stat.S_IFREG | 0o755)), \
             patch.object(q.os,"access",return_value=True), \
             patch.object(q.subprocess,"run",
                          return_value=SimpleNamespace(returncode=7,
                          stdout=b"",stderr=msg)) as run:
            result=q._one("cpapi2_statsbar")
        self.assertEqual(result["diagnostic"],"process_failed")
        self.assertNotIn("very-secret",str(result))
        self.assertEqual(run.call_args.args[0],q.CALLS["cpapi2_statsbar"])
        self.assertFalse(run.call_args.kwargs.get("shell",False))

    def test_15_provider_sanitized_happy_path(self):
        payload=json.dumps(good_cpapi2()).encode()
        with patch.object(q.os,"lstat",return_value=SimpleNamespace(
                          st_mode=stat.S_IFREG | 0o755)), \
             patch.object(q.os,"access",return_value=True), \
             patch.object(q.subprocess,"run",
                          return_value=SimpleNamespace(returncode=0,
                            stdout=payload,stderr=b"")):
            out=q._one("cpapi2_statsbar")
        self.assertEqual(out["diagnostic"],"success_numeric_quota")
        self.assertEqual(out["account_disk"]["percent_used"],125.0)
        self.assertEqual(out["mysql_disk"]["used"],455.0)

    def test_16_root_owned_cpanel_symlink_target_can_be_checked_readonly(self):
        api=b'{"result":{"status":1,"data":[{"id":"diskusage","count":"125","max":"100","units":"MB"}]}}'
        with patch.object(q.os,"lstat",return_value=SimpleNamespace(
                          st_mode=stat.S_IFLNK | 0o777,st_uid=0)), \
             patch.object(q.os.path,"realpath",
                          return_value="/usr/local/cpanel/3rdparty/bin/uapi"), \
             patch.object(q.os,"stat",return_value=SimpleNamespace(
                          st_mode=stat.S_IFREG | 0o755,st_uid=0)), \
             patch.object(q.os,"access",return_value=True), \
             patch.object(q.subprocess,"run",
                          return_value=SimpleNamespace(returncode=0,
                                stdout=api,stderr=b"")) as runner:
            result=q._one("uapi_statsbar")
        self.assertEqual(result["diagnostic"],"success_numeric_quota")
        self.assertEqual(result["account_disk"]["percent_used"],125.0)
        self.assertEqual(runner.call_args.args[0],q.CALLS["uapi_statsbar"])

    def test_17_symlink_outside_root_trusted_prefix_denied(self):
        with patch.object(q.os,"lstat",return_value=SimpleNamespace(
                          st_mode=stat.S_IFLNK | 0o777,st_uid=0)), \
             patch.object(q.os.path,"realpath",return_value="/tmp/evil"), \
             patch.object(q.subprocess,"run") as runner:
            result=q._one("uapi_statsbar")
        runner.assert_not_called()
        self.assertEqual(result["diagnostic"],"binary_not_regular_or_executable")

    def test_18_symlink_to_group_writable_cpanel_executable_denied(self):
        with patch.object(q.os,"lstat",return_value=SimpleNamespace(
                          st_mode=stat.S_IFLNK | 0o777,st_uid=0)), \
             patch.object(q.os.path,"realpath",
                          return_value="/usr/local/cpanel/3rdparty/bin/uapi"), \
             patch.object(q.os,"stat",return_value=SimpleNamespace(
                          st_mode=stat.S_IFREG | 0o775,st_uid=0)), \
             patch.object(q.subprocess,"run") as runner:
            result=q._one("uapi_statsbar")
        runner.assert_not_called()
        self.assertEqual(result["diagnostic"],"binary_not_regular_or_executable")

    def test_19_c120_previously_proven_owner_uapi_exact_path(self):
        self.assertEqual(q.UAPI,"/usr/bin/uapi")
        self.assertEqual(q.CALLS["uapi_statsbar"][2],"--user=zomorod2")
        self.assertEqual(q.CALLS["uapi_statsbar"][-1],
                         "display=diskusage|mysqldiskusage")

    def test_20_owner_uapi_fallback_without_user_only_after_nonzero(self):
        good=b'{"result":{"status":1,"data":[{"id":"diskusage","count":125,"max":100,"units":"MB"}]}}'
        results=[SimpleNamespace(returncode=1,stdout=b"",stderr=b"safe-test"),
                 SimpleNamespace(returncode=0,stdout=good,stderr=b"")]
        with patch.object(q.os,"lstat",return_value=SimpleNamespace(
                          st_mode=stat.S_IFREG | 0o755,st_uid=0)), \
             patch.object(q.os,"access",return_value=True), \
             patch.object(q.subprocess,"run",side_effect=results) as runner:
            r=q._one("uapi_statsbar")
        self.assertEqual(r["diagnostic"],"success_numeric_quota")
        self.assertEqual(r["account_disk"]["percent_used"],125.0)
        self.assertEqual(runner.call_count,2)
        self.assertEqual(runner.call_args_list[0].args[0],q.CALLS["uapi_statsbar"])
        self.assertEqual(runner.call_args_list[1].args[0],
                         [q.UAPI,"--output=json","StatsBar","get_stats",
                          "display="+q.DISPLAY])
        self.assertEqual(runner.call_args_list[1].kwargs["env"]["LC_ALL"],"C")
        self.assertEqual(runner.call_args_list[1].kwargs["env"]["LOGNAME"],q.OWNER)

    def test_21_unrelated_legacy_api2_failure_has_no_additional_retry(self):
        with patch.object(q.os,"lstat",return_value=SimpleNamespace(
                          st_mode=stat.S_IFREG | 0o755,st_uid=0)), \
             patch.object(q.os,"access",return_value=True), \
             patch.object(q.subprocess,"run",return_value=SimpleNamespace(
                           returncode=2,stdout=b"",stderr=b"unknown")) as runner:
            r=q._one("cpapi2_statsbar")
        self.assertEqual(r["diagnostic"],"process_failed")
        self.assertEqual(runner.call_count,1)

    def test_22_empty_uapi_stats_with_user_retry_no_user_matches_real_quota(self):
        first=b'{"result":{"status":1,"data":[]}}'
        second=b'{"result":{"status":1,"data":[{"id":"diskusage","count":"25000","max":"20000","units":"MB"}]}}'
        with patch.object(q.os,"lstat",return_value=SimpleNamespace(
                          st_mode=stat.S_IFREG | 0o755,st_uid=0)), \
             patch.object(q.os,"access",return_value=True), \
             patch.object(q.subprocess,"run",side_effect=[
                 SimpleNamespace(returncode=0,stdout=first,stderr=b""),
                 SimpleNamespace(returncode=0,stdout=second,stderr=b"")
             ]) as runner:
            out=q._one("uapi_statsbar")
        self.assertEqual(out["diagnostic"],"success_numeric_quota")
        self.assertEqual(out["account_disk"]["percent_used"],125.0)
        self.assertEqual(runner.call_count,2)
        self.assertEqual(runner.call_args_list[1].args[0],
                         [q.UAPI,"--output=json","StatsBar","get_stats",
                          "display="+q.DISPLAY])

    def test_23_empty_uapi_both_modes_must_stay_unknown(self):
        empty=b'{"result":{"status":1,"data":[]}}'
        with patch.object(q.os,"lstat",return_value=SimpleNamespace(
                          st_mode=stat.S_IFREG | 0o755,st_uid=0)), \
             patch.object(q.os,"access",return_value=True), \
             patch.object(q.subprocess,"run",return_value=SimpleNamespace(
                           returncode=0,stdout=empty,stderr=b"")) as runner:
            out=q._one("uapi_statsbar")
        self.assertEqual(runner.call_count,2)
        self.assertEqual(out["diagnostic"],"success_no_matching_quota")
        self.assertFalse(out["account_disk"]["found"])

    def test_16_no_valid_quota_does_not_authorize_backups(self):
        with patch.object(q.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name="foreign")), \
             patch.object(q.subprocess,"run") as run:
            out=q.report()
        run.assert_not_called()
        self.assertFalse(out["owner_identity_verified"])
        for k in ("account_backup_write_authorized",
                  "offhost_independent_restore_verified",
                  "full_app_db_media_restore_proven",
                  "database_content_read",
                  "backup_content_read",
                  "customer_data_accessed",
                  "external_network_called",
                  "production_deployment_authorized",
                  "payment_created","cost_incurred"):
            self.assertFalse(out[k])

if __name__=="__main__":
    unittest.main()
