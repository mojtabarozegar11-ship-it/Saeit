"""S-01 guest purchase recovery: no orders or payment in these synthetic tests."""
import unittest
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
# Do not override an existing Django project configuration during CI collection.
if not settings.configured and not os.environ.get("DJANGO_SETTINGS_MODULE"):
    settings.configure(SECRET_KEY="synthetic-s01-only", DEFAULT_CHARSET="utf-8")

from django.http import Http404, HttpResponse
from django.test import RequestFactory
from services.mpw_trx_guest_commerce import COOKIE, patch_public, _install_cookie


def request(*, secure=True, host="mojplaywin.com", cookie=None, authenticated=False, method="GET"):
    # Django's never_cache decorator requires a genuine HttpRequest (META).
    # Keep this test entirely synthetic: no session, database or HTTP request.
    req = RequestFactory().generic(
        method, "/commerce/trx-easy/purchases/", secure=secure,
        HTTP_HOST=host,
    )
    req.user = SimpleNamespace(is_authenticated=authenticated)
    req.COOKIES = {COOKIE: cookie} if cookie is not None else {}
    # Exercise our explicit hostname guard, independent of ALLOWED_HOSTS.
    req.get_host = lambda: host
    return req


class GuestRecoveryLandingTests(unittest.TestCase):
    def setUp(self):
        self.seen_user = None
        def checkout(_request, _product_id):
            return HttpResponse("checkout")
        def purchases(_request):
            self.seen_user = getattr(_request, "user", None)
            return HttpResponse("PRIVATE_INVOICE_SENTINEL")
        self.namespace = {"product_checkout": checkout, "purchases": purchases}
        patch_public(self.namespace)
        self.view = self.namespace["purchases"]

    def test_anonymous_no_cookie_is_safe_page_not_route_404(self):
        result = self.view(request())
        self.assertEqual(result.status_code, 200)
        self.assertIn(b"No active purchase session", result.content)
        self.assertNotIn(b"PRIVATE_INVOICE_SENTINEL", result.content)
        self.assertIn(b"do not send another payment", result.content)
        self.assertEqual(result["X-Robots-Tag"], "noindex, nofollow")
        self.assertIn("no-store", result["Cache-Control"])
        self.assertIn("Cookie", result["Vary"])
        self.assertIn("default-src 'none'", result["Content-Security-Policy"])

    def test_invalid_signed_cookie_does_not_disclose_invoice(self):
        result = self.view(request(cookie="invalid-signed-owner-cookie-123"))
        self.assertEqual(result.status_code, 200)
        self.assertNotIn(b"PRIVATE_INVOICE_SENTINEL", result.content)

    def test_authenticated_owner_retains_existing_purchases_view(self):
        result = self.view(request(authenticated=True))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b"PRIVATE_INVOICE_SENTINEL")

    def test_valid_guest_owner_lookup_preserves_private_invoice_access(self):
        # Simulate a verified guest principal without touching the database.
        owner = SimpleNamespace(pk=777, is_authenticated=True)
        with patch("services.mpw_trx_guest_commerce._read_user", return_value=owner) as lookup:
            result = self.view(request(cookie="synthetic-valid-guest-owner"))
        self.assertGreaterEqual(lookup.call_count, 2)
        self.assertIs(self.seen_user, owner)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b"PRIVATE_INVOICE_SENTINEL")
        self.assertEqual(result["X-Robots-Tag"], "noindex, nofollow")
        self.assertIn("no-store", result["Cache-Control"])

    def test_original_authorization_wrapper_is_not_unwrapped(self):
        # The guest adapter must not discard authorization or other decorators
        # owned by the original purchases route.
        from functools import wraps
        observed = []
        def protect(view):
            @wraps(view)
            def wrapped(req):
                observed.append("checked")
                if not req.user.is_authenticated:
                    return HttpResponse("DENIED", status=403)
                return view(req)
            return wrapped
        namespace = {
            "product_checkout": lambda req, product_id: HttpResponse("checkout"),
            "purchases": protect(lambda req: HttpResponse("PRIVATE_PURCHASE")),
        }
        patch_public(namespace)
        owner = SimpleNamespace(pk=777, is_authenticated=True)
        with patch("services.mpw_trx_guest_commerce._read_user", return_value=owner):
            result = namespace["purchases"](request(cookie="signed-guest"))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b"PRIVATE_PURCHASE")
        self.assertEqual(observed, ["checked"])
        self.assertIn("cookie", result["Vary"].lower())

    def test_plain_http_is_not_accepted(self):
        with self.assertRaises(Http404):
            self.view(request(secure=False))

    def test_other_host_is_not_accepted(self):
        with self.assertRaises(Http404):
            self.view(request(host="evil.example"))

    def test_post_is_not_accepted(self):
        self.assertEqual(self.view(request(method="POST")).status_code, 405)

    def test_signed_owner_cookie_preserves_existing_vary(self):
        response = HttpResponse("invoice")
        response["Vary"] = "Accept-Language"
        result = _install_cookie(response, "synthetic-test-token")
        vary = {part.strip().lower() for part in result["Vary"].split(",")}
        self.assertEqual(vary, {"accept-language", "cookie"})
        self.assertEqual(result.cookies[COOKIE]["httponly"], True)
        self.assertEqual(result.cookies[COOKIE]["secure"], True)
        self.assertIn("no-store", result["Cache-Control"])

    def test_missing_cookie_does_not_clobber_existing_vary(self):
        response = HttpResponse("recovery")
        response["Vary"] = "Accept-Encoding"
        result = _install_cookie(response, None)
        self.assertEqual({part.strip().lower() for part in result["Vary"].split(",")},
                         {"accept-encoding", "cookie"})
        self.assertNotIn(COOKIE, result.cookies)


