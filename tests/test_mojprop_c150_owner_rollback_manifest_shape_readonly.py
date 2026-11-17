"""C150 contract and safety tests; never reads real customer backups."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import mojprop_c150_owner_rollback_manifest_shape_readonly as mod


def sample(run="4400000100", attempted=False):
    files=["config/urls.py","core/mojprop_views.py"]
    return {
        "run_id":run,
        "commit":"a"*40,
        "files":files,
        "schema_migration_attempted":attempted,
        "config/urls.py":{"existed":True,"sha256":"b"*64,"mode":0o644},
        "core/mojprop_views.py":{"existed":False},
    }


def case(root: Path,name="4400000100",doc=None):
    path=root/name
    path.mkdir(mode=0o700)
    target=path/"manifest.json"
    target.write_text(json.dumps(sample(name) if doc is None else doc), encoding="utf-8")
    os.chmod(target,0o600)
    return path


class LocalRollbackMetadataTests(unittest.TestCase):
    def test_01_valid_source_only_manifest_does_not_prove_database_restore(self):
        result=mod.classify_manifest(sample(),"4400000100")
        self.assertEqual(result["type"],"source-only-rollback")
        self.assertEqual(result["declared_source_files"],2)
        self.assertEqual(result["declared_existing_files"],1)
        self.assertFalse(result["schema_migration_attempted"])

    def test_02_migration_attempted_is_historical_flag_not_restore_proof(self):
        result=mod.classify_manifest(sample(attempted=True),"4400000100")
        self.assertTrue(result["schema_migration_attempted"])
        self.assertNotIn("independent_restore_verified",result)

    def test_03_wrong_case_id_or_nonhex_commit_is_invalid(self):
        self.assertEqual(mod.classify_manifest(sample(),"other")["type"],"unknown")
        bad=sample()
        bad["commit"]="not-sha"
        self.assertEqual(mod.classify_manifest(bad,bad["run_id"])["type"],"unknown")

    def test_04_reject_unsafe_relative_paths_and_duplicates(self):
        for bad in ("../../private.py","/etc/passwd","core/.env",
                    "config/../users.py","other/file.py"):
            self.assertFalse(mod.safe_source_path(bad))
        x=sample()
        x["files"]=["config/urls.py","config/urls.py"]
        self.assertEqual(mod.classify_manifest(x,x["run_id"])["type"],"unknown")

    def test_05_reject_undocumented_or_malformed_source_entry(self):
        x=sample()
        x["config/urls.py"]["sha256"]="invalid"
        self.assertEqual(mod.classify_manifest(x,x["run_id"])["type"],"unknown")
        x=sample()
        x["core/mojprop_views.py"].pop("existed")
        self.assertEqual(mod.classify_manifest(x,x["run_id"])["type"],"unknown")

    def test_06_read_only_fixed_named_manifest_in_private_owned_case(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            os.chmod(root,0o700)
            c=case(root)
            parsed=mod.read_fixed_manifest(c,os.geteuid())
        self.assertIsInstance(parsed,dict)
        self.assertEqual(parsed["run_id"],"4400000100")

    def test_07_duplicate_json_key_is_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            c=case(root)
            m=c/"manifest.json"
            m.write_text('{"run_id":"a","run_id":"b"}')
            self.assertIsNone(mod.read_fixed_manifest(c,os.geteuid()))

    def test_08_symlink_manifest_not_followed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            c=case(root)
            (c/"manifest.json").unlink()
            (c/"manifest.json").symlink_to("/etc/passwd")
            self.assertIsNone(mod.read_fixed_manifest(c,os.geteuid()))

    def test_09_group_writable_manifest_not_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            c=case(root)
            os.chmod(c/"manifest.json",0o660)
            self.assertIsNone(mod.read_fixed_manifest(c,os.geteuid()))

    def test_10_large_manifest_not_loaded(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            c=case(root)
            (c/"manifest.json").write_bytes(b"x"*(mod.MAX_BYTES+1))
            self.assertIsNone(mod.read_fixed_manifest(c,os.geteuid()))

    def test_11_bounded_inventory_of_valid_and_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            os.chmod(root,0o700)
            case(root,"4400000100")
            case(root,"4400000101",doc={"unexpected":"secret-free-test"})
            result=mod.inventory(root,os.geteuid())
        self.assertTrue(result["completed"])
        self.assertEqual(result["case_directories_checked"],2)
        self.assertEqual(result["source_only_rollback_manifests"],1)
        self.assertEqual(result["unknown_or_invalid_manifest_shapes"],1)
        self.assertFalse(result["independent_restore_verified"])
        self.assertFalse(result["read_any_backup_saved_file"])

    def test_12_more_than_128_entries_does_not_masquerade_as_complete(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            os.chmod(root,0o700)
            for i in range(mod.MAX_ENTRIES+1):
                (root/f"unrelated{i}").mkdir()
            result=mod.inventory(root,os.geteuid())
        self.assertFalse(result["completed"])
        self.assertEqual(result["source_only_rollback_manifests"],0)

    def test_13_wrong_user_stops_before_examining_actual_private_paths(self):
        with patch.object(mod.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name="foreign")):
            report=mod.report()
        self.assertFalse(report["owner_identity_verified"])
        self.assertFalse(report["db_snapshot_read"])
        self.assertFalse(report["app_db_media_restore_proven"])
        self.assertFalse(report["production_release_authorized"])

    def test_14_run_id_regex_and_no_read_of_unknown_file(self):
        self.assertTrue(mod.CASE.fullmatch("4400000100"))
        self.assertFalse(mod.CASE.fullmatch("../backup"))
        self.assertFalse(mod.CASE.fullmatch("customer@example.com"))
        self.assertEqual(mod.MAX_BYTES,65536)
        self.assertEqual(mod.MAX_CASES,64)

    def test_15_no_file_content_scouting_or_restore_automation(self):
        code=Path(mod.__file__).read_text("utf-8")
        for prohibited in ("subprocess.", "ssh ", "urllib.", "requests.",
                           "shutil.", "tarfile.", "cursor(", "migrate(",
                           "os.remove(", "os.rename(", "open(\"/home/"):
            self.assertNotIn(prohibited,code)
        self.assertIn('path = case_dir / "manifest.json"',code)

if __name__=="__main__":
    unittest.main()
