"""Offline tests: no network calls, no production access or writes."""
import json
import unittest
import urllib.request
from scripts.dual_site_public_recovery_canary_20261023 import (
    MANIFEST_PATH, RestrictedRedirect, SITES, examine, probe
)


class FakeResponse:
    status = 200

    def __init__(self, body: bytes, url: str):
        self.body, self.url = body, url

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, n):
        assert n <= 550_000
        return self.body

    def geturl(self):
        return self.url


class FakeOpener:
    def open(self, request, timeout):
        assert request.get_method() == "GET"
        assert timeout <= 14
        assert "Cookie" not in request.headers
        assert "Authorization" not in request.headers
        body = b"<html><title>Moj Play Win</title>" + b"x" * 110 + b"</html>"
        return FakeResponse(body, request.full_url)


class RecoveryCanaryTests(unittest.TestCase):
    def test_readonly_public_GET_and_content_check(self):
        record = probe("mojplaywin.com", "/", opener_factory=lambda h: FakeOpener())
        self.assertEqual(record["http_status"], 200)
        self.assertEqual(record["outcome"], "pass")
        self.assertNotIn("Moj Play Win</title>", str(record))

    def test_http200_directory_listing_is_not_health(self):
        page = b"<html><title>Index of /</title>" + b"x" * 100
        self.assertEqual(
            examine("mojplaywin.com", "/", 200, page, "https://mojplaywin.com/"),
            "directory_listing_exposed",
        )

    def test_different_site_or_503_fails(self):
        page = ("<html>" + "زمرد" * 100 + "</html>").encode()
        self.assertEqual(examine("mojplaywin.com", "/", 200, page, "https://mojplaywin.com/"), "wrong_page_identity")
        self.assertEqual(examine("zomorodmelal.ir", "/", 503, page, "https://zomorodmelal.ir/"), "http_503")

    def test_manifest_release_id_and_count_required(self):
        valid = {
            "release_id": "MPW-FIELDGUIDES-20261023-01",
            "guide_count": 50, "stage_count": 150,
            "files_sha256": {str(i): "a" * 64 for i in range(53)},
        }
        url = "https://mojplaywin.com" + MANIFEST_PATH
        data = json.dumps(valid).encode()
        self.assertEqual(examine("mojplaywin.com", MANIFEST_PATH, 200, data, url), "")
        valid["guide_count"] = 0
        self.assertEqual(examine("mojplaywin.com", MANIFEST_PATH, 200, json.dumps(valid).encode(), url), "release_manifest_mismatch")

    def test_redirect_cannot_escape_site_or_allowlist(self):
        request = urllib.request.Request("https://mojplaywin.com/")
        redirect = RestrictedRedirect("mojplaywin.com", "/")
        for destination in ("http://mojplaywin.com/", "https://evil.example/",
                            "https://mojplaywin.com/admin/", "https://zomorodmelal.ir/",
                            "https://mojplaywin.com/?token=1"):
            with self.subTest(destination=destination):
                with self.assertRaises(ValueError):
                    redirect.redirect_request(request, None, 302, "found", {}, destination)

    def test_legacy_crown_game_redirect_is_the_only_permitted_new_path(self):
        handler = RestrictedRedirect("mojplaywin.com", "/games/corwn-defender/")
        request = urllib.request.Request("https://mojplaywin.com/games/corwn-defender/")
        canonical = "https://mojplaywin.com/games/crown-defender/"
        redirected = handler.redirect_request(request, None, 301, "moved", {}, canonical)
        self.assertEqual(redirected.full_url, canonical)
        original_html = b"<html><title>Crown Defender</title>" + b"x" * 100
        self.assertEqual(examine("mojplaywin.com", "/games/corwn-defender/",
                                 200, original_html, canonical), "")
        with self.assertRaises(ValueError):
            handler.redirect_request(request, None, 302, "moved", {},
                                     "https://mojplaywin.com/store/")

    def test_store_canonical_passthrough_is_narrowly_allowlisted(self):
        request = urllib.request.Request("https://mojplaywin.com/store/")
        handler = RestrictedRedirect("mojplaywin.com", "/store/")
        canonical = "https://mojplaywin.com/store/?__mpw_canon_passthru=1"
        redirected = handler.redirect_request(request, None, 302, "canonical", {}, canonical)
        self.assertEqual(redirected.full_url, canonical)
        page = b"<html><title>MojPlayWin Digital Store</title>" + b"x" * 110
        self.assertEqual(examine("mojplaywin.com", "/store/", 200, page, canonical), "")
        for bad in ("https://mojplaywin.com/store/?token=1",
                    "https://mojplaywin.com/store/?__mpw_canon_passthru=0",
                    "https://mojplaywin.com/store/?__mpw_canon_passthru=1&token=1",
                    "https://mojplaywin.com/store/?__mpw_canon_passthru=1#fragment",
                    "https://evil.example/store/?__mpw_canon_passthru=1"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    RestrictedRedirect("mojplaywin.com", "/store/").redirect_request(
                        request, None, 302, "canonical", {}, bad)
                self.assertEqual(examine("mojplaywin.com", "/store/", 200, page, bad),
                                 "wrong_origin_or_route")
        with self.assertRaises(ValueError):
            RestrictedRedirect("mojplaywin.com", "/products/").redirect_request(
                urllib.request.Request("https://mojplaywin.com/products/"),
                None, 302, "canonical", {}, "https://mojplaywin.com/products/?__mpw_canon_passthru=1")

    def test_unapproved_paths_refuse_network(self):
        for host, path in (("mojplaywin.com", "/store/checkout/"),
                           ("zomorodmelal.ir", "/admin/"), ("attacker.example", "/")):
            with self.subTest(host=host, path=path):
                with self.assertRaises(ValueError):
                    probe(host, path, opener_factory=lambda handler: self.fail("network used"))

    def test_allowlist_contains_two_sites_and_no_sensitive_routes(self):
        self.assertEqual(set(SITES), {"zomorodmelal.ir", "mojplaywin.com"})
        self.assertGreaterEqual(sum(len(paths) for paths in SITES.values()), 20)
        self.assertNotIn("/picm/login/", SITES["mojplaywin.com"])
        self.assertNotIn("/admin/", SITES["zomorodmelal.ir"])


if __name__ == "__main__":
    unittest.main()
