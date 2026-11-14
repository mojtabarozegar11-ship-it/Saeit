"""Fail-closed commercialization decisions from public-only metadata."""
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

from deploy.company_public_intake_release_gate import (
    PREFIX, evaluate_report, main,
)


def report(*, form=None):
    canonical = {
        "target": "canonical_php",
        "observation": "public_html_observed",
        "http_status": 200,
        "structural_evidence_complete": True,
        "candidate_post_email_form_count_capped": 1,
        "submission_target_class": "same_origin_https",
        "submit_control_in_candidate": True,
        "consent_named_in_candidate": True,
        "required_named_consent_checkbox_seen": True,
        "csrf_named_hidden_in_candidate": True,
        "captcha_named_field_in_candidate": True,
    }
    canonical.update(form or {})
    return {
        "mode": "public_readonly_get_no_credentials",
        "results": [canonical, {
            "target": "company_page", "http_status": 200,
        }, {
            "target": "contact_page", "http_status": 200,
        }],
    }


class ReadinessGateTests(unittest.TestCase):
    def test_perfect_public_form_still_not_a_deploy_or_sale_authorization(self):
        result = evaluate_report(report())
        self.assertEqual(result["readiness"], "NO_GO_REQUIRES_PRODUCTION_HOST_EVIDENCE")
        self.assertEqual(result["public_structural_findings"], [])
        self.assertFalse(result["release_authorized"])
        self.assertIsNone(result["cash_settlement_verified"])
        self.assertFalse(result["real_customer_post_submitted"])
        self.assertGreaterEqual(len(result["production_unverified_requirements"]), 5)

    def test_missing_named_consent_is_flagged_without_claiming_server_absence(self):
        output = evaluate_report(report(form={"consent_named_in_candidate": False}))
        self.assertIn("named_consent_field_not_observed", output["public_structural_findings"])
        self.assertIn("php_server_side_consent_validation_and_retention",
                      output["production_unverified_requirements"])

    def test_missing_required_checkbox_is_a_distinct_issue(self):
        output = evaluate_report(report(form={"required_named_consent_checkbox_seen": False}))
        self.assertIn("required_named_consent_checkbox_not_observed",
                      output["public_structural_findings"])

    def test_missing_csrf_named_hidden_field_is_review_not_exploit_claim(self):
        output = evaluate_report(report(form={"csrf_named_hidden_in_candidate": False}))
        self.assertIn("csrf_named_hidden_field_not_observed",
                      output["public_structural_findings"])
        self.assertFalse(output["release_authorized"])

    def test_missing_captcha_named_field_is_observation_not_backend_assertion(self):
        output = evaluate_report(report(form={"captcha_named_field_in_candidate": False}))
        self.assertIn("captcha_named_field_not_observed", output["public_structural_findings"])

    def test_unsafe_or_cross_origin_form_action_blocks_release(self):
        for target in ("unsafe_or_non_https", "external_https", None, "invalid_action"):
            with self.subTest(target=target):
                output = evaluate_report(report(form={"submission_target_class": target}))
                self.assertIn("post_destination_unverified_or_cross_origin",
                              output["public_structural_findings"])
                self.assertFalse(output["release_authorized"])

    def test_no_post_with_email_field_is_not_customer_form_proof(self):
        output = evaluate_report(report(form={
            "candidate_post_email_form_count_capped": 0,
        }))
        self.assertIn("no_post_with_email_form_observed",
                      output["public_structural_findings"])
        self.assertFalse(output["public_php_post_email_form_observed"])

    def test_incomplete_or_truncated_form_is_not_green(self):
        output = evaluate_report(report(form={
            "structural_evidence_complete": False
        }))
        self.assertIn("php_public_form_evidence_incomplete",
                      output["public_structural_findings"])

    def test_404_php_and_missing_page_does_not_pass_as_revenue(self):
        r = report(form={"http_status": 404, "observation": "http_response_not_success"})
        r["results"][1]["http_status"] = 404
        result = evaluate_report(r)
        self.assertIn("php_public_html_not_observed", result["public_structural_findings"])
        self.assertIn("company_page_public_http_200_not_observed",
                      result["public_structural_findings"])

    def test_duplicate_target_rejected(self):
        r = report()
        r["results"][1]["target"] = "canonical_php"
        with self.assertRaises(ValueError):
            evaluate_report(r)

    def test_unknown_target_rejected(self):
        r = report()
        r["results"][1]["target"] = "secret_customer_db"
        with self.assertRaises(ValueError):
            evaluate_report(r)

    def test_wrong_mode_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_report({"mode": "production_verified", "results": report()["results"]})

    def test_main_reads_redacted_local_line_only_and_prints_no_customer_payload(self):
        payload = report()
        secret = "PRIVATE_CLIENT_EMAIL_NEVER_LEAKED"
        payload["untrusted_note"] = secret
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as f:
            path = f.name
            f.write(PREFIX + json.dumps(payload) + "\n")
        try:
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(path), 0)
            self.assertIn("ZM_PUBLIC_INTAKE_RELEASE_GATE=", output.getvalue())
            self.assertNotIn(secret, output.getvalue())
            self.assertIn("NO_GO_REQUIRES_PRODUCTION_HOST_EVIDENCE", output.getvalue())
        finally:
            os.unlink(path)

    def test_main_invalid_file_or_oversized_payload_remains_no_go(self):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as f:
            path = f.name
            f.write("NOT_VALID_PREFIX=" + "x" * 40000)
        try:
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(path), 0)
            self.assertIn("NO_GO_PROBE_INVALID_OR_UNAVAILABLE", output.getvalue())
            self.assertIn('"release_authorized": false', output.getvalue())
        finally:
            os.unlink(path)

    def test_main_missing_file_fails_closed_without_exception_detail(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main("/nonexistent/private-receipts-file",), 0)
        self.assertIn("NO_GO_PROBE_INVALID_OR_UNAVAILABLE", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())


if __name__ == "__main__":
    unittest.main()
