"""Offline synthetic checks; never contacts cPanel or the public store."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.mpw_dynamic_store_cutover_20261108 import (
    BUYER_ROUTE_PROBES, FALLBACK_BLOCK, MARKER, inspect_owned_fallback,
    perform_cutover, verify_dynamic_public, verify_public_buyer_routes,
)


class DynamicStoreCutoverTests(unittest.TestCase):
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
            with patch("scripts.mpw_dynamic_store_cutover_20261108.verify_public_buyer_routes", return_value=True):
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
            with patch("scripts.mpw_dynamic_store_cutover_20261108.verify_public_buyer_routes", return_value=True):
                with contextlib.redirect_stdout(sink):
                    self.assertTrue(verify_dynamic_public("42425162108"))
        self.assertIn('"dynamic_confirmed": true', sink.getvalue())
        self.assertNotIn("mpw-shop-kicker", sink.getvalue())

    def test_six_buyer_routes_are_read_only_and_content_checked(self):
        from urllib.parse import urlsplit
        calls = []

        class Reply:
            status = 200

            def __init__(self, req, body):
                self.url = req.full_url
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def geturl(self):
                return self.url

            def read(self, limit):
                assert limit == 250_000
                return self.body

        def fetch(req, timeout):
            self.assertEqual(req.get_method(), "GET")
            self.assertEqual(timeout, 7)
            path = urlsplit(req.full_url).path
            self.assertTrue(req.full_url.startswith("https://mojplaywin.com/"))
            title, action = next((title, action) for p, title, action in BUYER_ROUTE_PROBES if p == path)
            calls.append(path)
            return Reply(req, title + b" " + action)

        with patch("scripts.mpw_dynamic_store_cutover_20261108.urllib.request.urlopen", side_effect=fetch):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(verify_public_buyer_routes("42425162108-before"))
        self.assertEqual(calls, [p for p, _, _ in BUYER_ROUTE_PROBES])
        self.assertEqual(len(calls), 6)

    def test_buyer_route_failure_forces_cutover_rollback(self):
        from scripts.mpw_dynamic_store_cutover_20261108 import PRODUCT_ROUTES
        html = b"mpw-shop-kicker mpw-store-catalog-20261026 " + b" ".join(PRODUCT_ROUTES)
        sink = io.StringIO()
        with patch("scripts.mpw_dynamic_store_cutover_20261108.public_response", return_value=html):
            with patch("scripts.mpw_dynamic_store_cutover_20261108.verify_public_buyer_routes", return_value=False):
                with contextlib.redirect_stdout(sink):
                    with self.assertRaisesRegex(RuntimeError, "LIVE_DYNAMIC_PUBLIC_SMOKE_FAILED"):
                        perform_cutover(self.public, self.backups, "42425162110", lambda: verify_dynamic_public("42425162110"))
        self.assertIn('"buyer_route_guard_failed": 1', sink.getvalue())
        self.assertIn('"dynamic_confirmed": false', sink.getvalue())
        self.assertEqual((self.public / ".htaccess").read_bytes(), self.original)
        self.assertIn(MARKER, (self.public / "store/index.html").read_bytes())

    def test_buyer_route_http_error_is_redacted(self):
        from urllib.error import HTTPError
        sink = io.StringIO()
        with patch("scripts.mpw_dynamic_store_cutover_20261108.urllib.request.urlopen",
                   side_effect=HTTPError("https://mojplaywin.com/private", 404, "not found", {}, None)):
            with contextlib.redirect_stdout(sink):
                self.assertFalse(verify_public_buyer_routes("42425162108-after"))
        self.assertIn('"category": "http_404"', sink.getvalue())
        self.assertNotIn("private", sink.getvalue())

    def test_buyer_route_content_mismatch_blocks_release(self):
        class WrongContent:
            status = 200

            def __init__(self, request):
                self.url = request.full_url

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def geturl(self):
                return self.url

            def read(self, limit):
                return b"<html>Unrelated success page</html>"

        sink = io.StringIO()
        with patch("scripts.mpw_dynamic_store_cutover_20261108.urllib.request.urlopen",
                   side_effect=lambda req, timeout: WrongContent(req)):
            with contextlib.redirect_stdout(sink):
                self.assertFalse(verify_public_buyer_routes("42425162108-before"))
        self.assertIn('"category": "unexpected_response"', sink.getvalue())
        self.assertIn('"checked": 0', sink.getvalue())

    def test_failed_buyer_baseline_cannot_start_cutover(self):
        from types import SimpleNamespace
        from scripts.mpw_dynamic_store_cutover_20261108 import main
        with patch("scripts.mpw_dynamic_store_cutover_20261108.pwd.getpwuid",
                   return_value=SimpleNamespace(pw_name="zomorod2")):
            with patch("scripts.mpw_dynamic_store_cutover_20261108.check_actual_staging_store"):
                with patch("scripts.mpw_dynamic_store_cutover_20261108.public_response",
                           return_value=MARKER + b"x" * 2400):
                    with patch("scripts.mpw_dynamic_store_cutover_20261108.verify_public_buyer_routes", return_value=False):
                        with patch("scripts.mpw_dynamic_store_cutover_20261108.perform_cutover") as cutover:
                            with self.assertRaisesRegex(RuntimeError, "PUBLIC_BUYER_ROUTE_BASELINE_FAILED"):
                                main("42425162111")
        cutover.assert_not_called()


if __name__ == "__main__":
    unittest.main()
