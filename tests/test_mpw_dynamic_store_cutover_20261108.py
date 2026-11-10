"""Offline synthetic checks; never contacts cPanel or the public store."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.mpw_dynamic_store_cutover_20261108 import (
    BUYER_ROUTE_PROBES, FALLBACK_BLOCK, MARKER, inspect_owned_fallback,
    check_actual_staging_store, has_guarded_guest_invoice_form, perform_cutover,
    verify_buyer_route_resolution, verify_dynamic_public,
    verify_guarded_store_source, verify_guest_email_ownership_source,
    verify_guest_order_claim_schema,
    verify_public_buyer_routes,
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

SAFE_GUEST_EMAIL_SOURCE = b'''from services.mpw_trx_email_recovery import _posted_email, bound_checkout
def _new_user(request):
    address = _posted_email(request)
    user = request.user
    user.email = address
    user.save(update_fields=["email"])
    return user
def _dispatch(request, view, args, kwargs, *, create=False):
    if create:
        return bound_checkout(request, view, args, kwargs)
    return view(request, *args, **kwargs)
''' + b'# synthetic source guard\n' * 20


def public_buyer_body(route, title, action):
    body = title + b" " + action
    if b"Create my TRX payment invoice" not in action:
        return body
    product_id = int(route.split("/")[3])
    return (body +
            f'<form method="post" action="/commerce/trx-easy/start/{product_id}/">'.encode() +
            b'<input type="email" name="email" required>' +
            b'<input type="hidden" name="csrfmiddlewaretoken" value="synthetic-token">' +
            b'</form>')


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

    def test_noncallable_invoice_start_route_refuses_cutover(self):
        def incorrect(path):
            match = self.sample_route_resolver(path)
            if path == "/commerce/trx-easy/start/72/":
                match.func = None
            return match
        with self.assertRaisesRegex(RuntimeError, "STAGING_INVOICE_START_ROUTE_INVALID"):
            verify_buyer_route_resolution(incorrect)

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

    def test_staged_checkout_must_validate_and_persist_email_ownership(self):
        verify_guest_email_ownership_source(SAFE_GUEST_EMAIL_SOURCE)
        variants = (
            SAFE_GUEST_EMAIL_SOURCE.replace(b"_posted_email(request)", b"request.POST.get('email')"),
            SAFE_GUEST_EMAIL_SOURCE.replace(b"user.email = address", b"user.name = address"),
            SAFE_GUEST_EMAIL_SOURCE.replace(b'user.save(update_fields=["email"])', b'user.save()'),
            SAFE_GUEST_EMAIL_SOURCE.replace(b"return bound_checkout(", b"return view("),
            SAFE_GUEST_EMAIL_SOURCE.replace(b"from services.mpw_trx_email_recovery import",
                                            b"from unknown_module import"),
        )
        for invalid in variants:
            with self.subTest(invalid=invalid[:90]):
                with self.assertRaisesRegex(RuntimeError, "STAGING_GUEST_EMAIL_OWNERSHIP_NOT_PROVEN"):
                    verify_guest_email_ownership_source(invalid)

    def test_unparseable_guest_adapter_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "STAGING_GUEST_OWNER_SOURCE_INVALID"):
            verify_guest_email_ownership_source(b"def _new_user(:" + b"#" * 600)

    @staticmethod
    def _guest_order_schema(*, present=True, columns=None, unique=True, broken=False):
        required = ("id", "order_id", "email_address", "email_digest", "created_at")
        model = SimpleNamespace(_meta=SimpleNamespace(
            db_table="core_guestorderemail",
            concrete_fields=[SimpleNamespace(column=field) for field in required],
        ))
        if columns is None:
            columns = required
        connection = SimpleNamespace(
            cursor=lambda: contextlib.nullcontext(object()),
            introspection=SimpleNamespace(
                table_names=(lambda _cursor: 1 / 0) if broken else
                    (lambda _cursor: ["core_order"] + (["core_guestorderemail"] if present else [])),
                get_table_description=lambda _cursor, _table: [
                    SimpleNamespace(name=field) for field in columns
                ],
                get_constraints=lambda _cursor, _table: {
                    "unique_order": {"unique": unique, "columns": ["order_id"]}
                },
            ),
        )
        return model, connection

    def test_guest_order_claim_requires_real_schema_in_default_db(self):
        model, connection = self._guest_order_schema()
        verify_guest_order_claim_schema(model, connection)
        _, missing = self._guest_order_schema(present=False)
        with self.assertRaisesRegex(RuntimeError, "STAGING_GUEST_ORDER_EMAIL_SCHEMA_MISSING"):
            verify_guest_order_claim_schema(model, missing)
        _, unavailable = self._guest_order_schema(broken=True)
        with self.assertRaisesRegex(RuntimeError, "STAGING_GUEST_ORDER_EMAIL_SCHEMA_UNKNOWN"):
            verify_guest_order_claim_schema(model, unavailable)

    def test_guest_claim_missing_columns_blocks_release(self):
        model, connection = self._guest_order_schema(columns=(
            "id", "order_id", "email_address", "created_at",
        ))
        with self.assertRaisesRegex(RuntimeError, "STAGING_GUEST_ORDER_EMAIL_COLUMNS_MISSING"):
            verify_guest_order_claim_schema(model, connection)

    def test_guest_claim_without_unique_order_constraint_blocks_release(self):
        model, connection = self._guest_order_schema(unique=False)
        with self.assertRaisesRegex(RuntimeError, "STAGING_GUEST_ORDER_EMAIL_UNIQUE_ORDER_MISSING"):
            verify_guest_order_claim_schema(model, connection)

    def test_old_unbound_adapter_blocks_before_any_dynamic_store_mutation(self):
        with tempfile.TemporaryDirectory() as root:
            app = Path(root)
            (app / "core").mkdir()
            (app / "services").mkdir()
            (app / "core/mojplaywin_views.py").write_bytes(SAFE_STORE_SOURCE)
            # Matches the old logic's missing buyer-email binding while staying parseable.
            old_source = SAFE_GUEST_EMAIL_SOURCE.replace(
                b"return bound_checkout(", b"return view(")
            (app / "services/mpw_trx_guest_commerce.py").write_bytes(old_source)
            with patch("scripts.mpw_dynamic_store_cutover_20261108.APP", app):
                with self.assertRaisesRegex(RuntimeError, "STAGING_GUEST_EMAIL_OWNERSHIP_NOT_PROVEN"):
                    check_actual_staging_store()

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

    def test_nine_buyer_routes_are_read_only_and_content_checked(self):
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
            return Reply(req, public_buyer_body(path, title, action))

        with patch("scripts.mpw_dynamic_store_cutover_20261108.urllib.request.urlopen", side_effect=fetch):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(verify_public_buyer_routes("42425162108-before"))
        self.assertEqual(calls, [p for p, _, _ in BUYER_ROUTE_PROBES])
        self.assertEqual(len(calls), 9)

    def test_alias_http_error_blocks_release(self):
        from urllib.error import HTTPError
        from urllib.parse import urlsplit
        sink = io.StringIO()

        class Reply:
            status = 200

            def __init__(self, req):
                self.url = req.full_url
                path = urlsplit(req.full_url).path
                title, action = next((t, a) for p, t, a in BUYER_ROUTE_PROBES if p == path)
                self.body = public_buyer_body(path, title, action)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def geturl(self):
                return self.url

            def read(self, limit):
                return self.body

        def fetch(req, timeout):
            if urlsplit(req.full_url).path == "/commerce/book/72/":
                raise HTTPError(req.full_url, 404, "not found", {}, None)
            return Reply(req)

        with patch("scripts.mpw_dynamic_store_cutover_20261108.urllib.request.urlopen", side_effect=fetch):
            with contextlib.redirect_stdout(sink):
                self.assertFalse(verify_public_buyer_routes("42425162112-before"))
        self.assertIn('"checked": 6', sink.getvalue())
        self.assertIn('"route_group": "checkout"', sink.getvalue())
        self.assertIn('"category": "http_404"', sink.getvalue())

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

    def test_checkout_form_requires_exact_post_email_and_csrf(self):
        expected = (b'<form method="post" action="/commerce/trx-easy/start/225/">'
                    b'<input name="email" type="email" required>'
                    b'<input name="csrfmiddlewaretoken" value="synthetic">'
                    b'</form>')
        self.assertTrue(has_guarded_guest_invoice_form(expected, 225))
        variants = (
            expected.replace(b'method="post"', b'method="get"'),
            expected.replace(b'/start/225/', b'/start/72/'),
            expected.replace(b'name="email"', b'name="other"'),
            expected.replace(b' type="email"', b' type="text"'),
            expected.replace(b' required', b''),
            expected.replace(b'name="csrfmiddlewaretoken"', b'name="other"'),
            expected.replace(b'value="synthetic"', b'value=""'),
            expected.replace(b'</form>', b''),
        )
        for invalid in variants:
            with self.subTest(invalid=invalid):
                self.assertFalse(has_guarded_guest_invoice_form(invalid, 225))

    def test_checkout_page_with_wrong_form_blocks_public_route_gate(self):
        from urllib.parse import urlsplit
        sink = io.StringIO()

        class Reply:
            status = 200

            def __init__(self, req):
                self.url = req.full_url
                route = urlsplit(req.full_url).path
                title, action = next((t, a) for p, t, a in BUYER_ROUTE_PROBES if p == route)
                self.body = public_buyer_body(route, title, action)
                if route == "/store/product/72/checkout/":
                    self.body = self.body.replace(b'method="post"', b'method="get"')

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def geturl(self):
                return self.url

            def read(self, limit):
                return self.body

        with patch("scripts.mpw_dynamic_store_cutover_20261108.urllib.request.urlopen",
                   side_effect=lambda req, timeout: Reply(req)):
            with contextlib.redirect_stdout(sink):
                self.assertFalse(verify_public_buyer_routes("42425162108-before"))
        self.assertIn('"checked": 3', sink.getvalue())
        self.assertIn('"category": "checkout_form_invalid"', sink.getvalue())

    def test_failed_buyer_baseline_cannot_start_cutover(self):
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

    def test_buyer_probe_deadline_aborts_remaining_gets(self):
        from scripts.mpw_dynamic_store_cutover_20261108 import BUYER_ROUTE_TOTAL_SECONDS
        self.assertLessEqual(BUYER_ROUTE_TOTAL_SECONDS, 25)
        sink = io.StringIO()

        class Reply:
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
                return b"The Science and Practice of Chess Improvement Buy securely with native TRX"

        with patch("scripts.mpw_dynamic_store_cutover_20261108.time.monotonic",
                   side_effect=[100, 100, 126]):
            with patch("scripts.mpw_dynamic_store_cutover_20261108.urllib.request.urlopen",
                       side_effect=lambda request, timeout: Reply(request)) as get:
                with contextlib.redirect_stdout(sink):
                    self.assertFalse(verify_public_buyer_routes("42425162108-before"))
        self.assertEqual(get.call_count, 1)
        self.assertIn('"checked": 1', sink.getvalue())
        self.assertIn('"category": "probe_deadline_exceeded"', sink.getvalue())

    def test_preparation_budget_refuses_mutation_before_ssh_timeout(self):
        from scripts.mpw_dynamic_store_cutover_20261108 import PREFLIGHT_BUDGET_SECONDS, main
        self.assertLessEqual(PREFLIGHT_BUDGET_SECONDS, 40)
        with patch("scripts.mpw_dynamic_store_cutover_20261108.pwd.getpwuid",
                   return_value=SimpleNamespace(pw_name="zomorod2")):
            with patch("scripts.mpw_dynamic_store_cutover_20261108.check_actual_staging_store"):
                with patch("scripts.mpw_dynamic_store_cutover_20261108.public_response",
                           return_value=MARKER + b"x" * 2400):
                    with patch("scripts.mpw_dynamic_store_cutover_20261108.verify_public_buyer_routes",
                               return_value=True):
                        with patch("scripts.mpw_dynamic_store_cutover_20261108.time.monotonic",
                                   side_effect=[100, 141]):
                            with patch("scripts.mpw_dynamic_store_cutover_20261108.perform_cutover") as cutover:
                                with self.assertRaisesRegex(RuntimeError,
                                                            "CUTOVER_PREPARATION_TIME_BUDGET_EXCEEDED"):
                                    main("42425162111")
        cutover.assert_not_called()


if __name__ == "__main__":
    unittest.main()

