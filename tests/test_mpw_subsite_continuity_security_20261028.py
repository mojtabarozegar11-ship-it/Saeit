"""Offline regression for the production read-only MojPlayWin route guard.

No HTTP calls, credentials, payment intents, orders or server writes.
"""
import unittest
import urllib.request
from unittest.mock import patch
from xml.etree import ElementTree as ET

from scripts import mpw_subsite_continuity_guard_20261026 as guard


class _Response:
    status = 200

    def __init__(self, url):
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        return self.url

    def read(self, limit):
        assert limit <= 950001
        return b"<html><body>safe</body></html>"


class ContinuityGuardSecurityTests(unittest.TestCase):
    def setUp(self):
        self.request = urllib.request.Request(guard.ORIGIN + "/saman/")

    def test_redirects_never_leave_public_scope(self):
        rejected = (
            "http://mojplaywin.com/saman/",
            "https://evil.example/saman/",
            "https://www.mojplaywin.com/saman/",
            "https://mojplaywin.com:8443/saman/",
            "https://mojplaywin.com@evil.example/saman/",
            "https://mojplaywin.com/admin/",
            guard.ORIGIN + "/picm/login/",
            guard.ORIGIN + "/picm/",
            "https://mojplaywin.com/commerce/trx-easy/purchases/",
            "https://mojplaywin.com/%61dmin/",
            "https://mojplaywin.com/saman/#fragment",
        )
        for url in rejected:
            with self.subTest(url=url):
                with self.assertRaises(guard.UnsafeRedirect):
                    guard.ScopedRedirect().redirect_request(
                        self.request, None, 302, "redirect", {}, url
                    )

    def test_login_redirect_and_known_child_are_allowed(self):
        for url in (
            guard.ORIGIN + "/accounts/login/?next=%2Fstore%2Fproduct%2F72%2Fcheckout%2F",
            guard.ORIGIN + "/studio.Roham/",
            guard.ORIGIN + "/zahra$$/",
        ):
            with self.subTest(url=url):
                result = guard.ScopedRedirect().redirect_request(
                    self.request, None, 302, "redirect", {}, url
                )
                self.assertEqual(result.full_url, url)

    def test_redirect_query_cannot_change_login_return_or_child_route(self):
        rejected = (
            guard.ORIGIN + "/accounts/login/",
            guard.ORIGIN + "/accounts/login/?next=https%3A%2F%2Fevil.example%2F",
            guard.ORIGIN + "/accounts/login/?next=%2Fstore%2Fproduct%2F999%2Fcheckout%2F",
            guard.ORIGIN + "/accounts/login/?next=%2Fstore%2Fproduct%2F72%2Fcheckout%2F&next=%2Fadmin%2F",
            guard.ORIGIN + "/saman/?next=%2Fadmin%2F",
        )
        for url in rejected:
            with self.subTest(url=url):
                with self.assertRaises(guard.UnsafeRedirect):
                    guard.ScopedRedirect().redirect_request(
                        self.request, None, 302, "redirect", {}, url
                    )

    def test_direct_get_cannot_leave_public_scope(self):
        for url in (
            "https://evil.example/saman/",
            "http://mojplaywin.com/saman/",
            guard.ORIGIN + "/admin/",
            guard.ORIGIN + "/saman/?unexpected=1",
        ):
            with self.subTest(url=url):
                with patch.object(guard.urllib.request, "build_opener") as opener:
                    with self.assertRaises(guard.UnsafeRedirect):
                        guard.get(url, attempts=1)
                    opener.assert_not_called()

    def test_checkout_login_return_path_is_exact_and_product_specific(self):
        for pk in guard.PROTECTED_PRODUCT_IDS:
            expected = f"/store/product/{pk}/checkout/"
            correct = guard.Check(guard.ORIGIN + expected,
                guard.ORIGIN + "/accounts/login/?next=" +
                guard.urllib.parse.quote(expected, safe=""), 200, 0.01)
            with patch.object(guard, "get", return_value=(correct, b"")):
                self.assertEqual(guard.check_authentication_gate(pk), correct)
            for wrong_query in ("", "?next=%2Fstore%2Fproduct%2F999%2Fcheckout%2F",
                                "?next=https%3A%2F%2Fevil.example%2F"):
                wrong = guard.Check(guard.ORIGIN + expected,
                    guard.ORIGIN + "/accounts/login/" + wrong_query, 200, 0.01)
                with patch.object(guard, "get", return_value=(wrong, b"")):
                    with self.assertRaisesRegex(RuntimeError, "return path"):
                        guard.check_authentication_gate(pk)

    def _guest_html(self, pk, *, email=True, csrf=True, action=None,
                    method="post", marker=True):
        action = action or f"/commerce/trx-easy/start/{pk}/"
        email_part = (
            '<input type="email" name="email" maxlength="254" required>'
            if email else '<input type="text" name="email">'
        )
        csrf_part = (
            '<input type="hidden" name="csrfmiddlewaretoken" value="test-only">'
            if csrf else ''
        )
        gateway = 'data-gateway="trx-public-v1"' if marker else ''
        return (
            '<!doctype html><html><head><title>Checkout</title></head>'
            '<body><main><section ' + gateway + '><h1>Secure TRX</h1>'
            '<form method="' + method + '" action="' + action + '">'
            + email_part + csrf_part + '<button type="submit">Invoice</button>'
            '</form></section></main>' + (' ' * 600) + '</body></html>'
        ).encode("utf-8")

    def test_exact_legacy_mobile_guest_form_is_accepted_without_login(self):
        for pk in guard.PROTECTED_PRODUCT_IDS:
            path = f"/store/product/{pk}/checkout/"
            check = guard.Check(guard.ORIGIN + path, guard.ORIGIN + path,
                                200, 0.01)
            with self.subTest(pk=pk), patch.object(
                guard, "get", return_value=(check, self._guest_html(pk)),
            ):
                self.assertEqual(guard.check_authentication_gate(pk), check)

    def test_guest_checkout_never_passes_without_email_and_csrf(self):
        for variation in (
            {"email": False},
            {"csrf": False},
            {"method": "get"},
            {"marker": False},
            {"action": "/commerce/trx-easy/start/999/"},
            {"action": "https://evil.example/commerce/trx-easy/start/72/"},
        ):
            with self.subTest(variation=variation):
                check = guard.Check(
                    guard.ORIGIN + "/store/product/72/checkout/",
                    guard.ORIGIN + "/store/product/72/checkout/",
                    200, 0.01)
                with patch.object(
                    guard, "get", return_value=(check, self._guest_html(72, **variation)),
                ):
                    with self.assertRaisesRegex(RuntimeError,
                                                "lacks exact email, CSRF"):
                        guard.check_authentication_gate(72)

    def test_guest_wrong_location_or_query_is_denied(self):
        path = "/store/product/72/checkout/"
        for effective in (
            guard.ORIGIN + "/store/",
            guard.ORIGIN + path + "?token=unsafe",
            "https://evil.example" + path,
        ):
            with self.subTest(effective=effective):
                check = guard.Check(guard.ORIGIN + path, effective, 200, 0.01)
                with patch.object(guard, "get", return_value=(check, self._guest_html(72))):
                    with self.assertRaises(RuntimeError):
                        guard.check_authentication_gate(72)

    def test_guest_only_http200_or_empty_html_is_never_auth_or_sale_proof(self):
        path = "/store/product/72/checkout/"
        check = guard.Check(guard.ORIGIN + path, guard.ORIGIN + path, 200, 0.01)
        for body in (b"", b"<html><body>OK</body></html>", b"x" * 650):
            with self.subTest(length=len(body)), patch.object(
                guard, "get", return_value=(check, body),
            ):
                with self.assertRaises(RuntimeError):
                    guard.check_authentication_gate(72)

    def test_rejected_redirect_names_only_approved_source_route(self):
        # Live guard had only a generic failure, so operators could not tell
        # which protected site redirected. Never reveal redirect Location.
        source = guard.ORIGIN + "/zahra$/"
        seen = []

        class _Refused:
            def open(self, request, timeout):
                seen.append(request.full_url)
                raise guard.UnsafeRedirect(
                    "untrusted Location: https://outside.example/token=PRIVATE"
                )

        with patch.object(guard.urllib.request, "build_opener",
                          return_value=_Refused()):
            with self.assertRaises(guard.UnsafeRedirect) as failure:
                guard.get(source, attempts=3)
        text = str(failure.exception)
        self.assertIn("/zahra$/", text)
        self.assertNotIn("outside.example", text)
        self.assertNotIn("PRIVATE", text)
        self.assertEqual(seen, [source])

    def test_denied_unknown_initial_url_is_never_sent_or_logged(self):
        with patch.object(guard.urllib.request, "build_opener") as opener:
            with self.assertRaises(guard.UnsafeRedirect):
                guard.get("https://outside.example/secret", attempts=1)
            opener.assert_not_called()

    def test_redirect_hops_are_bounded(self):
        handler = guard.ScopedRedirect()
        for _ in range(3):
            handler.redirect_request(
                self.request, None, 302, "redirect", {},
                guard.ORIGIN + "/saman/"
            )
        with self.assertRaisesRegex(guard.UnsafeRedirect, "Too many"):
            handler.redirect_request(
                self.request, None, 302, "redirect", {},
                guard.ORIGIN + "/saman/"
            )

    def test_public_child_coverage_has_no_duplicate_paths(self):
        self.assertTrue({"/studio.Roham/", "/zahra$$/"}.issubset(
            guard.PROTECTED_CHILDREN
        ))
        self.assertTrue(set(guard.PROTECTED_CHILDREN).issubset(
            guard.REQUIRED_PATHS
        ))
        self.assertEqual(len(guard.REQUIRED_PATHS), len(set(guard.REQUIRED_PATHS)))
        self.assertEqual(len(guard.PERSONAL_PATHS), 11)
        self.assertEqual(len(guard.PROTECTED_CHILDREN), 5)
        self.assertNotIn("/picm/", guard.REQUIRED_PATHS)
        self.assertNotIn("/picm/login/", guard.REDIRECT_PATHS)

    def test_get_uses_scoped_opener_and_anonymous_get(self):
        calls = []

        class _Opener:
            def open(self, request, timeout):
                calls.append((request, timeout))
                return _Response(request.full_url)

        def make_opener(handler):
            self.assertIsInstance(handler, guard.ScopedRedirect)
            return _Opener()

        with patch.object(guard.urllib.request, "build_opener", side_effect=make_opener):
            result, body = guard.get(guard.ORIGIN + "/saman/", attempts=1)
        self.assertEqual(result.status, 200)
        self.assertIn(b"safe", body)
        self.assertEqual(len(calls), 1)
        request, timeout = calls[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertLessEqual(timeout, 22)
        self.assertNotIn("Cookie", request.headers)
        self.assertNotIn("Authorization", request.headers)

    def test_sitemap_rejects_malformed_same_origin_path(self):
        paths = [guard.ORIGIN + f"/safe-{n}/" for n in range(70)]
        paths += [guard.ORIGIN + path for path in guard.SITEMAP_URLS]
        paths.append(guard.ORIGIN + "//evil.example/")
        xml = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
               + "".join(f"<url><loc>{url}</loc></url>" for url in paths)
               + "</urlset>").encode()
        observed = guard.Check(guard.ORIGIN + "/sitemap.xml",
                               guard.ORIGIN + "/sitemap.xml", 200, 0.01)
        with patch.object(guard, "get", return_value=(observed, xml)):
            with self.assertRaisesRegex(RuntimeError, "Malformed or unsafe"):
                guard.check_sitemap()

    def test_sitemap_accepts_valid_known_urls(self):
        paths = [guard.ORIGIN + f"/safe-{n}/" for n in range(70)]
        paths += [guard.ORIGIN + path for path in guard.SITEMAP_URLS]
        xml = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
               + "".join(f"<url><loc>{url}</loc></url>" for url in paths)
               + "</urlset>").encode()
        observed = guard.Check(guard.ORIGIN + "/sitemap.xml",
                               guard.ORIGIN + "/sitemap.xml", 200, 0.01)
        with patch.object(guard, "get", return_value=(observed, xml)):
            _, count = guard.check_sitemap()
        self.assertEqual(count, len(paths))


if __name__ == "__main__":
    unittest.main()