class PublicSalesFloorTests(unittest.TestCase):
    def test_public_price_floor_blocks_micro_trials_and_invalid_prices(self):
        from decimal import Decimal
        from services.mpw_trx_guest_commerce import _public_price_ok
        for value in (Decimal("0.03"), 0, -4, "3.999", "NaN",
                      "Infinity", "-Infinity", None, True, "not-a-price"):
            with self.subTest(value=value):
                self.assertFalse(_public_price_ok(value))
        for value in (Decimal("4.00"), "4.00", Decimal("6.80"), 7.5):
            with self.subTest(value=value):
                self.assertTrue(_public_price_ok(value))

    def test_public_trx_catalog_filters_micro_trial_and_links_real_checkouts(self):
        from decimal import Decimal
        from types import ModuleType
        from unittest.mock import patch
        import sys
        from services.mpw_trx_guest_commerce import _public_shop_page

        products = [
            SimpleNamespace(pk=72, title="<Chess>", price=Decimal("7.50")),
            SimpleNamespace(pk=225, title="Taniya", price=Decimal("4.00")),
            SimpleNamespace(pk=879, title="Atelier", price=Decimal("6.80")),
            SimpleNamespace(pk=779, title="Micro trial", price=Decimal("0.03")),
        ]

        class ProductQuery:
            def filter(self, **kwargs):
                self.assertion = kwargs
                return self
            def order_by(self, field):
                if field != "pk":
                    raise AssertionError("Unexpected catalog ordering")
                return products

        class Product:
            objects = ProductQuery()

        def module(name, **members):
            obj = ModuleType(name)
            obj.__dict__.update(members)
            return obj

        good_file = SimpleNamespace(
            is_symlink=lambda: False,
            is_file=lambda: True,
            stat=lambda: SimpleNamespace(st_size=100),
        )
        fakes = {
            "core.models": module("core.models", Product=Product),
            "mpw_commerce.buyer_orders": module("mpw_commerce.buyer_orders",
                                                 _eligible=lambda p: True),
            "mpw_commerce.downloads": module("mpw_commerce.downloads",
                                              _private_file=lambda order: good_file),
            "services.mpw_trx_commercial_context": module(
                "services.mpw_trx_commercial_context",
                rights_cleared_for_sale=lambda p: True),
            "services.mpw_trx_commercial_web": module(
                "services.mpw_trx_commercial_web", _configured_receiver=lambda: "receiver"),
            "services.mpw_trx_walletless_core": module(
                "services.mpw_trx_walletless_core",
                PaymentHold=type("PaymentHold", (Exception,), {})),
            "services.mpw_walletless_commercial_intent": module(
                "services.mpw_walletless_commercial_intent",
                _commercial_db=lambda *args: None),
        }
        ns = {"_page": lambda title, body: HttpResponse(title + body)}
        with (patch.dict(sys.modules, fakes),
              patch.object(settings, "MPW_TRX_PUBLIC_PRODUCT_IDS",
                           (72, 225, 879, 779), create=True)):
            result = _public_shop_page(request(), ns)
        self.assertEqual(result.status_code, 200)
        self.assertIn(b"/store/product/72/checkout/", result.content)
        self.assertIn(b"/store/product/225/checkout/", result.content)
        self.assertIn(b"/store/product/879/checkout/", result.content)
        self.assertNotIn(b"/store/product/779/checkout/", result.content)
        self.assertNotIn(b"Micro trial", result.content)
        self.assertNotIn(b"sign in", result.content.lower())
        self.assertIn(b"No account is required", result.content)
        self.assertIn(b"Trust Wallet", result.content)
        self.assertIn(b"&lt;Chess&gt;", result.content)

    def test_public_shop_is_patched_only_when_original_helpers_exist(self):
        from services.mpw_trx_guest_commerce import patch_public
        namespace = {
            "_page": lambda title, body: HttpResponse(title + body),
            "public_shop": lambda req: HttpResponse("OLD_PUBLIC_CATALOG"),
            "product_checkout": lambda req, product_id: HttpResponse("checkout"),
            "purchases": lambda req: HttpResponse("purchases"),
        }
        patch_public(namespace)
        self.assertEqual(namespace["public_shop"](request(method="POST")).status_code, 405)
        with self.assertRaises(Http404):
            namespace["public_shop"](request(secure=False))


