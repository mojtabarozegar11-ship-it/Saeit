"""No-network tests for public company GET audit, privacy and fail-closed semantics."""
import io
import json
import socket
import unittest
import urllib.error
from contextlib import redirect_stdout
from unittest.mock import patch

from deploy.company_public_intake_probe_readonly import (
    MAX_BYTES, MAX_FORMS, URLS, _public_structure, _safe_probe, main,
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


    def test_multiple_forms_cannot_cross_contaminate_consent_or_email(self):
        sample = """<form method="post" action="/unrelated"><input name="consent">
            <button>Submit</button></form>
            <form method="get"><input name="email"></form>"""
        output = _public_structure(sample, URLS[0][1])
        self.assertEqual(output["form_count_capped"], 2)
        self.assertEqual(output["candidate_post_email_form_count_capped"], 0)
        self.assertIsNone(output["consent_named_in_candidate"])

    def test_post_email_and_consent_on_same_form_are_detected(self):
        sample = """<form method="POST" action="/ask-master/submit.php">
          <input type="email" name="sender_email">
          <input type="checkbox" name="consent" required>
          <input type="hidden" name="csrf_token" value="SUPER_SECRET">
          <button type="submit">Send</button></form>"""
        output = _public_structure(sample, URLS[0][1])
        self.assertEqual(output["candidate_post_email_form_count_capped"], 1)
        self.assertEqual(output["submission_target_class"], "same_origin_https")
        self.assertTrue(output["required_named_consent_checkbox_seen"])
        self.assertTrue(output["csrf_named_hidden_in_candidate"])
        self.assertTrue(output["submit_control_in_candidate"])
        self.assertNotIn("SUPER_SECRET", json.dumps(output))

    def test_checkbox_without_required_is_not_counted_as_required(self):
        result = _public_structure(
            '<form method=post><input type=email><input type=checkbox name=agree>'
            '<button>Go</button></form>', URLS[0][1])
        self.assertTrue(result["consent_named_in_candidate"])
        self.assertFalse(result["required_named_consent_checkbox_seen"])

    def test_text_field_named_consent_is_not_checkbox_proof(self):
        result = _public_structure(
            '<form method=post><input type=email><input type=text name=consent required>'
            '</form>', URLS[0][1])
        self.assertTrue(result["consent_named_in_candidate"])
        self.assertFalse(result["required_named_consent_checkbox_seen"])

    def test_external_form_action_is_classified_not_leaked(self):
        sample = ('<form method="post" action="https://third-party.example.com/'
                  'path?token=VERY_PRIVATE_TOKEN"><input name=email></form>')
        result = _public_structure(sample, URLS[0][1])
        self.assertEqual(result["submission_target_class"], "external_https")
        self.assertNotIn("third-party.example", json.dumps(result))
        self.assertNotIn("VERY_PRIVATE_TOKEN", json.dumps(result))

    def test_http_action_classified_insecure_without_echo(self):
        result = _public_structure(
            '<form method=post action="http://localhost/private">'
            '<input type=email></form>', URLS[0][1])
        self.assertEqual(result["submission_target_class"], "unsafe_or_non_https")

    def test_javascript_action_classified_unsafe_without_execution(self):
        result = _public_structure(
            '<form method=post action="javascript:alert(1)">'
            '<input type=email></form>', URLS[0][1])
        self.assertEqual(result["submission_target_class"], "unsafe_or_non_https")

    def test_empty_action_is_same_origin_default(self):
        result = _public_structure(
            '<form method=post><input name=email></form>', URLS[0][1])
        self.assertEqual(result["submission_target_class"], "same_origin_default")

    def test_no_email_in_post_form_cannot_be_proven_from_footer_get_form(self):
        result = _public_structure(
            '<form method=post><input name=message></form>'
            '<form method=get><input name=email></form>', URLS[0][1])
        self.assertEqual(result["candidate_post_email_form_count_capped"], 0)

    def test_captcha_named_field_is_not_validation_proof(self):
        result = _public_structure(
            '<form method=post><input name=email>'
            '<input name=cf-turnstile-response></form>', URLS[0][1])
        self.assertTrue(result["captcha_named_field_in_candidate"])
        self.assertIsNone(_safe_probe(
            "canonical_php", URLS[0][1],
            Opener(HtmlResponse(
                b"<form method=post><input name=email><input name=cf-turnstile-response></form>"
            ))
        )["php_database_connected"])

    def test_truncated_response_fails_closed_for_missing_form(self):
        result = _safe_probe(
            "canonical_php", URLS[0][1],
            Opener(HtmlResponse(b"<html><p>" + b"z" * (MAX_BYTES + 42)))
        )
        self.assertTrue(result["body_truncated"])
        self.assertFalse(result["structural_evidence_complete"])
        self.assertIsNone(result["form_post_seen"])
        self.assertIsNone(result["consent_field_seen"])

    def test_form_cap_is_explicit_and_scan_is_incomplete(self):
        result = _safe_probe(
            "canonical_php", URLS[0][1],
            Opener(HtmlResponse(
                ("<form method=post><input name=email></form>" * (MAX_FORMS + 4)).encode()
            ))
        )
        self.assertEqual(result["form_count_capped"], MAX_FORMS)
        self.assertTrue(result["form_limit_reached"])
        self.assertFalse(result["structural_evidence_complete"])

    def test_hidden_fields_are_never_echoed_as_values(self):
        secret = "UNREDACTED_CSRF_SECRET_EXAMPLE"
        r = _safe_probe("canonical_php", URLS[0][1],
                        Opener(HtmlResponse(
                            (f"<form method='post'><input name=email><input type=hidden"
                             f" name=csrf_token value='{secret}'></form>").encode())))
        self.assertTrue(r["csrf_named_hidden_in_candidate"])
        self.assertNotIn(secret, json.dumps(r))

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
