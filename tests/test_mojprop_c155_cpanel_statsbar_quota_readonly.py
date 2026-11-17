"""C155 StatsBar read-only account quota and MySQL size parser regressions."""
from __future__ import annotations
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import mojprop_c155_cpanel_statsbar_quota_readonly as q


class C155QuotaTruth(unittest.TestCase):
    def test_01_documented_one_fixed_call(self):
        self.assertEqual(q.DISPLAY,"diskusage|fileusage|mysqldiskusage")
        self.assertEqual(q.ALLOWED_IDS,("diskusage","fileusage","mysqldiskusage"))

    def test_02_overquota_actual_same_unit_is_detectable(self):
        d=q.normalize({"result":{"status":1,"data":[
            {"id":"diskusage","count":"24913.85","max":"20480","units":"MB"},
            {"id":"mysqldiskusage","count":"500.5","max":"unlimited","units":"MB"}]}})
        self.assertTrue(d["api_ok"])
        self.assertEqual(d["diskusage"]["percent_of_limit"],121.65)
        self.assertEqual(d["diskusage"]["maximum"],20480.0)
        self.assertEqual(d["mysqldiskusage"]["usage"],500.5)
        self.assertFalse(d["account_write_headroom_proven"])

    def test_03_null_and_unlimited_max_are_unknown(self):
        for maxval in (None,"unlimited",0,"0","n/a"):
            d=q.stat_row({"id":"diskusage","count":"100","max":maxval,
                          "units":"MB"},"diskusage")
            self.assertTrue(d["available"])
            self.assertIsNone(d["percent_of_limit"])
            self.assertIsNone(d["maximum"])

    def test_04_no_units_do_not_assume_megabytes(self):
        d=q.stat_row({"id":"diskusage","count":"100","max":"200"},"diskusage")
        self.assertFalse(d["available"])

    def test_05_no_secret_or_user_fields_ever_appear(self):
        d=q.normalize({"result":{"status":1,"data":[
            {"id":"diskusage","count":100,"max":200,"units":"MB",
             "token":"DEADBEEF","email":"sensitive@private","directory":"/home/owner"},
            {"id":"emailaccounts","count":99,"max":500,"units":"files"}]}})
        payload=json.dumps(d)
        for secret in ("DEADBEEF","sensitive@private","/home/owner","emailaccounts"):
            self.assertNotIn(secret,payload)

    def test_06_duplicate_account_stat_rows_are_discarded(self):
        d=q.normalize({"result":{"status":1,"data":[
            {"id":"diskusage","count":10,"max":100,"units":"MB"},
            {"id":"diskusage","count":99,"max":100,"units":"MB"}]}})
        self.assertTrue(d["api_ok"])
        self.assertFalse(d["diskusage"]["available"])

    def test_07_status_failure_cannot_authorize_backup(self):
        for value in (None,[],{"result":{}},
                      {"result":{"status":0,"data":[]}},
                      {"result":{"status":1,"data":"invalid"}}):
            d=q.normalize(value)
            self.assertFalse(d["api_ok"])
            self.assertFalse(d["account_write_headroom_proven"])

    def test_08_statsbar_list_malformed_fails_closed(self):
        d=q.normalize({"result":{"status":1,"data":[None]*13}})
        self.assertFalse(d["api_ok"])
        self.assertEqual(d["response_type"],"unsupported")

    def test_09_nan_inf_negatives_and_bool_are_rejected(self):
        for val in (True,-1,float("nan"),float("inf"),"NaN","Infinity","1,000"):
            self.assertIsNone(q._number(val))

    def test_10_same_unit_percent_without_external_estimate(self):
        d=q.stat_row({"id":"fileusage","count":"8","max":"10",
                      "units":"files"},"fileusage")
        self.assertEqual(d["percent_of_limit"],80.0)
        self.assertFalse(d["account_write_headroom_proven"])

    def test_11_direct_uapi_argv_and_no_shell(self):
        with patch.object(q.subprocess,"run",return_value=SimpleNamespace(
            returncode=0,stdout=b'{"result":{"status":1,"data":[]}}')) as runner:
            res=q.query()
        self.assertTrue(res["api_ok"])
        args=runner.call_args.args[0]
        self.assertEqual(args,[q.UAPI,"--output=json","StatsBar","get_stats",
                               "display="+q.DISPLAY])
        self.assertFalse(runner.call_args.kwargs.get("shell",False))
        self.assertEqual(runner.call_args.kwargs["timeout"],15)
        self.assertNotIn("PASSWORD",runner.call_args.kwargs["env"])

    def test_12_failed_or_long_output_is_unavailable(self):
        with patch.object(q.subprocess,"run",return_value=SimpleNamespace(
            returncode=0,stdout=b'x'*(q.MAX_JSON+1))):
            res=q.query()
        self.assertFalse(res["api_ok"])

    def test_13_wrong_os_identity_never_calls_provider(self):
        with patch.object(q.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name="not-owner")), \
             patch.object(q.subprocess,"run") as runner:
            res=q.report()
        runner.assert_not_called()
        self.assertFalse(res["owner_identity_verified"])
        self.assertFalse(res["full_app_db_media_restore_verified"])
        self.assertFalse(res["production_release_authorized"])

    def test_14_no_backup_release_even_with_zero_disk_usage(self):
        with patch.object(q.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name=q.OWNER)), \
             patch.object(q.subprocess,"run",return_value=SimpleNamespace(
                 returncode=0,stdout=b'{"result":{"status":1,"data":'
                                     b'[{"id":"diskusage","count":"0",'
                                     b'"max":"20000","units":"MB"}]}}')):
            res=q.report()
        self.assertEqual(res["stats"]["diskusage"]["percent_of_limit"],0)
        self.assertFalse(res["production_release_authorized"])
        self.assertFalse(res["full_app_db_media_restore_verified"])
        self.assertFalse(res["stats"]["account_write_headroom_proven"])

if __name__=="__main__":
    unittest.main()
