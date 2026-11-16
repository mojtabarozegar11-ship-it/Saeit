"""C130: offline checks for bounded, private, read-only cPanel parity audit."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import mojprop_live_cpanel_source_parity_readonly_c130 as probe


def route_source():
    return (
        'from django.urls import path\n'
        'urlpatterns = [\n'
        '  path("moj-prop-intake/", mojprop_intake),\n'
        '  path("moj-prop-status/", mojprop_receipt_status),\n'
        '  path("moj-prop-quote/<str:token>/", customer_quote),\n'
        ']\n'
    ).encode()


class SourceParityOfflineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.app = self.root / "app"
        self.app.mkdir()
        self.passenger = self.root / "passenger_wsgi.py"
        self.passenger.write_text("sys.path.insert(0, '/home/zomorod2/Saeit-staging')\n")
        self.url = self.app / "config/urls.py"
        self.url.parent.mkdir()
        self.url.write_bytes(route_source())
        self.view = self.app / "core/mojprop_views.py"
        self.view.parent.mkdir()
        self.view.write_text(
            "def mojprop_intake(request): pass\n"
            "def mojprop_receipt_status(request): pass\n"
        )
        self.names = {
            "config/urls.py": probe.git_blob_digest(self.url.read_bytes()),
            "core/mojprop_views.py": probe.git_blob_digest(self.view.read_bytes()),
        }
        patched = patch.object(probe, "REVIEWED_BLOBS", self.names)
        patched.start()
        self.addCleanup(patched.stop)

    def test_blob_is_git_compatible(self):
        # Git test vector: echo -n "test content" | git hash-object --stdin
        self.assertEqual(probe.git_blob_digest(b"test content"),
                         "d670460b4b4aece5915caf5c68d12f560a9fe3e4")

    def test_matching_source_metadata_only(self):
        report = probe.audit(self.app, self.passenger, owner_ok=True)
        self.assertEqual(report["reviewed_source_exact_match_count"], 2)
        self.assertTrue(report["active_mojprop_routes_present"])
        self.assertTrue(report["intake_status_handlers_present"])
        self.assertTrue(report["passenger_wsgi_staging_reference_present"])
        self.assertFalse(report["effective_passenger_runtime_verified"])
        self.assertFalse(report["database_restore_executed"])
        self.assertFalse(report["production_deploy_authorized"])

    def test_changed_source_detects_drift(self):
        self.view.write_text("def mojprop_intake(request): pass\n")
        report = probe.audit(self.app, self.passenger, owner_ok=True)
        self.assertEqual(report["source_status"]["core/mojprop_views.py"], "drift")
        self.assertFalse(report["intake_status_handlers_present"])

    def test_missing_source_detected(self):
        self.view.unlink()
        result = probe.audit(self.app, self.passenger, owner_ok=True)
        self.assertEqual(result["source_status"]["core/mojprop_views.py"], "missing")

    def test_symlinked_source_denied(self):
        self.view.unlink()
        self.view.symlink_to(self.passenger)
        self.assertEqual(probe.compare_source(self.view, self.names["core/mojprop_views.py"]),
                         "unsafe")

    def test_symlinked_ancestor_denied(self):
        nested = self.root / "linked"
        nested.symlink_to(self.app, target_is_directory=True)
        self.assertEqual(probe.compare_source(nested / "config/urls.py", self.names["config/urls.py"]),
                         "unsafe")

    def test_large_source_denied(self):
        self.view.write_bytes(b"x" * (probe.MAX_SOURCE_BYTES + 1))
        self.assertEqual(probe.compare_source(self.view, self.names["core/mojprop_views.py"]),
                         "oversized")

    def test_fake_comment_and_string_routes_not_active(self):
        raw = (
            b"urlpatterns = []\n"
            b"# path('moj-prop-intake/', mojprop_intake)\n"
            b"demo = \"path('moj-prop-status/', mojprop_receipt_status)\"\n"
        )
        self.assertEqual(probe.declared_routes(raw), {})

    def test_nested_dead_function_not_active(self):
        raw = (
            b"urlpatterns = []\n"
            b"def never_called():\n"
            b"    path('moj-prop-intake/', mojprop_intake)\n"
        )
        self.assertEqual(probe.declared_routes(raw), {})

    def test_duplicate_active_routes_are_rejected(self):
        raw = route_source() + (
            b"urlpatterns += [path('moj-prop-intake/', attacker)]\n"
        )
        self.assertIsNone(probe.declared_routes(raw))

    def test_route_view_mismatch_denied(self):
        raw = route_source().replace(
            b"path(\"moj-prop-intake/\", mojprop_intake)",
            b"path(\"moj-prop-intake/\", attacker)",
        )
        self.url.write_bytes(raw)
        report = probe.audit(self.app, self.passenger, owner_ok=True)
        self.assertFalse(report["active_mojprop_routes_present"])

    def test_ast_parse_errors_not_printed(self):
        self.assertIsNone(probe.declared_routes(b"\xff"))
        self.assertIsNone(probe.declared_routes(b"def syntax(:"))
        self.assertFalse(probe.source_functions(b"\xff", ("x",)))

    def test_main_sanitizes_other_owner_without_reading_live_paths(self):
        with patch.object(probe.pwd, "getpwuid", return_value=type("User", (), {"pw_name": "other"})()):
            with patch.object(probe, "ROOT", self.app):
                with patch.object(probe, "PASSENGER", self.passenger):
                    stream = io.StringIO()
                    with contextlib.redirect_stdout(stream):
                        probe.main()
        txt = stream.getvalue()
        payload = json.loads(txt.split("=", 1)[1])
        self.assertFalse(payload["owner_shell_verified"])
        self.assertEqual(payload["reviewed_source_exact_match_count"], 0)
        self.assertNotIn("sys.path", txt)
        self.assertFalse(payload["production_deploy_authorized"])

    def test_source_bytes_never_in_json_output(self):
        self.view.write_text("PASSWORD='SHOULD_NEVER_PRINT'\n")
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            print(json.dumps(probe.audit(self.app, self.passenger, owner_ok=True)))
        self.assertNotIn("SHOULD_NEVER_PRINT", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
