"""No-write tests for actual-domain public presence verification."""
import io
import unittest
from urllib.error import HTTPError, URLError

from scripts.mojprop_world20_public_readonly_probe import (
    NoRedirects, _CASES, scan_one, snapshot,
)


class PublicPage:
    status = 200

    def __init__(self, body=b""):
        self.content = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, length):
        assert length <= 128 * 1024
        return self.content[:length]


class FakeOpener:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request.full_url, request.get_method(), timeout))
        outcome = self.mapping.get(request.full_url)
        if outcome == "missing":
            raise HTTPError(request.full_url, 404, "Not Found", {}, io.BytesIO())
        if outcome == "redirect":
            raise HTTPError(request.full_url, 302, "Redirect", {"Location": "https://example.com"}, io.BytesIO())
        if outcome == "offline":
            raise URLError("unreachable")
        return PublicPage(outcome if isinstance(outcome, bytes) else b"")


class MojPropPublicPresenceTests(unittest.TestCase):
    def test_fixed_preapproved_urls_and_no_post_or_customer_input(self):
        opener = FakeOpener({})
        with self.assertRaises(ValueError):
            scan_one("/buyer/account/", "GET", b"", opener=opener)
        with self.assertRaises(ValueError):
            scan_one("/world/", "POST", b"", opener=opener)
        self.assertEqual(opener.calls, [])
        self.assertEqual(len(_CASES), 6)

    def test_real_diagnostic_distinguishes_live_csrf_from_200_placeholder(self):
        origin = "https://mojplaywin.com"
        opener = FakeOpener({
            origin + "/world/": b"HTML but no form",
            origin + "/moj-prop-intake/?format=html":
                b'<form action="/moj-prop-intake/?format=html"><input name="csrfmiddlewaretoken">',
        })
        result = snapshot(opener=opener)
        self.assertTrue(result["world20_publicly_reachable"])
        self.assertTrue(result["crm_html_form_publicly_reachable"])
        self.assertFalse(result["payment_verified"])
        self.assertFalse(result["proof_of_submission"])
        self.assertFalse(result["buyer_data_accessed"])
        self.assertFalse(result["publication_authorized"])
        self.assertEqual(len(opener.calls), len(_CASES))
        self.assertTrue(all(method == "GET" for _, method, _ in opener.calls))

    def test_404_redirect_or_network_failure_never_becomes_success(self):
        origin = "https://mojplaywin.com"
        opener = FakeOpener({
            origin + "/world/": "redirect",
            origin + "/moj-prop-intake/?format=html": "offline",
            origin + "/moj-prop/": "missing",
        })
        result = snapshot(opener=opener)
        observations = {p["path"]: p for p in result["observations"]}
        self.assertEqual(observations["/world/"]["http_status"], 302)
        self.assertEqual(observations["/moj-prop/"]["http_status"], 404)
        self.assertIsNone(observations["/moj-prop-intake/?format=html"]["http_status"])
        self.assertFalse(result["world20_publicly_reachable"])
        self.assertFalse(result["crm_html_form_publicly_reachable"])

    def test_disabled_redirect_handler_never_reuses_untrusted_url(self):
        guard = NoRedirects()
        self.assertIsNone(guard.redirect_request(
            None, None, 302, "Found", {}, "https://bad.example/"))
