"""No buyer GET or private file may be opened by the route inspection."""
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.mpw_trx_active_download_route_readonly_20261116 import (
    BASE, expand_literal_route, inspect_active_patterns,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts/mpw_trx_active_download_route_readonly_20261116.py"
WF = ROOT / ".github/workflows/mpw-trx-safe-flags-evidence-20261115.yml"


def handler(request=None):
    return None


def match(path):
    return SimpleNamespace(func=handler)


class MerchantNativeDownloadRouteSafety(unittest.TestCase):
    def test_replaces_bounded_integer_path_parameter(self):
        self.assertEqual(
            expand_literal_route("/commerce/trx-easy/download/<int:item_id>/"),
            "/commerce/trx-easy/download/1/",
        )

    def test_wrong_external_prefix_rejected(self):
        self.assertIsNone(expand_literal_route("/admin/download/<int:id>/"))

    def test_query_string_not_a_safe_route(self):
        self.assertIsNone(expand_literal_route("/commerce/trx-easy/download/<int:id>/?key=abc"))

    def test_path_traversal_not_generated_by_expander(self):
        self.assertIsNone(expand_literal_route("/commerce/trx-easy//download/1/"))

    def test_backslash_not_in_approved_route(self):
        self.assertIsNone(expand_literal_route("/commerce/trx-easy/\\download/1/"))

    def test_unknown_converter_denied(self):
        self.assertIsNone(expand_literal_route("/commerce/trx-easy/download/<uuid:id>/"))

    def test_missing_trailing_slash_not_a_match(self):
        self.assertIsNone(expand_literal_route("/commerce/trx-easy/download/<int:id>"))

    def test_registered_and_actual_matching_download(self):
        result = inspect_active_patterns(
            [("/commerce/trx-easy/download/<int:item_id>/", handler)],
            match, {"download_paid": handler},
        )
        self.assertTrue(result["declared_paid_download_route"])
        self.assertTrue(result["actual_paid_download_route_resolves"])
        self.assertTrue(result["resolved_download_is_current_registered_handler"])
        self.assertFalse(result["download_request_executed"])

    def test_unregistered_route_reports_no_download(self):
        result = inspect_active_patterns([], match, {"download_paid": handler})
        self.assertFalse(result["declared_paid_download_route"])

    def test_missing_handler_does_not_claim_same_active_view(self):
        result = inspect_active_patterns(
            [("/commerce/trx-easy/download/<int:id>/", handler)],
            match, {"download_paid": None},
        )
        self.assertTrue(result["declared_paid_download_route"])
        self.assertFalse(result["resolved_download_is_current_registered_handler"])

    def test_faked_resolver_callable_cannot_claim_registered_handler(self):
        def different(request=None):
            return None
        result = inspect_active_patterns(
            [("/commerce/trx-easy/download/<int:id>/", handler)],
            lambda _: SimpleNamespace(func=different),
            {"download_paid": handler},
        )
        self.assertTrue(result["actual_paid_download_route_resolves"])
        self.assertFalse(result["resolved_download_is_current_registered_handler"])

    def test_bad_resolver_remains_unverified(self):
        def broken(_):
            raise LookupError("not found")
        result = inspect_active_patterns(
            [("/commerce/trx-easy/download/<int:id>/", handler)],
            broken, {"download_paid": handler},
        )
        self.assertFalse(result["actual_paid_download_route_resolves"])

    def test_an_untrusted_registry_item_has_no_paid_route(self):
        result = inspect_active_patterns([("https://evil.example/download/1/", handler)],
                                         match, {"download_paid": handler})
        self.assertTrue(result["untrusted_route_format_observed"])
        self.assertFalse(result["declared_paid_download_route"])

    def test_empty_registry_is_not_positive_route_evidence(self):
        result = inspect_active_patterns(None, match, {"download_paid": handler})
        self.assertFalse(result["declared_paid_download_route"])

    def test_no_real_client_session_or_file_touch(self):
        src = SRC.read_text("utf-8")
        for banned in (
            "RequestFactory(", "Client(", "requests.get(", "requests.post(",
            "urllib.request", ".save(", "objects.create(", "FileResponse(",
            "open(", "download_paid_item(", "view(request,", "request.user =",
            "sendrawtransaction", "broadcasttransaction", "private_key",
        ):
            with self.subTest(token=banned):
                self.assertNotIn(banned, src)
        self.assertIn('"buyer_impersonated": False', src)

    def test_ci_workflow_pinned_readonly_web_routing_probe(self):
        s = WF.read_text("utf-8")
        self.assertIn("scripts/mpw_trx_active_download_route_readonly_20261116.py", s)
        self.assertIn("tests.test_mpw_trx_active_download_route_readonly_20261116", s)
        self.assertIn("MPW_TRX_ACTUAL_DOWNLOAD_ROUTE_READONLY=", s)
        self.assertIn("permissions:\n  contents: read", s)
        self.assertNotIn("  workflow_dispatch:", s)
        self.assertNotIn("  push:", s)


if __name__ == "__main__":
    unittest.main()
