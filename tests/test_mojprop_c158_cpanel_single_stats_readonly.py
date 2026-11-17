"""C158 no-network verified parser of cPanel inline-unit quota strings."""
from __future__ import annotations
import json
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from scripts import mojprop_c158_cpanel_single_stats_readonly as q

def payload(used="24.91 GB",limit="20 GB"):
    return {"result":{"status":1,"data":[
        {"id":"diskusage","count":used,"max":limit},
        {"id":"mysqldiskusage","count":"610.2 MB","max":"unlimited"}]}}

class C158AccountQuotaTests(unittest.TestCase):
    def test_01_sample_human_readable_GB_is_numeric(self):
        x=q.stats(payload())
        self.assertTrue(x["api_success"])
        self.assertTrue(x["valid_list"])
        self.assertEqual(x["diskusage"]["limit_kind"],"explicit_finite")
        self.assertGreater(x["diskusage"]["quota_percent_approx"],100)
        self.assertGreater(x["diskusage"]["usage_mb_approx"],24000)
        self.assertIsNone(x["mysqldiskusage"]["limit_mb_approx"])
        self.assertFalse(x["quota_verified_for_backup_writes"])

    def test_02_cpanel_count_with_no_units_is_not_automatically_MB(self):
        x=q.item_stats({"id":"diskusage","count":"24913.85","max":"20480"},
                       "diskusage")
        self.assertIsNone(x["usage_mb_approx"])
        self.assertIsNone(x["quota_percent_approx"])

    def test_03_cpanel_separate_units_safely_convert(self):
        x=q.item_stats({"id":"diskusage","count":"24913.85","max":"20480",
                        "units":"MB"},"diskusage")
        self.assertGreater(x["quota_percent_approx"],121)
        self.assertLess(x["quota_percent_approx"],122)

    def test_04_cpanel_display_unlimited_not_restore_authority(self):
        x=q.stats(payload(limit="unlimited"))["diskusage"]
        self.assertEqual(x["limit_kind"],
            "provider_unlimited_display_not_account_contract")
        self.assertIsNone(x["quota_percent_approx"])

    def test_05_reject_bad_strings_and_nonfinite(self):
        for v in ("NaN","Inf","1,000 MB","-1 GB","1e4 MB","auto","1 GB;rm",
                  "1 TB\npassword"," 12 GB",{},[],True):
            self.assertIsNone(q.parsed_bytes(v))

    def test_06_reject_wrong_units_or_missing(self):
        for unit in (None,"Gigabytes","MB/GB","unlimited"):
            self.assertIsNone(q.parsed_bytes("100",unit))

    def test_07_real_numeric_megabytes_are_decimal_marked_approx(self):
        b=q.parsed_bytes("1 GB")
        self.assertEqual(b,1073741824)
        self.assertEqual(q.parsed_bytes("1 MB"),1048576)

    def test_08_multiple_diskusage_rows_refused(self):
        raw=payload()
        raw["result"]["data"].append(raw["result"]["data"][0])
        x=q.stats(raw)
        self.assertTrue(x["api_success"])
        self.assertFalse(x["diskusage"]["present"])

    def test_09_status_errors_are_not_usage_proof(self):
        for x in ({"result":{"status":0,"data":[]}},
                  {"result":{}},{"result":{"status":1,"data":"garbled"}},None):
            out=q.stats(x)
            self.assertFalse(out["quota_verified_for_backup_writes"])

    def test_10_privacy_no_untrusted_fields_in_report(self):
        p=payload()
        p["result"]["data"][0]["customer"]="hidden@example.com"
        p["result"]["secret"]="DO_NOT_LOG"
        out=q.stats(p)
        self.assertNotIn("hidden@",json.dumps(out))
        self.assertNotIn("DO_NOT_LOG",json.dumps(out))

    def test_11_exactly_one_Cpanel_owner_readonly_statsbar_command(self):
        self.assertEqual(q.ARGS,(q.BIN,"--output=json","StatsBar",
                                 "get_stats","display=diskusage|mysqldiskusage"))

    def test_12_untrusted_binary_never_executes(self):
        with patch.object(q.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name=q.OWNER)), \
             patch.object(q,"trusted_binary",return_value=False), \
             patch.object(q.subprocess,"run") as runner:
            res=q.report()
        runner.assert_not_called()
        self.assertEqual(res["api_diagnostic"],"binary_untrusted")
        self.assertFalse(res["production_deployment_authorized"])

    def test_13_wrong_owner_never_executes(self):
        with patch.object(q.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name="other")), \
             patch.object(q.subprocess,"run") as runner:
            res=q.report()
        runner.assert_not_called()
        self.assertFalse(res["owner_identity_verified"])

    def test_14_successful_provider_response_sanitized(self):
        z=json.dumps(payload()).encode()
        with patch.object(q.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name=q.OWNER)), \
             patch.object(q,"trusted_binary",return_value=True), \
             patch.object(q.subprocess,"run",return_value=SimpleNamespace(
                         returncode=0,stdout=z,stderr=b"secret")) as m:
            r=q.report()
        self.assertEqual(r["api_diagnostic"],"ok")
        self.assertGreater(r["usage"]["diskusage"]["quota_percent_approx"],100)
        self.assertFalse(r["account_quota_confirmed_current"])
        self.assertFalse(r["offhost_independent_app_db_media_restore_verified"])
        self.assertFalse(m.call_args.kwargs.get("shell",False))
        self.assertEqual(m.call_args.kwargs["timeout"],14)

    def test_15_owner_root_symlink_inside_cpanel_allowed(self):
        with patch.object(q.os,"lstat",return_value=SimpleNamespace(
             st_mode=stat.S_IFLNK|0o777,st_uid=0)), \
             patch.object(q.os.path,"realpath",return_value="/usr/local/cpanel/bin/uapi.bin"), \
             patch.object(q.os,"stat",return_value=SimpleNamespace(
             st_mode=stat.S_IFREG|0o755,st_uid=0)), \
             patch.object(q.os,"access",return_value=True):
            self.assertTrue(q.trusted_binary())

    def test_16_symlink_outside_cpanel_refused(self):
        with patch.object(q.os,"lstat",return_value=SimpleNamespace(
             st_mode=stat.S_IFLNK|0o777,st_uid=0)), \
             patch.object(q.os.path,"realpath",return_value="/tmp/uapi"):
            self.assertFalse(q.trusted_binary())
if __name__=="__main__":
    unittest.main()
