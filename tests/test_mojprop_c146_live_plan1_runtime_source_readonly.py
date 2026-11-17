"""C146 source-only regression: public Plan1 cannot be declared live from CLI source.

The test suite uses temporary local files only; no cPanel access, DNS, HTTP,
database, customer data, wallet, migrations or server changes.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import mojprop_c146_live_plan1_runtime_source_readonly as diag


def sample_urls():
    return b'''from django.urls import path
from core.moj_prop_views import moj_prop_interest, moj_prop_interest_form
urlpatterns = [
  path("moj-prop-interest/", moj_prop_interest, name="moj_prop_interest"),
  path("moj-prop-interest/form/", moj_prop_interest_form,
       name="moj_prop_interest_form"),
]'''


class C146Integrity(unittest.TestCase):
    def test_01_expected_exact_four_sources(self):
        self.assertEqual(set(diag.SOURCE), {
            "config/urls.py", "core/moj_prop_views.py",
            "core/templates/mojplaywin/moj_prop_interest_form_d.html",
            "prop_firm/lead_models.py",
        })
        self.assertEqual(len(set(diag.SOURCE.values())), 4)
        self.assertTrue(all(len(sha) == 40 for sha in diag.SOURCE.values()))

    def test_02_django_ast_requires_both_exact_paths_and_views(self):
        self.assertEqual(diag.declared_routes(sample_urls()),
                         {"browser_get": True, "consent_post": True})

    def test_03_comments_and_quoted_strings_never_spoof_route(self):
        fake = b'''# path("moj-prop-interest/form/",moj_prop_interest_form)
message = "path('moj-prop-interest/', moj_prop_interest)"
'''
        self.assertEqual(diag.declared_routes(fake),
                         {"browser_get": False, "consent_post": False})

    def test_04_legacy_starter30_must_not_be_mistaken_for_real_plan1(self):
        fake = b'''from django.urls import path
urlpatterns = [path("moj-prop-intake/", mojprop_intake),
path("moj-prop-interest/form/", old_starter30_checkout),
path("moj-prop-interest/", old_product_checkout)]
'''
        self.assertEqual(diag.declared_routes(fake),
                         {"browser_get": False, "consent_post": False})

    def test_05_malicious_source_does_not_get_imported_or_executed(self):
        fake = b'''raise RuntimeError("never execute me")
from django.urls import path
urlpatterns=[path("moj-prop-interest/form/", moj_prop_interest_form)]
'''
        self.assertEqual(diag.declared_routes(fake)["browser_get"], True)
        # Source AST discovery does not execute the top-level raise.
        self.assertIn("return out", ast.get_source_segment(
            Path(diag.__file__).read_text("utf-8"),
            next(n for n in ast.walk(ast.parse(
                Path(diag.__file__).read_text("utf-8")))
                if isinstance(n, ast.FunctionDef) and n.name == "declared_routes")
        ))

    def test_06_nonutf8_and_malformed_ast_fail_closed(self):
        for blob in (b"\xff", b"this is !!!", b"", b"x" * (diag.MAX_FILE_BYTES+1)):
            self.assertEqual(diag.declared_routes(blob),
                             {"browser_get": False, "consent_post": False})

    def test_07_exact_git_blob_rejects_nonbytes_and_oversize(self):
        blob = sample_urls()
        import hashlib
        self.assertEqual(diag.exact_git_blob(blob),
                         hashlib.sha1(b"blob " + str(len(blob)).encode() +
                                      b"\0" + blob).hexdigest())
        for invalid in ("str", None, bytearray(b"hi"), b"x"*(diag.MAX_FILE_BYTES+1)):
            with self.assertRaises(ValueError):
                diag.exact_git_blob(invalid)

    def test_08_safe_files_no_symlink_or_tampered_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            os.chmod(root, 0o700)
            config = root / "config"
            config.mkdir(mode=0o700)
            blob = sample_urls()
            target = config / "urls.py"
            target.write_bytes(blob)
            os.chmod(target, 0o600)
            sha = diag.exact_git_blob(blob)
            with patch.object(diag, "ROOT", root), \
                 patch.object(diag, "SOURCE", {"config/urls.py": sha}):
                self.assertEqual(diag.source_state(root, "config/urls.py", sha),
                                 "matches")
                target.write_bytes(blob + b" #drift")
                self.assertEqual(diag.source_state(root, "config/urls.py", sha),
                                 "drifted")
                target.unlink()
                target.symlink_to("/etc/passwd")
                self.assertEqual(diag.source_state(root, "config/urls.py", sha),
                                 "unsafe")
                self.assertEqual(diag.source_state(root, "../private", sha),
                                 "unsafe")

    def test_09_owned_group_writable_parent_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            os.chmod(root, 0o770)
            with patch.object(diag, "ROOT", root):
                self.assertFalse(diag.safe_directory(root))
                self.assertEqual(diag.source_state(root, "config/urls.py", "a"*40),
                                 "unsafe")

    def test_10_report_never_claims_worker_parity_or_restored_backup(self):
        import inspect
        source = inspect.getsource(diag.report)
        self.assertIn('"actual_passenger_worker_source_proven": False', source)
        self.assertIn('"full_app_db_media_restore_proven": False', source)
        self.assertIn('"public_plan1_get_verified": False', source)
        self.assertIn('"production_change_or_cost_authorized": False', source)
        self.assertIn('"customer_data_accessed": False', source)

    def test_11_no_executive_side_effects_or_network(self):
        source = Path(diag.__file__).read_text("utf-8")
        for bad in ("subprocess", "urllib", "requests.get", "requests.post",
                    "cursor(", "connection.execute(", "sendTransaction",
                    "open('w')", "shutil.copy", "os.system"):
            self.assertNotIn(bad, source)
        self.assertEqual(set(diag.ROUTES), {"browser_get", "consent_post"})

if __name__ == "__main__":
    unittest.main()
