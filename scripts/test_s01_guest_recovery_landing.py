"""S-01 guest purchase recovery: no orders or payment in these synthetic tests."""
import unittest
import os
from types import SimpleNamespace

from django.conf import settings
# Do not override an existing Django project configuration during CI collection.
if not settings.configured and not os.environ.get("DJANGO_SETTINGS_MODULE"):
    settings.configure(SECRET_KEY="synthetic-s01-only", DEFAULT_CHARSET="utf-8")

from django.http import Http404, HttpResponse
from django.test import RequestFactory
from services.mpw_trx_guest_commerce import COOKIE, patch_public


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
        def checkout(_request, _product_id):
            return HttpResponse("checkout")
        def purchases(_request):
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
        self.assertIn("default-src 'none'", result["Content-Security-Policy"])

    def test_invalid_signed_cookie_does_not_disclose_invoice(self):
        result = self.view(request(cookie="invalid-signed-owner-cookie-123"))
        self.assertEqual(result.status_code, 200)
        self.assertNotIn(b"PRIVATE_INVOICE_SENTINEL", result.content)

    def test_authenticated_owner_retains_existing_purchases_view(self):
        result = self.view(request(authenticated=True))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b"PRIVATE_INVOICE_SENTINEL")

    def test_plain_http_is_not_accepted(self):
        with self.assertRaises(Http404):
            self.view(request(secure=False))

    def test_other_host_is_not_accepted(self):
        with self.assertRaises(Http404):
            self.view(request(host="evil.example"))

    def test_post_is_not_accepted(self):
        self.assertEqual(self.view(request(method="POST")).status_code, 405)


if __name__ == "__main__":
    unittest.main()
