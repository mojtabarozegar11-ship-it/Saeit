"""No production access: adversarial aggregate-only manifest fingerprint tests."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from scripts import mojprop_c151_owner_manifest_format_readonly as probe


def make_case(root, name="4400000100", data=None):
    case=root/name
    case.mkdir(mode=0o700)
    target=case/"manifest.json"
    target.write_text(json.dumps({"run_id":name, "commit":"a"*40,
                                   "files":["config/urls.py"],
                                   "schema_migration_attempted":False,
                                   "config/urls.py":{"existed":True}}
                                  if data is None else data))
    os.chmod(target,0o600)
    return case


class OldManifestFeatureTests(unittest.TestCase):
    def test_01_backend_style_detected_without_marking_restored(self):
        f=probe.fingerprint({"run_id":"12345678", "commit":"a"*40,
                             "files":["config/urls.py"],
                             "config/urls.py":{"existed":True},
                             "schema_migration_attempted":False}, "12345678")
        self.assertTrue(f["parsed_json_map"])
        self.assertTrue(f["matching_run_id"])
        self.assertTrue(f["commit_40hex"])
        self.assertTrue(f["files_list_string"])
        self.assertTrue(f["declared_first_party_source_list"])
        self.assertTrue(f["original_file_metadata_dict_present"])
        self.assertTrue(f["migration_flag_boolean"])

    def test_02_static_legacy_style_is_distinct_from_backend(self):
        f=probe.fingerprint({"schema":"mojprop.static.starter30.v3",
                             "run_id":"12345678", "commit_sha":"b"*40,
                             "rolled_back":False,"files":[{"path":"index.html"}]},
                            "12345678")
        self.assertTrue(f["schema_contains_static_marker"])
        self.assertTrue(f["commit_sha_40hex"])
        self.assertTrue(f["files_list_map"])
        self.assertFalse(f["files_list_string"])
        self.assertFalse(f["commit_40hex"])

    def test_03_mismatched_run_id_counted_not_released(self):
        f=probe.fingerprint({"run_id":"some_other_run","files":[]},
                            "4400000100")
        self.assertTrue(f["run_id_string_mismatch"])
        self.assertFalse(f["matching_run_id"])

    def test_04_unknown_shapes_do_not_invent_schema(self):
        f=probe.fingerprint({"customer_email":"never echo this"},"12345678")
        self.assertEqual(set(f),set(probe.SIG_KEYS))
        self.assertFalse(f["schema_string"])
        self.assertTrue(f["file_entries_absent_or_other"])
        self.assertNotIn("customer_email",f)
        self.assertNotIn("never echo",str(f))

    def test_05_source_paths_with_parent_escape_not_accepted(self):
        f=probe.fingerprint({"files":["core/../.env"]},"12345678")
        self.assertFalse(f["declared_first_party_source_list"])

    def test_06_json_duplicate_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            c=make_case(root)
            (c/"manifest.json").write_text('{"run_id":"foo","run_id":"bar"}')
            self.assertIsNone(probe._read_manifest(c,os.geteuid()))

    def test_07_manifest_symlink_never_follows(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            c=make_case(root)
            (c/"manifest.json").unlink()
            (c/"manifest.json").symlink_to("/etc/passwd")
            self.assertIsNone(probe._read_manifest(c,os.geteuid()))

    def test_08_oversized_manifest_refused_before_json(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            c=make_case(root)
            (c/"manifest.json").write_bytes(b"x"*(probe.MAX_BYTES+1))
            self.assertIsNone(probe._read_manifest(c,os.geteuid()))

    def test_09_real_fake_dir_aggregate_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            make_case(root)
            make_case(root,"4400000101",data={"schema":"legacy","files":[{"path":"unknown"}]})
            z=probe.inventory(root,os.geteuid())
        self.assertTrue(z["completed"])
        self.assertEqual(z["cases_checked"],2)
        self.assertEqual(z["features"]["files_list_string"],1)
        self.assertEqual(z["features"]["files_list_map"],1)
        self.assertFalse(z["independent_restore_proven"])

    def test_10_over_128_entries_report_unknown_not_zero(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);os.chmod(root,0o700)
            for i in range(probe.MAX_ENTRIES+1):
                (root/f"item{i}").mkdir()
            z=probe.inventory(root,os.geteuid())
        self.assertFalse(z["completed"])
        self.assertEqual(z["cases_checked"],0)

    def test_11_other_user_denies_even_metadata_scan(self):
        with patch.object(probe.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name="foreign")):
            result=probe.report()
        self.assertFalse(result["owner_identity_verified"])
        self.assertFalse(result["app_db_media_restore_verified"])
        self.assertFalse(result["production_release_authorized"])

    def test_12_only_fixed_manifest_bytes_ever_opened(self):
        code=Path(probe.__file__).read_text("utf-8")
        self.assertIn('path=case_dir/"manifest.json"',code)
        for forbidden in ("subprocess.", "ssh ", "os.remove(", "os.rename(",
                          "shutil.", "tarfile.", "requests.", "cursor(",
                          "sql.connect(", "restore("):
            self.assertNotIn(forbidden,code)

if __name__=="__main__":
    unittest.main()
