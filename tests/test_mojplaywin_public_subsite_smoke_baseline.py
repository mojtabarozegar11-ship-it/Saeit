"""Unit tests never reach a network or private MojPlayWin paths."""
import unittest
import urllib.request

from scripts.mojplaywin_public_subsite_smoke_baseline import (
    BODY_LIMIT, PUBLIC_PATHS, StrictRedirect, UnsafeRedirect, probe, report
)


class FakeResponse:
    status = 200
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, n):
        assert n == BODY_LIMIT
        return b"<html>public-only</html>"


class FakeOpener:
    def open(self, request, timeout):
        assert request.get_method() == "GET"
        assert timeout <= 12
        assert request.full_url.startswith("https://mojplaywin.com/")
        assert "Cookie" not in request.headers
        assert "Authorization" not in request.headers
        return FakeResponse()


class PublicSmokeBaselineTests(unittest.TestCase):
    def test_get_is_bounded_and_anonymous(self):
        result = probe("/saman/", opener_factory=lambda handler: FakeOpener())
        self.assertEqual(result["status"], 200)
        self.assertIsNone(result["error_class"])
        self.assertEqual(result["response_bytes_sampled"], len(b"<html>public-only</html>"))
        self.assertNotIn("public-only", str(result))

    def test_redirect_refuses_external_or_insecure(self):
        for url in ("http://mojplaywin.com/picm/", "https://example.com/",
                    "https://evil.mojplaywin.com/"):
            with self.subTest(url=url):
                with self.assertRaises(UnsafeRedirect):
                    StrictRedirect().redirect_request(
                        urllib.request.Request("https://mojplaywin.com/"),
                        None, 302, "redirect", {}, url
                    )

    def test_nonallowlisted_routes_rejected_without_network(self):
        for path in ("/admin/", "/picm/admin/", "/private/", "/health/",
                     "/store/checkout/", "/not-listed-child/"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    probe(path, opener_factory=lambda handler: self.fail("network used"))

    def test_observations_do_not_certify_100_percent_safety(self):
        data = report(lambda p: {"path": p, "status": 200})
        self.assertEqual(len(data["responses"]), len(PUBLIC_PATHS))
        self.assertFalse(data["unknown_subsites_inventoried"])
        self.assertFalse(data["all_protected_sites_verified"])
        self.assertFalse(data["release_permitted"])


if __name__ == "__main__":
    unittest.main()
