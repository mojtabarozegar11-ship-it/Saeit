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
            guard.ORIGIN + "/picm/login/",
            guard.ORIGIN + "/studio.Roham/",
            guard.ORIGIN + "/zahra$$/",
        ):
            with self.subTest(url=url):
                result = guard.ScopedRedirect().redirect_request(
                    self.request, None, 302, "redirect", {}, url
                )
                self.assertEqual(result.full_url, url)

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
