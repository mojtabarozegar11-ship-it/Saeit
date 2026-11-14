"""No-network tests for public company GET audit, privacy and fail-closed semantics."""
import io
import json
import socket
import unittest
import urllib.error
from contextlib import redirect_stdout
from unittest.mock import patch

from deploy.company_public_intake_probe_readonly import (
    MAX_BYTES, URLS, _safe_probe, main,
)


class HtmlResponse:
    def __init__(self, html, *, status=200, content_type="text/html"):
        self.status = status
        self.contents = html
        self.headers = type("Headers", (), {
            "get_content_type": lambda self: content_type
        })()

    def read(self, size=-1):
        return self.contents[:size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Opener:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if self.error:
            raise self.error
        return self.response


class PublicProbeTests(unittest.TestCase):
    def test_public_form_observation_is_metadata_only(self):
        secret = "PRIVATE_PRE_FILLED_CUSTOMER_EMAIL_XYZZY"
        opener = Opener(HtmlResponse(
            ("<html><form method='post'><input name='email'>"
             "<input name='consent' value='on'>"
             + secret + "</form></html>").encode()
        ))
        result = _safe_probe("canonical_php", URLS[0][1], opener)
        self.assertEqual(result["observation"], "public_html_observed")
        self.assertTrue(result["form_post_seen"])
        self.assertTrue(result["html_form_seen"])
        self.assertTrue(result["email_field_seen"])
        self.assertTrue(result["consent_field_seen"])
        self.assertNotIn(secret, json.dumps(result))
        self.assertIsNone(result["payment_received"])

    def test_only_public_get_with_no_cookies_or_credentials(self):
        opener = Opener(HtmlResponse(b"<html></html>"))
        _safe_probe("company_page", URLS[1][1], opener)
        req, timeout = opener.requests[0]
        self.assertEqual(req.get_method(), "GET")
        self.assertNotIn("cookie", str(req.headers).lower())
        self.assertNotIn("authorization", str(req.headers).lower())
        self.assertLessEqual(timeout, 8)

    def test_dns_fail_has_no_false_health(self):
        opener = Opener(error=urllib.error.URLError(
            socket.gaierror("private dns details should never be printed")
        ))
        r = _safe_probe("canonical_php", URLS[0][1], opener)
        self.assertEqual(r["observation"], "unknown")
        self.assertEqual(r["reason_code"], "network_or_dns")
        self.assertNotIn("private dns", str(r))
        self.assertIsNone(r["php_database_connected"])

    def test_public_404_proves_only_http_response(self):
        err = urllib.error.HTTPError(URLS[0][1], 404, "Not Found", {}, None)
        r = _safe_probe("canonical_php", URLS[0][1], Opener(error=err))
        self.assertEqual(r["observation"], "http_response_not_success")
        self.assertEqual(r["http_status"], 404)
        self.assertIsNone(r["customer_intake_written"])

    def test_200_without_html_does_not_prove_form(self):
        r = _safe_probe("canonical_php", URLS[0][1],
                        Opener(HtmlResponse(b"ok", content_type="text/plain")))
        self.assertEqual(r["observation"], "non_html_or_non_200_response")
        self.assertIsNone(r["html_form_seen"])

    def test_200_html_without_form_does_not_prove_customer_intake(self):
        r = _safe_probe("canonical_php", URLS[0][1],
                        Opener(HtmlResponse(b"<html>no form here</html>")))
        self.assertFalse(r["html_form_seen"])
        self.assertIsNone(r["customer_intake_written"])

    def test_limit_is_enforced_and_disclosed(self):
        r = _safe_probe("canonical_php", URLS[0][1],
                        Opener(HtmlResponse(b"x" * (MAX_BYTES + 600))))
        self.assertTrue(r["body_truncated"])
        self.assertFalse(r["html_form_seen"])

    def test_program_output_never_asserts_settlement(self):
        opener = Opener(HtmlResponse(b"<html></html>"))
        with patch("deploy.company_public_intake_probe_readonly.urllib.request.build_opener",
                   return_value=opener):
            buf = io.StringIO()
            with redirect_stdout(buf):
                outcome = main()
        self.assertEqual(outcome, 0)
        raw = buf.getvalue().split("ZM_PUBLIC_INTAKE_READONLY=", 1)[1]
        result = json.loads(raw)
        self.assertFalse(result["backend_storage_verified"])
        self.assertFalse(result["buyer_order_verified"])
        self.assertFalse(result["external_payment_verified"])
        self.assertEqual(len(result["results"]), 3)


if __name__ == "__main__":
    unittest.main()
