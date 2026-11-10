"""Offline synthetic checks; never contacts cPanel or the public store."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.mpw_dynamic_store_cutover_20261108 import (
    FALLBACK_BLOCK, MARKER, inspect_owned_fallback, perform_cutover,
    verify_buyer_route_resolution, verify_dynamic_public,
    verify_invoice_start_rejects_get,
    verify_guarded_store_source,
)


SAFE_STORE_SOURCE = b'''from django.shortcuts import render
PRODUCTS = []
def store(request):
 # Optional analytics cannot hide the storefront or leak visitor details.
 try:
  from .commerce_funnel import record_funnel_event
  record_funnel_event(request, "view_store")
 except Exception as exc:
  import logging
  logging.getLogger(__name__).warning("Optional analytics unavailable")
 return render(request, "mojplaywin/store.html", {"products": PRODUCTS})
'''


class DynamicStoreCutoverTests(unittest.TestCase):
    @staticmethod
    def sample_route_resolver(path):
        def handler(request):
            return request
        if path == "/store/":
            return SimpleNamespace(url_name="store", args=(), kwargs={}, func=handler)
        for product_id in (72, 225, 879):
            if path == f"/store/product/{product_id}/checkout/":
                return SimpleNamespace(url_name="product_checkout", args=(),
                                       kwargs={"product_id": product_id}, func=handler)
            if path == f"/commerce/trx-easy/start/{product_id}/":
                return SimpleNamespace(url_name="trx_invoice_start", args=(),
                                       kwargs={"product_id": product_id}, func=handler)
        raise LookupError("unknown route")

    def test_all_three_real_buyer_url_routes_must_resolve(self):
        callback = verify_buyer_route_resolution(self.sample_route_resolver)
        self.assertTrue(callable(callback))

    def test_missing_checkout_route_refuses_store_cutover(self):
        def incomplete(path):
            if path.endswith("/879/checkout/"):
                raise LookupError("404")
            return self.sample_route_resolver(path)
        with self.assertRaisesRegex(RuntimeError, "STAGING_BUYER_ROUTE_UNAVAILABLE"):
            verify_buyer_route_resolution(incomplete)

    def test_checkout_route_with_wrong_product_refuses_cutover(self):
        def incorrect(path):
            match = self.sample_route_resolver(path)
            if path.endswith("/225/checkout/"):
                match.kwargs = {"product_id": 72}
            return match
        with self.assertRaisesRegex(RuntimeError, "STAGING_BUYER_CHECKOUT_ROUTE_INVALID"):
            verify_buyer_route_resolution(incorrect)

    def test_wrong_store_url_handler_refuses_cutover(self):
        def incorrect(path):
            match = self.sample_route_resolver(path)
            if path == "/store/":
                match.url_name = "old_static_store"
            return match
        with self.assertRaisesRegex(RuntimeError, "STAGING_STORE_URL_NOT_RESOLVED"):
            verify_buyer_route_resolution(incorrect)

    def test_missing_invoice_start_route_refuses_cutover(self):
        def incomplete(path):
            if path == "/commerce/trx-easy/start/225/":
                raise LookupError("404")
            return self.sample_route_resolver(path)
        with self.assertRaisesRegex(RuntimeError, "STAGING_BUYER_ROUTE_UNAVAILABLE"):
            verify_buyer_route_resolution(incomplete)

    def test_invoice_start_route_with_wrong_product_refuses_cutover(self):
        def incorrect(path):
            match = self.sample_route_resolver(path)
            if path == "/commerce/trx-easy/start/879/":
                match.kwargs = {"product_id": 72}
            return match
        with self.assertRaisesRegex(RuntimeError, "STAGING_INVOICE_START_ROUTE_INVALID"):
            verify_buyer_route_resolution(incorrect)

    def test_invoice_start_get_must_return_post_only_405(self):
        factory = SimpleNamespace(get=lambda path, **kwargs: object())
        def good(path):
            match = self.sample_route_resolver(path)
            match.func = lambda request: SimpleNamespace(
                status_code=405, get=lambda key, default="": "POST" if key == "Allow" else default)
            return match
        verify_invoice_start_rejects_get(good, factory)

        def unsafe(path):
            match = good(path)
            if path == "/commerce/trx-easy/start/72/":
                match.func = lambda request: SimpleNamespace(
                    status_code=200, get=lambda key, default="": "GET")
            return match
        with self.assertRaisesRegex(RuntimeError, "STAGING_INVOICE_START_POST_ONLY_NOT_PROVEN"):
            verify_invoice_start_rejects_get(unsafe, factory)

    def test_optional_existing_funnel_module_is_not_an_automatic_cutover_block(self):
        verify_guarded_store_source(SAFE_STORE_SOURCE)

    def test_unguarded_funnel_call_is_refused(self):
        source = SAFE_STORE_SOURCE.replace(b" try:\n", b" if True:\n").replace(
            b" except Exception as exc:\n", b" else:\n")
        with self.assertRaisesRegex(RuntimeError, "STAGING_GUARDED_VIEW_NOT_PROVEN"):
            verify_guarded_store_source(source)

    def test_analytics_handler_that_raises_is_refused(self):
        source = SAFE_STORE_SOURCE.replace(
            b'  logging.getLogger(__name__).warning("Optional analytics unavailable")',
            b'  raise RuntimeError("fail closed")',
        )
        with self.assertRaisesRegex(RuntimeError, "STAGING_GUARDED_VIEW_NOT_PROVEN"):
            verify_guarded_store_source(source)

    def test_mismatched_template_and_duplicate_view_are_refused(self):
        with self.assertRaisesRegex(RuntimeError, "STAGING_GUARDED_VIEW_NOT_PROVEN"):
            verify_guarded_store_source(SAFE_STORE_SOURCE.replace(
                b"mojplaywin/store.html", b"mojplaywin/other.html"))
        with self.assertRaisesRegex(RuntimeError, "STAGING_GUARDED_VIEW_NOT_PROVEN"):
            verify_guarded_store_source(SAFE_STORE_SOURCE + SAFE_STORE_SOURCE)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.public = Path(self.temp.name) / "public"
        self.public.mkdir()
        (self.public / "tmp").mkdir()
        (self.public / "tmp/restart.txt").touch()
        (self.public / "store").mkdir()
        (self.public / "store/index.html").write_bytes(
            b"<html><body>" + MARKER + b"</body></html>"
        )
        # Real live rule starts at line seven, so do not assume a file prefix.
        self.original = b"# retained owner config\n" * 6 + FALLBACK_BLOCK + b"PassengerAppRoot retained\n"
        (self.public / ".htaccess").write_bytes(self.original)
        self.backups = Path(self.temp.name) / "private-backups"

    def test_line_seven_exact_rule_removed_without_impact_on_other_config(self):
        original, changed, _ = inspect_owned_fallback(self.public)
        self.assertEqual(original, self.original)
        self.assertEqual(changed, self.original.replace(FALLBACK_BLOCK, b"", 1))
        checks = []

        def successful_probe():
            checks.append(1)
            self.assertFalse((self.public / "store").exists())
            self.assertEqual((self.public / ".htaccess").read_bytes(), changed)
            return True

        with contextlib.redirect_stdout(io.StringIO()):
            perform_cutover(self.public, self.backups, "42425162108", successful_probe)
        self.assertEqual(checks, [1])
        self.assertTrue((self.backups / "42425162108/store/index.html").is_file())
        self.assertEqual((self.backups / "42425162108/htaccess.original").read_bytes(), original)
        self.assertEqual((self.public / ".htaccess").read_bytes(), changed)

    def test_failed_public_probe_restores_exact_original_files(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "LIVE_DYNAMIC_PUBLIC_SMOKE_FAILED"):
                perform_cutover(self.public, self.backups, "42425162109", lambda: False)
        self.assertEqual((self.public / ".htaccess").read_bytes(), self.original)
        self.assertIn(MARKER, (self.public / "store/index.html").read_bytes())
        self.assertTrue((self.public / "tmp/restart.txt").is_file())

    def test_duplicate_rule_and_unrelated_store_file_are_rejected(self):
        (self.public / ".htaccess").write_bytes(self.original + FALLBACK_BLOCK)
        with self.assertRaisesRegex(RuntimeError, "FALLBACK_ANCHOR_DRIFT"):
            inspect_owned_fallback(self.public)
        (self.public / ".htaccess").write_bytes(self.original)
        (self.public / "store/unrelated.txt").write_text("preserve")
        with self.assertRaisesRegex(RuntimeError, "UNOWNED_STORE_DIRECTORY_CONTENTS"):
            inspect_owned_fallback(self.public)
        self.assertEqual((self.public / "store/unrelated.txt").read_text(), "preserve")

    def test_invalid_run_id_cannot_create_backup(self):
        with self.assertRaisesRegex(RuntimeError, "INVALID_RUN_ID"):
            perform_cutover(self.public, self.backups, "../../escape", lambda: True)
        self.assertFalse(self.backups.exists())

    def test_owner_only_workflow_is_fail_closed(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/mpw-dynamic-store-cutover-20261108.yml").read_text()
        self.assertIn("github.event.comment.user.login == 'mojtabarozegar11-ship-it'", workflow)
        self.assertIn("github.event.comment.author_association == 'OWNER'", workflow)
        self.assertIn("github.event.issue.number == 1600", workflow)
        self.assertIn("github.event.comment.body == 'MPW-STORE-DYNAMIC-CUTOVER-20261108'", workflow)
        self.assertIn("timeout 150s ssh -T", workflow)
        self.assertNotIn("StrictHostKeyChecking no", workflow)

    def test_public_probe_reports_only_redacted_static_category(self):
        sink = io.StringIO()
        with patch("scripts.mpw_dynamic_store_cutover_20261108.public_response", return_value=(MARKER + b"x" * 2400)):
            with patch("scripts.mpw_dynamic_store_cutover_20261108.time.sleep", return_value=None):
                with contextlib.redirect_stdout(sink):
                    self.assertFalse(verify_dynamic_public("42425162108"))
        out = sink.getvalue()
        self.assertIn('"still_owned_static_fallback": 18', out)
        self.assertIn('"attempts": 18', out)
        self.assertIn('"dynamic_confirmed": false', out)
        self.assertNotIn("buyer", out)

    def test_public_probe_stops_at_deadline_without_extra_requests(self):
        sink = io.StringIO()
        with patch("scripts.mpw_dynamic_store_cutover_20261108.public_response", return_value=(MARKER + b"x" * 2400)) as probe:
            with patch("scripts.mpw_dynamic_store_cutover_20261108.time.monotonic", side_effect=[100, 100, 156]):
                with patch("scripts.mpw_dynamic_store_cutover_20261108.time.sleep", return_value=None):
                    with contextlib.redirect_stdout(sink):
                        self.assertFalse(verify_dynamic_public("42425162108"))
        self.assertEqual(probe.call_count, 1)
        self.assertIn('"attempts": 1', sink.getvalue())
        self.assertIn('"still_owned_static_fallback": 1', sink.getvalue())

    def test_public_probe_recovers_after_previous_six_static_responses(self):
        from scripts.mpw_dynamic_store_cutover_20261108 import PRODUCT_ROUTES
        html = b"mpw-shop-kicker mpw-store-catalog-20261026 " + b" ".join(PRODUCT_ROUTES)
        sink = io.StringIO()
        with patch("scripts.mpw_dynamic_store_cutover_20261108.public_response",
                   side_effect=[MARKER + b"x" * 2400] * 7 + [html]) as probe:
            with patch("scripts.mpw_dynamic_store_cutover_20261108.time.sleep", return_value=None):
                with contextlib.redirect_stdout(sink):
                    self.assertTrue(verify_dynamic_public("42425162108"))
        self.assertEqual(probe.call_count, 8)
        self.assertIn('"attempts": 8', sink.getvalue())
        self.assertIn('"still_owned_static_fallback": 7', sink.getvalue())

    def test_public_probe_reports_verified_django_without_raw_html(self):
        from scripts.mpw_dynamic_store_cutover_20261108 import PRODUCT_ROUTES
        html = b"mpw-shop-kicker mpw-store-catalog-20261026 " + b" ".join(PRODUCT_ROUTES)
        sink = io.StringIO()
        with patch("scripts.mpw_dynamic_store_cutover_20261108.public_response", return_value=html):
            with contextlib.redirect_stdout(sink):
                self.assertTrue(verify_dynamic_public("42425162108"))
        self.assertIn('"dynamic_confirmed": true', sink.getvalue())
        self.assertNotIn("mpw-shop-kicker", sink.getvalue())


if __name__ == "__main__":
    unittest.main()

