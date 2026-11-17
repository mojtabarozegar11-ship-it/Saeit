"""C160 independent synthetic source-parity tests; no live cPanel contact."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import mojprop_c160_owner_plan1_source_parity_readonly as probe


def fixture(root):
    source = {
        "config/urls.py":b"urlpatterns = []\n",
        "config/settings.py":b"SECRET_KEY='NEVER_READ_REAL_SECRETS'\n",
        "core/moj_prop_views.py":b"def moj_prop_interest_form(request): pass\n",
        "core/templates/mojplaywin/moj_prop_interest_form_d.html":
            b"<form></form>",
        "prop_firm/migrations/0008_prospect_contact_intake.py":
            b"dependencies = []\n",
    }
    mapping={}
    os.chmod(root,0o700)
    for name, data in source.items():
        file=root/name
        file.parent.mkdir(parents=True,exist_ok=True)
        os.chmod(file.parent,0o700)
        file.write_bytes(data)
        os.chmod(file,0o600)
        mapping[name]=hashlib.sha256(data).hexdigest()
    return mapping


class C160ParityTests(unittest.TestCase):
    def test_01_real_5_file_synthetic_source_validity(self):
        with tempfile.TemporaryDirectory() as td:
            mapping=fixture(Path(td))
        self.assertEqual(probe.validate_expected(mapping),mapping)
        self.assertEqual(probe._group("prop_firm/migrations/0008_prospect_contact_intake.py"),
                         "prop_migrations")

    def test_02_exact_sha_match_and_secret_exclusion(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            mapping=fixture(root)
            self.assertEqual(probe.file_parity(root,"core/moj_prop_views.py",
                            mapping["core/moj_prop_views.py"],os.geteuid()),
                            "matches")
            self.assertEqual(probe.file_parity(root,"config/settings.py",
                            mapping["config/settings.py"],os.geteuid()),"withheld")

    def test_03_tamper_detected_by_real_sha256(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);mapping=fixture(root)
            (root/"core/moj_prop_views.py").write_text("changed locally")
            self.assertEqual(probe.file_parity(root,"core/moj_prop_views.py",
                         mapping["core/moj_prop_views.py"],os.geteuid()),"drifted")

    def test_04_missing_dir_and_file_separately_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);mapping=fixture(root)
            (root/"core/moj_prop_views.py").unlink()
            self.assertEqual(probe.file_parity(root,"core/moj_prop_views.py",
                         mapping["core/moj_prop_views.py"],os.geteuid()),"missing")
            (root/"prop_firm/migrations/0008_prospect_contact_intake.py").unlink()
            (root/"prop_firm/migrations").rmdir()
            self.assertEqual(probe.file_parity(root,
                         "prop_firm/migrations/0008_prospect_contact_intake.py",
                         mapping["prop_firm/migrations/0008_prospect_contact_intake.py"],
                         os.geteuid()),"missing")

    def test_05_symlink_source_file_denied(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);mapping=fixture(root)
            file=root/"core/moj_prop_views.py"
            file.unlink();file.symlink_to("/etc/passwd")
            self.assertEqual(probe.file_parity(root,"core/moj_prop_views.py",
                         mapping["core/moj_prop_views.py"],os.geteuid()),"unsafe")

    def test_06_symlink_parent_denied_without_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);mapping=fixture(root)
            file=root/"core/moj_prop_views.py"
            file.unlink()
            (root/"core/templates/mojplaywin/moj_prop_interest_form_d.html").unlink()
            (root/"core/templates/mojplaywin").rmdir()
            (root/"core/templates").rmdir()
            (root/"core").rmdir()
            (root/"core").symlink_to("/tmp")
            self.assertEqual(probe.file_parity(root,"core/moj_prop_views.py",
                         mapping["core/moj_prop_views.py"],os.geteuid()),"unsafe")

    def test_07_group_writable_parent_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);mapping=fixture(root)
            os.chmod(root/"prop_firm",0o770)
            self.assertEqual(probe.file_parity(root,
                         "prop_firm/migrations/0008_prospect_contact_intake.py",
                         mapping["prop_firm/migrations/0008_prospect_contact_intake.py"],
                         os.geteuid()),"unsafe")

    def test_08_wrong_owner_or_invalid_relative_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);mapping=fixture(root)
            self.assertEqual(probe.file_parity(root,"core/moj_prop_views.py",
                         mapping["core/moj_prop_views.py"],os.geteuid()+1123),"unsafe")
            for invalid in ("/etc/passwd","config/../.env","../../secrets.py",
                            "media/uploads/file.py","core//.env","prop_firm/x.sql"):
                self.assertFalse(probe._safe_name(invalid))
                self.assertEqual(probe.file_parity(root,invalid,
                         "f"*64,os.geteuid()),"unsafe")

    def test_09_source_inventory_counts_never_claim_whole_restore(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);mapping=fixture(root)
            report=probe.compare(root,mapping,os.geteuid())
        self.assertEqual(report["file_count"],5)
        self.assertEqual(report["total_counts"]["matches"],4)
        self.assertEqual(report["total_counts"]["withheld"],1)
        self.assertFalse(report["backup_or_restore_proven"])
        self.assertFalse(report["production_deploy_authorized"])
        self.assertFalse(report["read_customer_or_database"])

    def test_10_duplicate_or_invalid_sha_manifest_denied(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);mapping=fixture(root)
        for evil in ("nothex","A"*64,"e"*63,"e"*65,42):
            m=dict(mapping);m["core/moj_prop_views.py"]=evil
            with self.assertRaises(ValueError):
                probe.validate_expected(m)

    def test_11_undefined_manifest_and_wrong_user_fail_closed(self):
        with patch.object(probe.pwd,"getpwuid",
              return_value=SimpleNamespace(pw_name="somebody-else")):
            doc=probe.report({"core/moj_prop_views.py":"f"*64})
        self.assertFalse(doc["owner_identity_verified"])
        self.assertFalse(doc["comparison_completed"])
        self.assertFalse(doc["production_deployment_authorized"])

    def test_12_no_local_io_or_customer_privacy_claim_without_manifest(self):
        with patch.object(probe.pwd,"getpwuid",
              return_value=SimpleNamespace(pw_name=probe.OWNER)), \
             patch.object(probe,"safe_owner_dir",return_value=True):
            doc=probe.report(None)
        self.assertTrue(doc["owner_identity_verified"])
        self.assertFalse(doc["comparison_completed"])
        for field in ("account_quota_proven","independent_full_app_db_media_restore_proven",
                      "public_form_get_verified","customer_data_accessed",
                      "backup_contents_read","database_accessed",
                      "external_network_called","production_deployment_authorized",
                      "payment_created","cost_incurred"):
            self.assertIs(doc[field],False)
        self.assertEqual(probe.MAX_FILES,128)

if __name__=="__main__":
    unittest.main()
