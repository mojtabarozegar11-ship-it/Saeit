"""C154 zero-network/offline adversarial cPanel quota parsing tests."""
import json
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from scripts import mojprop_c154_cpanel_quota_uapi_readonly as q


class QuotaTruthTests(unittest.TestCase):
    def test_01_documented_api_functions_only(self):
        self.assertEqual(q.FUNCTIONS,("get_quota_info","get_local_quota_info"))
        with self.assertRaises(ValueError):
            q.read_quota("set_quota")

    def test_02_whole_account_used_limit_ratio(self):
        x=q.quota_shape({"result":{"status":1,"data":{"used":"24000","limit":"20000"}}})
        self.assertTrue(x["api_ok"])
        self.assertEqual(x["same_unit_used_to_limit_ratio_percent"],120.0)
        self.assertFalse(x["account_write_headroom_proven"])

    def test_03_no_units_no_ratio_never_assume_quota_available(self):
        x=q.quota_shape({"result":{"status":1,"data":{"some_unrecognized_metric":123}}})
        self.assertTrue(x["api_ok"])
        self.assertIsNone(x["same_unit_used_to_limit_ratio_percent"])
        self.assertFalse(x["account_write_headroom_proven"])

    def test_04_uapi_error_or_malformed_is_not_safe(self):
        for v in ({"result":{"status":0,"data":{"used":2,"limit":5}}},
                  {"result":{}},{"result":{"status":1,"data":None}},[],None):
            r=q.quota_shape(v)
            self.assertFalse(r["api_ok"])
            self.assertFalse(r["account_write_headroom_proven"])

    def test_05_reject_secrets_and_arbitrary_result_fields(self):
        inp={"result":{"status":1,"data":{
            "email":"owner@example.com","api_token":"supersecret",
            "password":"private","used":"300","limit":"200"
        }}}
        out=q.quota_shape(inp)
        self.assertNotIn("supersecret",json.dumps(out))
        self.assertNotIn("owner@",json.dumps(out))
        self.assertNotIn("private",json.dumps(out))
        self.assertEqual(set(out["matched_numeric_fields"]),{"used","limit"})

    def test_06_accept_singleton_dictionary_array(self):
        r=q.quota_shape({"result":{"status":1,"data":[{"megabytes_used":"100",
                                                           "megabytes_limit":"80"}]}})
        self.assertEqual(r["same_unit_used_to_limit_ratio_percent"],125)

    def test_07_reject_list_ambiguous_multiple_quota_nodes(self):
        r=q.quota_shape({"result":{"status":1,"data":[{"used":1,"limit":100},
                                                          {"used":99,"limit":100}]}})
        self.assertFalse(r["api_ok"])
        self.assertIsNone(r["same_unit_used_to_limit_ratio_percent"])

    def test_08_reject_nan_infinity_boolean_bad_decimal(self):
        r=q.quota_shape({"result":{"status":1,"data":{"used":True,"limit":1,
                            "bytes_used":"NaN","bytes_limit":"Inf"}}})
        self.assertEqual(r["matched_numeric_fields"],{"limit":1.0})
        self.assertIsNone(r["same_unit_used_to_limit_ratio_percent"])
        self.assertFalse(r["account_write_headroom_proven"])

    def test_09_never_infer_unlimited_from_zero_limit(self):
        r=q.quota_shape({"result":{"status":1,"data":{"used":300,"limit":0}}})
        self.assertIsNone(r["same_unit_used_to_limit_ratio_percent"])
        self.assertFalse(r["account_write_headroom_proven"])

    def test_10_exact_uapi_command_no_shell_or_token(self):
        with patch.object(q.subprocess,"run",return_value=SimpleNamespace(
            returncode=0,stdout=b'{"result":{"status":1,"data":{"used":120,"limit":100}}}')) as m:
            z=q.read_quota("get_quota_info")
        self.assertEqual(z["same_unit_used_to_limit_ratio_percent"],120.0)
        args=m.call_args.args[0]
        self.assertEqual(args,[q.UAPI,"--output=json","Quota","get_quota_info"])
        self.assertFalse(m.call_args.kwargs.get("shell",False))
        self.assertEqual(m.call_args.kwargs["timeout"],12)
        self.assertNotIn("PASSWORD",m.call_args.kwargs["env"])

    def test_11_failed_or_oversized_provider_output_not_safe(self):
        with patch.object(q.subprocess,"run",return_value=SimpleNamespace(
            returncode=0,stdout=b'x'*(q.MAX_BYTES+1))):
            z=q.read_quota("get_quota_info")
        self.assertFalse(z["api_ok"])
        self.assertFalse(z["account_write_headroom_proven"])

    def test_12_wrong_user_does_not_execute_api(self):
        with patch.object(q.pwd,"getpwuid",return_value=SimpleNamespace(pw_name="wrong")), \
             patch.object(q.subprocess,"run") as m:
            r=q.report()
        m.assert_not_called()
        self.assertFalse(r["owner_identity_verified"])
        self.assertFalse(r["production_deployment_authorized"])
        self.assertFalse(r["full_app_db_media_restore_verified"])

    def test_13_no_client_release_even_with_quota_under_limit(self):
        with patch.object(q.pwd,"getpwuid",return_value=SimpleNamespace(pw_name="zomorod2")), \
             patch.object(q.subprocess,"run",return_value=SimpleNamespace(
               returncode=0,stdout=b'{"result":{"status":1,"data":{"used":1,"limit":100}}}')):
            r=q.report()
        self.assertEqual(r["whole_account"]["same_unit_used_to_limit_ratio_percent"],1.0)
        self.assertFalse(r["independent_restore_capacity_proven"])
        self.assertFalse(r["production_deployment_authorized"])

if __name__=="__main__":
    unittest.main()
