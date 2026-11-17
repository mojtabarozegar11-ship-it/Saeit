"""C157 synthetic-only tests. No network, credentials, files or customer access."""
from __future__ import annotations
import json
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from scripts import mojprop_c157_cpanel_statsbar_shape_readonly as q

class StatsBarShapeTests(unittest.TestCase):
    def test_01_exact_one_known_readonly_cli(self):
        self.assertEqual(q.ARGS,(q.BIN,"--output=json","StatsBar","get_stats",
                                  "display=diskusage|mysqldiskusage|fileusage"))
    def test_02_normal_flat_stats_list_counts_no_values(self):
        data={"result":{"status":1,"data":[
          {"id":"diskusage","name":"diskusage","count":"5200","max":"20000","units":"MB"},
          {"id":"mysqldiskusage","count":"private", "units":"MB"}]}}
        x=q.shape(data)
        self.assertEqual(x["status"],"ok")
        self.assertEqual(x["data_shape"],"list")
        self.assertEqual(x["row_count"],2)
        self.assertEqual(x["known_id_matches"]["diskusage"],1)
        self.assertEqual(x["known_name_matches"]["diskusage"],1)
        self.assertEqual(x["unit_declared_rows"],2)
        self.assertFalse(x["actual_account_quota_proven"])
        self.assertNotIn("5200",str(x))
        self.assertNotIn("private",str(x))
    def test_03_unknown_ids_never_exposed(self):
        x=q.shape({"result":{"status":1,"data":[
            {"id":"secretcustomer@example.com","units":"MB","password":"neverlog"}]}})
        self.assertEqual(x["unknown_id_rows"],1)
        self.assertEqual(x["field_presence"]["units"],1)
        self.assertNotIn("secretcustomer",str(x))
        self.assertNotIn("neverlog",str(x))
    def test_04_nested_data_list_supported(self):
        x=q.shape({"result":{"status":True,"data":{"data":[
          {"id":"diskusage","_count":"2","_max":"4"}]}}})
        self.assertEqual(x["data_nested_shape"],"list")
        self.assertEqual(x["row_count"],1)
        self.assertEqual(x["field_presence"]["_count"],1)
    def test_05_named_mapping_supported_without_echoing_keys(self):
        x=q.shape({"result":{"status":1,"data":{
          "diskusage":{"count":"99"},"mysqldiskusage":{"count":"5"},
          "secret": {"password":"not-exported"}}}})
        self.assertEqual(x["row_count"],2)
        self.assertNotIn("not-exported",str(x))
    def test_06_invalid_status_is_failure_not_stats(self):
        x=q.shape({"result":{"status":0,"data":[{"id":"diskusage"}]}})
        self.assertEqual(x["status"],"status_failure")
        self.assertEqual(x["row_count"],0)
    def test_07_invalid_envelope_fails_closed(self):
        for value in (None,[],{"data":[]},{"result":None},
                      {"result":{"status":1,"data":"not-structured"}}):
            x=q.shape(value)
            self.assertFalse(x["actual_account_quota_proven"])
    def test_08_bounded_rows_fail_closed(self):
        x=q.shape({"result":{"status":1,"data":[{}]*(q.MAX_ITEMS+1)}})
        self.assertEqual(x["data_shape"],"oversized")
        self.assertFalse(x["rows_bounded"])
    def test_09_known_fields_whitelist_only(self):
        x=q.shape({"result":{"status":1,"data":[
            {"id":"fileusage","api_key":"notlogged","units":"files"}]}})
        self.assertEqual(set(x["field_presence"]),set(q.FIELD_TYPES))
        self.assertNotIn("notlogged",str(x))
        self.assertEqual(x["known_id_matches"]["fileusage"],1)
    def test_10_missing_binary_blocks_provider_call(self):
        with patch.object(q,"trusted_binary",return_value=False),\
             patch.object(q.pwd,"getpwuid",return_value=SimpleNamespace(pw_name=q.OWNER)),\
             patch.object(q.subprocess,"run") as run:
            x=q.report()
        run.assert_not_called()
        self.assertEqual(x["cli"],"unsafe_binary")
        self.assertFalse(x["production_deploy_authorized"])
    def test_11_owner_mismatch_blocks_provider_call(self):
        with patch.object(q.pwd,"getpwuid",return_value=SimpleNamespace(pw_name="intruder")),\
             patch.object(q.subprocess,"run") as run:
            x=q.report()
        run.assert_not_called()
        self.assertFalse(x["owner_identity_verified"])
    def test_12_provider_output_is_structurally_sanitized(self):
        payload={"result":{"status":1,"data":[
            {"id":"diskusage","name":"diskusage","count":5200,"max":20000,
             "units":"MB","password":"SHOULDNEVERAPPEAR"}]}}
        with patch.object(q.pwd,"getpwuid",return_value=SimpleNamespace(pw_name=q.OWNER)),\
             patch.object(q,"trusted_binary",return_value=True),\
             patch.object(q.subprocess,"run",return_value=SimpleNamespace(
                 returncode=0,stdout=json.dumps(payload).encode(),stderr=b"private")):
            x=q.report()
        self.assertEqual(x["cli"],"ok")
        self.assertEqual(x["payload_shape"]["known_id_matches"]["diskusage"],1)
        self.assertNotIn("SHOULDNEVERAPPEAR",json.dumps(x))
        self.assertNotIn("5200",json.dumps(x))
        self.assertFalse(x["offhost_backup_verified"])
    def test_13_sanitized_no_backup_or_release_from_any_response(self):
        x=q.shape({"result":{"status":1,"data":[
            {"id":"diskusage","count":"0","max":"100","units":"MB"}]}})
        self.assertFalse(x["actual_account_quota_proven"])
    def test_14_reject_external_binary_symlink(self):
        with patch.object(q.os,"lstat",return_value=SimpleNamespace(
             st_mode=stat.S_IFLNK|0o777,st_uid=0)),\
             patch.object(q.os.path,"realpath",return_value="/tmp/evil"):
            self.assertFalse(q.trusted_binary())
    def test_15_trusted_root_owned_symlink_with_secure_target(self):
        with patch.object(q.os,"lstat",return_value=SimpleNamespace(
             st_mode=stat.S_IFLNK|0o777,st_uid=0)),\
             patch.object(q.os.path,"realpath",return_value="/usr/local/cpanel/bin/uapi.bin"),\
             patch.object(q.os,"stat",return_value=SimpleNamespace(
             st_mode=stat.S_IFREG|0o755,st_uid=0)),\
             patch.object(q.os,"access",return_value=True):
            self.assertTrue(q.trusted_binary())
if __name__=="__main__":
    unittest.main()
