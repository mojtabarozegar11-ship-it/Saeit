"""No production access: redacted MojPlayWin Passenger probe synthetic tests."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.mpw_public_passenger_runtime_readonly_20261102 import (
    _as_target_root, _uapi_summary, _passenger_status_summary, inspect,
)


class PassengerDiagnosticTests(unittest.TestCase):
    def test_exact_allowlisted_roots_only(self):
        self.assertEqual(_as_target_root("/home/zomorod2/mojplaywin.com/"), "public")
        self.assertEqual(_as_target_root("Saeit-staging"), "staging")
        self.assertEqual(_as_target_root("../mojplaywin.com"), "other")
        self.assertEqual(_as_target_root("/another-site/mojplaywin.com"), "other")

    def test_uapi_never_returns_other_site_or_secrets(self):
        payload = {"result": {"status": 1, "data": [
            {"app_path": "/home/zomorod2/mojplaywin.com",
             "domain": "mojplaywin.com", "secret": "synthetic sensitive token"},
            {"app_path": "/home/elsewhere/other-site", "domain": "other.test"}]}}
        summary = _uapi_summary(payload)
        self.assertTrue(summary["ok"])
        self.assertTrue(summary["public_root"])
        self.assertFalse(summary["staging_root"])
        self.assertTrue(summary["mentions_domain"])
        self.assertNotIn("synthetic", json.dumps(summary))
        self.assertNotIn("other-site", json.dumps(summary))

    def test_passenger_status_only_classifies_allowlisted_app_roots(self):
        raw = ("--- Application groups ---\n"
               "/home/zomorod2/mojplaywin.com#default:\n"
               "  App root: /home/zomorod2/mojplaywin.com\n"
               "  * PID: 12345 Sessions: 0\n"
               "other-app:\n"
               "  App root: /private/other-app-with-secret\n")
        result = _passenger_status_summary(raw)
        self.assertTrue(result["available"])
        self.assertTrue(result["readable"])
        self.assertTrue(result["public_root"])
        self.assertFalse(result["staging_root"])
        self.assertNotIn("other-app", json.dumps(result))

    def test_store_source_probe_reports_only_safe_file_metadata(self):
        from scripts.mpw_public_passenger_runtime_readonly_20261102 import inspect_store_sources
        with tempfile.TemporaryDirectory() as td:
            public = Path(td) / "public"
            app = Path(td) / "staging"
            public.mkdir()
            (app / "core").mkdir(parents=True)
            (app / "core" / "mojplaywin_views.py").write_text(
                "def store(request):\\n  record_funnel_event(request, 'view_store')\\n"
                "  # synthetic confidential marker must never be printed\\n"
            )
            info = inspect_store_sources(public=public, app=app)
            self.assertEqual(info["classification"], "MPW_STORE_SOURCE_METADATA_ONLY")
            self.assertFalse(info["roots"]["public"]["view"]["present"])
            self.assertTrue(info["roots"]["staging"]["view"]["present"])
            self.assertFalse(info["database_read"])
            self.assertFalse(info["files_modified"])
            self.assertNotIn("confidential marker", json.dumps(info))
            self.assertNotIn(str(app), json.dumps(info))

    def test_synthetic_public_app_contract_and_no_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            public = Path(td) / "public"
            app = Path(td) / "staging"
            public.mkdir()
            (app / "services").mkdir(parents=True)
            (public / "tmp").mkdir()
            (public / ".htaccess").write_text(
                "PassengerAppRoot /home/zomorod2/mojplaywin.com\n")
            (public / "passenger_wsgi.py").write_text(
                "APP='/home/zomorod2/Saeit-staging'\n")
            (app / "services/mpw_trx_guest_commerce.py").write_text(
                "synthetic adapter content")
            (public / "tmp/restart.txt").touch()
            report = inspect(public=public, app=app, uapi_payload={
                "result": {"status": 1, "data": [
                    {"app_path": "/home/zomorod2/mojplaywin.com"}]}},
                workers={"candidate_count": 2, "cwd_public": 1, "cwd_staging": 1},
                status_payload="App root: /home/zomorod2/Saeit-staging")
            self.assertTrue(report["htaccess_public_root"])
            self.assertTrue(report["public_wsgi_references_staging"])
            self.assertTrue(report["uapi_registers_public_root"])
            self.assertTrue(report["passenger_status_staging_root"])
            self.assertEqual(report["owned_candidate_worker_count_capped"], 2)
            self.assertFalse(report["guest_module_restored_to_known_prior"])
            self.assertFalse(report["files_modified"])
            self.assertFalse(report["effective_public_worker_proven"])
            self.assertFalse(report["release_permitted"])


    def test_exact_static_fallback_inventory_without_printing_names(self):
        from scripts.mpw_public_passenger_runtime_readonly_20261102 import (
            STORE_FALLBACK_PREFIX, inspect_public_store_fallback,
        )
        with tempfile.TemporaryDirectory() as td:
            public = Path(td)
            store = public / "store"
            store.mkdir()
            (store / "index.html").write_text(
                "<h1>Static fallback</h1>MPW_STATIC_STORE_FALLBACK_V1"
            )
            result = inspect_public_store_fallback(public, STORE_FALLBACK_PREFIX + "PassengerAppRoot public\n")
            self.assertTrue(result["exact_leading_rule"])
            self.assertTrue(result["exact_block_once"])
            self.assertTrue(result["normalized_block_once"])
            later_position = inspect_public_store_fallback(public, "PassengerAppRoot public\n" + STORE_FALLBACK_PREFIX)
            self.assertFalse(later_position["exact_leading_rule"])
            self.assertTrue(later_position["exact_block_once"])
            self.assertFalse(later_position["marker_at_first_line"])
            self.assertEqual(later_position["marker_line_capped"], 1)
            self.assertTrue(result["rule_marker_once"])
            self.assertTrue(result["store_index_only"])
            self.assertTrue(result["index_owner_marker"])
            self.assertEqual(result["entry_count_capped"], 1)
            (store / "other-unrelated-file.txt").write_text("private-synthetic")
            later = inspect_public_store_fallback(public, STORE_FALLBACK_PREFIX)
            self.assertFalse(later["store_index_only"])
            self.assertEqual(later["entry_count_capped"], 2)
            self.assertNotIn("private-synthetic", json.dumps(later))
            self.assertNotIn("other-unrelated-file", json.dumps(later))



    def test_error_log_probe_returns_only_fixed_categories(self):
        from scripts.mpw_public_passenger_runtime_readonly_20261102 import inspect_error_classes
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "error_log").write_text(
                "buyer@example.com /private/order/SECRET ModuleNotFoundError: No module named whatever\n"
                "Traceback (most recent call last)\n",
            )
            result = inspect_error_classes(root)
            self.assertEqual(result["regular_recent_error_files"], 1)
            self.assertEqual(result["classes"]["module_missing"], 1)
            self.assertEqual(result["classes"]["python_traceback"], 1)
            self.assertFalse(result["files_modified"])
            self.assertFalse(result["raw_log_emitted"])
            self.assertNotIn("buyer@", json.dumps(result))
            self.assertNotIn("SECRET", json.dumps(result))

    def test_wiring_flags_are_redacted(self):
        from scripts.mpw_public_passenger_runtime_readonly_20261102 import inspect_passenger_wiring
        conf = ("PassengerPython /home/zomorod2/virtualenv/other-app/3.11/bin/python\n"
                "PassengerStartupFile passenger_wsgi.py\n"
                "RewriteRule ^store/?$ store/index.html [END]\n")
        result = inspect_passenger_wiring(conf, "APP='/home/zomorod2/Saeit-staging'\nfrom config.wsgi import application")
        self.assertEqual(result["passenger_python_directives"], 1)
        self.assertTrue(result["passenger_python_311"])
        self.assertTrue(result["passenger_python_other_venv"])
        self.assertFalse(result["passenger_python_stage_venv"])
        self.assertTrue(result["wsgi_mentions_staging_source"])
        self.assertTrue(result["wsgi_has_django_entrypoint"])
        self.assertNotIn("other-app", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