class StorefrontRecoveryCopyTests(unittest.TestCase):
    def test_purchase_support_fallback_is_explicit(self):
        from pathlib import Path
        storefront = (Path(__file__).resolve().parents[1] / "core" / "templates" /
                      "mojplaywin" / "store.html").read_text("utf8")
        self.assertIn('href="/commerce/trx-easy/purchases/"', storefront)
        self.assertIn('href="/support/"', storefront)
        self.assertIn("do not pay a second time", storefront)
        self.assertIn("Never share your wallet recovery phrase", storefront)

    def test_all_three_listings_offer_direct_separate_checkout(self):
        from pathlib import Path
        storefront = (Path(__file__).resolve().parents[1] / "core" / "templates" /
                      "mojplaywin" / "store.html").read_text("utf8")
        for product_id in (72, 225, 879):
            with self.subTest(product_id=product_id):
                self.assertIn('href="/store/product/' + str(product_id) + '/checkout/"',
                              storefront)
        self.assertIn('href="/store/product/879/"', storefront)
        self.assertNotIn('href="/store/product/779/checkout/"', storefront)


class ReleasePurchasesSmokeContractTests(unittest.TestCase):
    def test_release_checks_exact_anonymous_purchases_route(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        controller = (root / "scripts" / "mpw_guest_checkout_live_release.py").read_text("utf8")
        workflow = (root / ".github" / "workflows" /
                    "mpw-guest-checkout-live-release.yml").read_text("utf8")
        route = "/commerce/trx-easy/purchases/"
        self.assertIn("recovery_route = '" + route + "'", controller)
        self.assertIn("ANONYMOUS_PURCHASES_HTTP", controller)
        self.assertIn("PURCHASES_NOINDEX_MISSING", controller)
        self.assertIn("PURCHASES_NOSTORE_MISSING", controller)
        self.assertIn("'" + route + "'", workflow)
        self.assertIn("GUEST_RECOVERY_NOINDEX_MISSING", workflow)
        self.assertIn("GUEST_RECOVERY_NOSTORE_MISSING", workflow)
        self.assertIn("PUBLIC_TRX_MICRO_TRIAL_EXPOSED", workflow)
        self.assertIn("PUBLIC_TRX_CATALOG_MISSING_REAL_SKU", workflow)


class ReleaseInterlockTests(unittest.TestCase):
    def test_release_is_manual_and_fail_closed_until_independent_proof(self):
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" /
                    "mpw-guest-checkout-live-release.yml").read_text("utf8")
        self.assertIn("  workflow_dispatch:", workflow)
        self.assertNotIn("  push:", workflow)
        self.assertIn("if: ${{ false }}", workflow)


class ReleaseRollbackSandboxTests(unittest.TestCase):
    """Exercise an actual publish/rollback cycle on throwaway files only."""

    def _run_fixture(self, tamper=False):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from scripts import mpw_guest_checkout_live_release as release

        original_pages = (
            b"def product_checkout(request, product_id):\\n    return None\\n"
            b"def purchases(request):\\n    return None\\n"
        ).replace(b"\\n", b"\n")
        original_web = (
            b"def _views():\\n    return None\\n"
            b"COMMERCIAL_URLPATTERNS=()\\n"
        ).replace(b"\\n", b"\n")
        source = (
            b"def patch_public(namespace):\\n    pass\\n"
            b"def patch_commercial(namespace):\\n    pass\\n"
        ).replace(b"\\n", b"\n")
        with tempfile.TemporaryDirectory(prefix="mpw-guest-rollback-ci-") as temp:
            root = Path(temp)
            paths = {
                "pages": root / "pages.py",
                "web": root / "web.py",
                "guest": root / "guest.py",
            }
            paths["pages"].write_bytes(original_pages)
            paths["web"].write_bytes(original_web)
            candidate = root / "candidate.py"
            candidate.write_bytes(source)
            run_id = "41270000000"
            with (patch.object(release, "TARGETS", paths),
                  patch.object(release, "BACKUPS", root / "backups"),
                  patch.object(release, "guard", lambda: None),
                  patch.object(release, "restart", lambda: None)):
                release.publish(run_id, str(candidate))
                self.assertEqual(paths["guest"].read_bytes(), source)
                self.assertNotEqual(paths["pages"].read_bytes(), original_pages)
                if tamper:
                    paths["guest"].write_bytes(source + b"# unexpected drift\\n")
                    before = {k: p.read_bytes() for k, p in paths.items()}
                    with self.assertRaisesRegex(RuntimeError, "ROLLBACK_DRIFT:guest"):
                        release.rollback(run_id)
                    self.assertEqual(before, {k: p.read_bytes() for k, p in paths.items()})
                else:
                    release.rollback(run_id)
                    self.assertFalse(paths["guest"].exists())
                    self.assertEqual(paths["pages"].read_bytes(), original_pages)
                    self.assertEqual(paths["web"].read_bytes(), original_web)

    def test_synthetic_publish_rollback_restores_exact_prior_modules(self):
        self._run_fixture()

    def test_synthetic_rollback_refuses_changed_adapter(self):
        self._run_fixture(tamper=True)


if __name__ == "__main__":
    unittest.main()
