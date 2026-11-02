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


if __name__ == "__main__":
    unittest.main()
