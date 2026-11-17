"""C125 contract: evidence success never equals a payable MOJ PROP launch.

Pure local fixtures; no HTTP, payment, email, CSRF values, tokens or customer
writes. Synthetic log injection tests ensure data cannot reach Actions summary.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.mojprop_public_buyer_readiness_summary_20261117 import (
    KEYS, TRANSPORT_KEYS, parse_contract_evidence, parse_transport_evidence, summary,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/mojprop-public-readonly-24h-evidence-20261115.yml"
RUNNER = ROOT / "scripts/mojprop_public_buyer_readiness_summary_20261117.py"


def specimen(intake="PASS", status="PASS", gate="PASS"):
    return "\n".join((
        f"{KEYS[0]}={intake}",
        f"{KEYS[1]}={status}",
        f"{KEYS[2]}={gate}",
        f"{KEYS[3]}=true",
        f"{KEYS[4]}=false",
    )) + "\n"


def transport(intake_http="200", intake_exit="0", intake_redirects="0",
              status_http="200", status_exit="0", status_redirects="0"):
    return "\n".join((
        f"{TRANSPORT_KEYS[0]}={intake_http}",
        f"{TRANSPORT_KEYS[1]}={intake_exit}",
        f"{TRANSPORT_KEYS[2]}={intake_redirects}",
        f"{TRANSPORT_KEYS[3]}={status_http}",
        f"{TRANSPORT_KEYS[4]}={status_exit}",
        f"{TRANSPORT_KEYS[5]}={status_redirects}",
    )) + "\n"


class BuyerReadinessEvidenceTests(unittest.TestCase):
    def test_valid_get_forms_never_claim_buyer_payment(self):
        status, page = summary(parse_contract_evidence(specimen()), parse_transport_evidence(transport()))
        self.assertEqual(status, "GET_HTML_ONLY_PASS_NOT_COMMERCIAL_READY")
        self.assertIn("Customer POST persisted | NOT TESTED", page)
        self.assertIn("TRON invoice / payment / settlement | NOT VERIFIED", page)
        self.assertNotIn("READY_TO_SELL", page)

    def test_intake_html_failure_holds_entire_buyer_gate(self):
        status, page = summary(parse_contract_evidence(specimen(intake="FAIL",gate="DEGRADED")))
        self.assertEqual(status, "BLOCKED")
        self.assertIn("Native consent / intake HTML | FAIL", page)

    def test_private_status_html_failure_holds_entire_buyer_gate(self):
        status, page = summary(parse_contract_evidence(specimen(status="FAIL",gate="DEGRADED")))
        self.assertEqual(status, "BLOCKED")
        self.assertIn("Private receipt-status POST-form HTML | FAIL", page)

    def test_both_broken_still_has_no_release_permission(self):
        status, page = summary(parse_contract_evidence(
            specimen(intake="FAIL",status="FAIL",gate="DEGRADED")
        ))
        self.assertEqual(status,"BLOCKED")
        self.assertIn("No paid launch permission",page)

    def test_fake_pass_when_one_html_contract_failed_is_invalid(self):
        self.assertIsNone(parse_contract_evidence(specimen(status="FAIL",gate="PASS")))

    def test_fake_degraded_when_both_pass_is_invalid(self):
        self.assertIsNone(parse_contract_evidence(specimen(gate="DEGRADED")))

    def test_missing_evidence_fails_closed(self):
        self.assertIsNone(parse_contract_evidence(specimen().replace(
            f"{KEYS[1]}=PASS\n",""
        )))
        self.assertEqual(summary(None)[0],"BLOCKED")

    def test_duplicate_status_is_not_accepted(self):
        self.assertIsNone(parse_contract_evidence(specimen()+f"{KEYS[0]}=PASS\n"))

    def test_unknown_data_and_private_fields_are_rejected(self):
        for extra in (
            "csrf_token=private-secret\n",
            "receipt_token=private-secret\n",
            "customer_email=buyer@example.com\n",
            "RAW_HTML=<input value=private>\n",
            "# stray output\n",
        ):
            with self.subTest(extra=extra.split("=")[0]):
                self.assertIsNone(parse_contract_evidence(specimen()+extra))

    def test_unapproved_checkout_claim_is_denied(self):
        sample=specimen().replace(
            f"{KEYS[4]}=false",f"{KEYS[4]}=true"
        )
        self.assertIsNone(parse_contract_evidence(sample))

    def test_oversize_classifier_output_denied(self):
        self.assertIsNone(parse_contract_evidence(specimen()+"X"*3000))

    def test_output_summary_contains_no_untrusted_log_text(self):
        text=specimen()+"receipt_token=SECRET-CANARY\n"
        status, page=summary(parse_contract_evidence(text))
        self.assertEqual(status,"BLOCKED")
        self.assertNotIn("SECRET-CANARY",page)
        self.assertNotIn("receipt_token=",page)

    def test_workflow_wires_only_sanitized_decisions_into_summary(self):
        wf=WORKFLOW.read_text("utf-8")
        self.assertIn("mojprop_public_nojs_get_contract_c123.py",wf)
        self.assertIn('tee "$RUNNER_TEMP/mojprop-nojs-sanitized-decisions.txt"',wf)
        self.assertIn('transport_proof="$RUNNER_TEMP/mojprop-nojs-transport-decisions.txt"',wf)
        self.assertIn("%{num_redirects}",wf)
        self.assertIn('"$transport_proof" \\',wf)
        self.assertIn("mojprop_public_buyer_readiness_summary_20261117.py",wf)
        self.assertIn('"$GITHUB_STEP_SUMMARY"',wf)
        self.assertIn("NO_POST_NO_PAYMENT_NO_RELEASE=true",wf)

    def test_html_only_pass_without_transport_is_blocked(self):
        state, page = summary(parse_contract_evidence(specimen()))
        self.assertEqual(state, "BLOCKED")
        self.assertIn("UNVERIFIED", page)

    def test_404_with_valid_looking_form_is_blocked(self):
        state, page = summary(
            parse_contract_evidence(specimen()),
            parse_transport_evidence(transport(status_http="404")),
        )
        self.assertEqual(state, "BLOCKED")
        self.assertIn("HTTP 404", page)

    def test_intake_500_with_form_shape_is_blocked(self):
        state, page = summary(
            parse_contract_evidence(specimen()),
            parse_transport_evidence(transport(intake_http="500")),
        )
        self.assertEqual(state, "BLOCKED")
        self.assertIn("HTTP 500", page)

    def test_network_error_000_is_blocked(self):
        state, page = summary(
            parse_contract_evidence(specimen()),
            parse_transport_evidence(transport(intake_http="000", intake_exit="6")),
        )
        self.assertEqual(state, "BLOCKED")
        self.assertIn("HTTP 000", page)

    def test_curl_transport_error_even_on_http200_is_blocked(self):
        state, _ = summary(
            parse_contract_evidence(specimen()),
            parse_transport_evidence(transport(status_exit="28")),
        )
        self.assertEqual(state, "BLOCKED")

    def test_intake_http_redirect_even_when_landed_200_is_blocked(self):
        state, _ = summary(
            parse_contract_evidence(specimen()),
            parse_transport_evidence(transport(intake_redirects="1")),
        )
        self.assertEqual(state, "BLOCKED")

    def test_private_receipt_redirect_even_when_landed_200_is_blocked(self):
        state, _ = summary(
            parse_contract_evidence(specimen()),
            parse_transport_evidence(transport(status_redirects="1")),
        )
        self.assertEqual(state, "BLOCKED")

    def test_unknown_redirect_is_blocked(self):
        state, _ = summary(
            parse_contract_evidence(specimen()),
            parse_transport_evidence(transport(status_redirects="unknown")),
        )
        self.assertEqual(state, "BLOCKED")

    def test_unknown_curl_exit_is_blocked(self):
        state, _ = summary(
            parse_contract_evidence(specimen()),
            parse_transport_evidence(transport(intake_exit="unknown")),
        )
        self.assertEqual(state, "BLOCKED")

    def test_transport_duplicate_or_missing_keys_fails_closed(self):
        self.assertIsNone(parse_transport_evidence(transport() + TRANSPORT_KEYS[0]+"=200\\n"))
        self.assertIsNone(parse_transport_evidence(transport().replace(
            TRANSPORT_KEYS[5]+"=0\\n", "")))
        self.assertEqual(summary(parse_contract_evidence(specimen()),None)[0],"BLOCKED")

    def test_transport_injected_privacy_data_denied(self):
        for injected in ("receipt_token=SECRET\\n", "csrf_token=SECRET\\n",
                         "customer_email=buyer@example.com\\n", "# html \\n"):
            with self.subTest(injected=injected[:8]):
                self.assertIsNone(parse_transport_evidence(transport()+injected))

    def test_transport_non_numeric_and_overlarge_fields_denied(self):
        self.assertIsNone(parse_transport_evidence(transport(status_http="two-hundred")))
        self.assertIsNone(parse_transport_evidence(transport(intake_redirects="NaN")))
        self.assertIsNone(parse_transport_evidence(transport(status_exit="-1")))
        self.assertIsNone(parse_transport_evidence(transport()+"X"*1300))

    def test_http_301_redirect_response_is_not_200(self):
        state,_=summary(parse_contract_evidence(specimen()),
                        parse_transport_evidence(transport(status_http="301",status_redirects="1")))
        self.assertEqual(state,"BLOCKED")

    def test_status_and_intake_must_be_independently_proven(self):
        self.assertEqual(summary(parse_contract_evidence(specimen()),
                                  parse_transport_evidence(transport(status_http="200",intake_http="404")))[0],
                         "BLOCKED")
        self.assertEqual(summary(parse_contract_evidence(specimen()),
                                  parse_transport_evidence(transport(status_http="404",intake_http="200")))[0],
                         "BLOCKED")

    def test_successful_runner_only_claims_get_html_not_payment(self):
        with tempfile.TemporaryDirectory() as td:
            c=Path(td)/"contract.txt"
            t=Path(td)/"transport.txt"
            result=Path(td)/"step-summary.md"
            c.write_text(specimen(),"utf-8")
            t.write_text(transport(),"utf-8")
            run=subprocess.run([sys.executable,str(RUNNER),str(c),str(t),str(result)],
                               check=False,capture_output=True,text=True,timeout=6)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertIn("GET_HTML_ONLY_PASS_NOT_COMMERCIAL_READY",run.stdout)
            self.assertIn("TRON invoice / payment / settlement | NOT VERIFIED",result.read_text("utf-8"))

    def test_transport_file_symlink_cannot_claim_readiness(self):
        with tempfile.TemporaryDirectory() as td:
            c=Path(td)/"contract.txt"
            actual=Path(td)/"real-transport.txt"
            symlink=Path(td)/"transport-link.txt"
            dest=Path(td)/"summary.md"
            c.write_text(specimen(),"utf-8")
            actual.write_text(transport(),"utf-8")
            symlink.symlink_to(actual)
            run=subprocess.run([sys.executable,str(RUNNER),str(c),str(symlink),str(dest)],
                               check=False,capture_output=True,text=True,timeout=6)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertIn("MOJPROP_LIVE_CUSTOMER_READINESS=BLOCKED",run.stdout)

    def test_runner_writes_fixed_blocked_summary_without_secret(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"classified.txt"
            out=Path(td)/"summary.md"
            t=Path(td)/"transport.txt"
            t.write_text(transport(status_http="404"),"utf-8")
            p.write_text(specimen(intake="FAIL",status="FAIL",gate="DEGRADED"),"utf-8")
            run=subprocess.run([sys.executable,str(RUNNER),str(p),str(t),str(out)],
                               check=False,capture_output=True,text=True,timeout=6)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertIn("MOJPROP_LIVE_CUSTOMER_READINESS=BLOCKED",run.stdout)
            self.assertIn("Customer POST persisted | NOT TESTED",out.read_text("utf-8"))
            self.assertNotIn("PASS_NOT_COMMERCIAL_READY",run.stdout)

    def test_runner_rejects_symlink_input(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"private-data.txt"
            link=Path(td)/"sanitized.txt"
            out=Path(td)/"summary.md"
            p.write_text(specimen(),"utf-8")
            link.symlink_to(p)
            t=Path(td)/"transport.txt"
            t.write_text(transport(),"utf-8")
            run=subprocess.run([sys.executable,str(RUNNER),str(link),str(t),str(out)],
                               check=False,capture_output=True,text=True,timeout=6)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertIn("MOJPROP_LIVE_CUSTOMER_READINESS=BLOCKED",run.stdout)

    def test_runner_rejects_symlink_summary_destination(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"sanitized.txt"
            final=Path(td)/"private.md"
            link=Path(td)/"summary.md"
            p.write_text(specimen(),"utf-8")
            final.write_text("private unchanged","utf-8")
            link.symlink_to(final)
            t=Path(td)/"transport.txt"
            t.write_text(transport(),"utf-8")
            run=subprocess.run([sys.executable,str(RUNNER),str(p),str(t),str(link)],
                               check=False,capture_output=True,text=True,timeout=6)
            self.assertNotEqual(run.returncode,0)
            self.assertEqual(final.read_text("utf-8"),"private unchanged")


if __name__ == "__main__":
    unittest.main()
