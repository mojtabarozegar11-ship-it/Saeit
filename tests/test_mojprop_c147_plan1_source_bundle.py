"""C147 nondeployable Plan1 source release package regression tests."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from scripts import mojprop_c147_plan1_source_bundle as bundler


class Plan1SourceOnlyClosure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = bundler.collect(bundler.ROOT)

    def _copy_to_temp(self, root: Path, overrides=None, missing=()):
        overrides = overrides or {}
        for name, data in self.files.items():
            if name in missing:
                continue
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(overrides.get(name, data))
        return root

    def test_01_reviewed_sources_include_all_eight_real_prospect_migrations(self):
        self.assertGreaterEqual(len(self.files), 40)
        for name in bundler.REQUIRED:
            with self.subTest(name=name):
                self.assertIn(name, self.files)
        self.assertIn("prop_firm/migrations/0008_prospect_contact_intake.py",
                      self.files)

    def test_02_django_real_plan1_get_and_post_routes(self):
        routes = bundler._path_view_mappings(self.files["config/urls.py"])
        self.assertIn(("moj-prop-interest/form/", "moj_prop_interest_form"), routes)
        self.assertIn(("moj-prop-interest/", "moj_prop_interest"), routes)
        self.assertTrue(bundler._installed_app(self.files["config/settings.py"]))

    def test_03_archive_bytes_deterministic_with_no_timestamps(self):
        a = bundler.tar_bytes(self.files)
        self.assertEqual(a, bundler.tar_bytes(dict(reversed(list(self.files.items())))))
        with tarfile.open(fileobj=io.BytesIO(a), mode="r:") as tar:
            names = tar.getnames()
            self.assertEqual(names, sorted(self.files))
            self.assertEqual(len(names), len(self.files))
            for entry in tar.getmembers():
                self.assertTrue(entry.isfile())
                self.assertEqual(entry.mtime, 0)
                self.assertEqual(entry.uid, 0)
                self.assertEqual(entry.gid, 0)
                self.assertEqual(entry.mode, 0o644)
                self.assertEqual(tar.extractfile(entry).read(),
                                 self.files[entry.name])

    def test_04_manifest_is_bounded_nonpayable_and_reference_configs_not_installed(self):
        doc = bundler.manifest(self.files)
        self.assertEqual(doc["schema"], "mojprop.plan1.source_closure.c147.v1")
        self.assertEqual(doc["product"], "MOJ-PROP-01")
        self.assertEqual(doc["file_count"], len(self.files))
        self.assertFalse(doc["production_deploy_authorized"])
        self.assertFalse(doc["db_app_media_restore_verified"])
        self.assertFalse(doc["merchant_authorized"])
        self.assertFalse(doc["tron_invoice_created"])
        self.assertFalse(doc["customer_consent_post_executed"])
        self.assertTrue(all(len(f["sha256"]) == 64 for f in doc["files"]))
        refs = {x["path"] for x in doc["files"]
                if x["installation_role"] == "reference-only-do-not-overwrite-live"}
        self.assertEqual(refs, {"config/settings.py", "config/urls.py"})

    def test_05_tampered_genuine_form_or_wallet_code_refused(self):
        name = "core/templates/mojplaywin/moj_prop_interest_form_d.html"
        actual = self.files[name]
        for malicious in (
            actual.replace(b"{% csrf_token %}", b""),
            actual.replace(b"MOJ-PROP-01", b"MOJPROP-STARTER30"),
            actual + b'<script>tronWeb.trx.sendTransaction()</script>',
        ):
            with self.subTest(malicious=len(malicious)):
                with tempfile.TemporaryDirectory() as td:
                    root = self._copy_to_temp(Path(td), {name: malicious})
                    with self.assertRaises(ValueError):
                        bundler.collect(root)

    def test_06_routes_wrong_or_missing_app_must_fail_closed(self):
        snippets = (
            ("config/urls.py",
             self.files["config/urls.py"].replace(
                 b'"moj-prop-interest/form/"', b'"starter-30-trx/"')),
            ("config/settings.py",
             self.files["config/settings.py"].replace(
                 b'"prop_firm.apps.MojPropConfig"', b'"untrusted.app"')),
        )
        for name, body in snippets:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
                root = self._copy_to_temp(Path(td), {name: body})
                with self.assertRaises(ValueError):
                    bundler.collect(root)

    def test_07_missing_or_broken_migration_predecessor_denied(self):
        name = "prop_firm/migrations/0008_prospect_contact_intake.py"
        with tempfile.TemporaryDirectory() as td:
            root = self._copy_to_temp(Path(td), missing=[name])
            with self.assertRaises(FileNotFoundError):
                bundler.collect(root)
        original = self.files[name]
        altered = original.replace(b"0007_equity_broker_source", b"0006_ten_plan_enrollment")
        with tempfile.TemporaryDirectory() as td:
            root = self._copy_to_temp(Path(td), {name: altered})
            with self.assertRaises(ValueError):
                bundler.collect(root)

    def test_08_no_symlink_in_any_bundle_file(self):
        name = "core/moj_prop_views.py"
        with tempfile.TemporaryDirectory() as td:
            root = self._copy_to_temp(Path(td))
            target = root / name
            target.unlink()
            target.symlink_to("/etc/passwd")
            with self.assertRaises(ValueError):
                bundler.collect(root)

    def test_09_reject_root_escape_and_arbitrary_source_names(self):
        for name in ("../.env", "/etc/passwd", "config/../.env",
                     "config//urls.py"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                bundler._file_bytes(bundler.ROOT, name)

    def test_10_package_to_runner_requires_approved_ephemeral_environment(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "mojprop-c147"
            with patch.dict(os.environ, {"GITHUB_ACTIONS": "false",
                                         "RUNNER_TEMP": td}):
                with self.assertRaises(PermissionError):
                    bundler.package_to_runner(self.files, target)
            self.assertFalse(target.exists())

    def test_11_verified_runner_package_with_exact_sha_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "mojprop-c147"
            with patch.dict(os.environ, {"GITHUB_ACTIONS": "true",
                                         "RUNNER_TEMP": td}):
                result = bundler.package_to_runner(self.files, target)
                self.assertTrue(result["ephemeral_only"])
                self.assertEqual(result["file_count"], len(self.files))
                tar = (target / bundler.BUNDLE_NAME).read_bytes()
                self.assertEqual(hashlib.sha256(tar).hexdigest(),
                                 result["archive_sha256"])
                doc = json.loads((target / bundler.MANIFEST_NAME).read_text())
                self.assertFalse(doc["production_deploy_authorized"])
                with self.assertRaises(PermissionError):
                    bundler.package_to_runner(self.files, target)

    def test_12_target_outside_runner_temp_never_created(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"GITHUB_ACTIONS": "true",
                                         "RUNNER_TEMP": td}):
                with self.assertRaises(PermissionError):
                    bundler.package_to_runner(self.files, Path(td) / "other")
            self.assertFalse((Path(td) / "other").exists())

if __name__ == "__main__":
    unittest.main()
