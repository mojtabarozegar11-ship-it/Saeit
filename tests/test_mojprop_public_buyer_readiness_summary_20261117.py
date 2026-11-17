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
    KEYS, parse_contract_evidence, summary,
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


class BuyerReadinessEvidenceTests(unittest.TestCase):
    def test_valid_get_forms_never_claim_buyer_payment(self):
        status, page = summary(parse_contract_evidence(specimen()))
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
        self.assertIn("mojprop_public_buyer_readiness_summary_20261117.py",wf)
        self.assertIn('"$GITHUB_STEP_SUMMARY"',wf)
        self.assertIn("NO_POST_NO_PAYMENT_NO_RELEASE=true",wf)

    def test_runner_writes_fixed_blocked_summary_without_secret(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"classified.txt"
            out=Path(td)/"summary.md"
            p.write_text(specimen(intake="FAIL",status="FAIL",gate="DEGRADED"),"utf-8")
            run=subprocess.run([sys.executable,str(RUNNER),str(p),str(out)],
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
            run=subprocess.run([sys.executable,str(RUNNER),str(link),str(out)],
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
            run=subprocess.run([sys.executable,str(RUNNER),str(p),str(link)],
                               check=False,capture_output=True,text=True,timeout=6)
            self.assertNotEqual(run.returncode,0)
            self.assertEqual(final.read_text("utf-8"),"private unchanged")


if __name__ == "__main__":
    unittest.main()
