"""Mock-only checks: never send real network requests or mutate production."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "zomorod_inner_attestation_reliability",
    ROOT / "scripts" / "zomorod_inner_live_css_attestation_20261114.py",
)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class FakeResponse:
    def __init__(self, html, status=200):
        self.raw = html.encode("utf8")
        self.status = status
        self.headers = {"Content-Type": "text/html; charset=UTF-8"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.raw[:size]


class LiveAttestationMockOnly(unittest.TestCase):
    def test_no_homepage_and_three_unique_inner_routes(self):
        routes = [p for p, _ in MOD.TARGETS]
        self.assertEqual(len(routes), 3)
        self.assertEqual(len(set(routes)), 3)
        self.assertNotIn("/", routes)

    def test_get_only_no_auth_or_post(self):
        with patch.object(MOD.urllib.request, "urlopen",
                          return_value=FakeResponse('<meta name="theme-color" content="#252b19">')) as fetch:
            result = MOD.inspect_path("/auctions/", "not-an-actual-marker")
        req = fetch.call_args.args[0]
        self.assertEqual(req.get_method(), "GET")
        self.assertEqual(req.full_url, MOD.BASE + "/auctions/")
        self.assertFalse(req.has_header("Authorization"))
        self.assertEqual(result["production_writes"], 0)
        self.assertFalse(result["deployment_claim"])
        self.assertFalse(result["host_file_identity_proven"])

    def test_marker_visible_is_not_host_file_attestation(self):
        m = "zm-auctions-inner-olive-20261114"
        with patch.object(MOD.urllib.request, "urlopen",
                          return_value=FakeResponse('<meta name="theme-color" content="#252b19">' + m)):
            result = MOD.inspect_path("/auctions/", m)
        self.assertEqual(result["live_css_status"], "MARKER_VISIBLE")
        self.assertTrue(result["marker_live"])
        self.assertFalse(result["host_file_identity_proven"])
        self.assertEqual(result["attempts"][0]["http_status"], 200)

    def test_missing_marker_is_not_claimed_as_a_release(self):
        with patch.object(MOD.urllib.request, "urlopen",
                          return_value=FakeResponse('<meta name="theme-color" content="#103a2b">')):
            result = MOD.inspect_path("/auctions/", "not-present")
        self.assertEqual(result["live_css_status"], "NOT_PROVEN_FROM_PUBLIC_HTML")
        self.assertFalse(result["marker_live"])
        self.assertEqual(result["theme_color"], "#103a2b")

    def test_timeout_then_success_preserves_first_failure(self):
        responses = [urllib.error.URLError("timed out"),
                     FakeResponse('<meta name="theme-color" content="#252b19">')]
        with patch.object(MOD.urllib.request, "urlopen", side_effect=responses) as fetch:
            with patch.object(MOD.time, "sleep") as delay:
                result = MOD.inspect_path("/ghanadi/", "missing")
        self.assertEqual(fetch.call_count, 2)
        delay.assert_called_once()
        self.assertEqual(result["attempts"][0]["kind"], "NETWORK_ERROR")
        self.assertTrue(result["attempts"][1]["ok"])
        self.assertEqual(result["live_css_status"], "NOT_PROVEN_FROM_PUBLIC_HTML")

    def test_two_timeouts_remain_unknown(self):
        with patch.object(MOD.urllib.request, "urlopen",
                          side_effect=urllib.error.URLError("timed out")) as fetch:
            with patch.object(MOD.time, "sleep"):
                result = MOD.inspect_path("/ghanadi/", "missing")
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(result["live_css_status"], "UNKNOWN_FETCH_FAILED")
        self.assertEqual(len(result["attempts"]), 2)
        self.assertFalse(result["host_file_identity_proven"])

    def test_http_404_does_not_retry(self):
        err = urllib.error.HTTPError(MOD.BASE + "/auctions/", 404, "Not Found", {}, None)
        with patch.object(MOD.urllib.request, "urlopen", side_effect=err) as fetch:
            result = MOD.inspect_path("/auctions/", "marker")
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(result["http_status"], 404)
        self.assertEqual(result["live_css_status"], "HTTP_ERROR_NOT_VERIFIED")

    def test_http_503_retry_success(self):
        err = urllib.error.HTTPError(MOD.BASE + "/auctions/", 503, "Busy", {}, None)
        with patch.object(MOD.urllib.request, "urlopen",
                          side_effect=[err, FakeResponse("<html>ok</html>")]) as fetch:
            with patch.object(MOD.time, "sleep"):
                result = MOD.inspect_path("/auctions/", "marker")
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(len(result["attempts"]), 2)
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["live_css_status"], "NOT_PROVEN_FROM_PUBLIC_HTML")

    def test_homepage_rejected_before_any_get(self):
        with patch.object(MOD.urllib.request, "urlopen") as fetch:
            with self.assertRaises(AssertionError):
                MOD.inspect_path("/", "marker")
            fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
