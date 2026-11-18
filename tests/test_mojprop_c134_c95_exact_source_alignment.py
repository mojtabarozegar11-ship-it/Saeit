"""C134: predeployment C95 source/script pin parity; no production access."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/mojprop_live_intake_source_drift_readonly_c95.py"
WORKFLOW = ROOT / ".github/workflows/mojprop-live-intake-source-readonly-c95.yml"
PIN = "4a467a4472c748ef134a2aa29df9a58a2b8be885"
OLD = "6b7dcdccc9765049d1f26d62cdf8c78a56cc6573"


class SourceIdentityC134Tests(unittest.TestCase):
    @staticmethod
    def source_blob():
        raw = SOURCE.read_bytes()
        return hashlib.sha1(
            b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
        ).hexdigest()

    def test_c95_script_exact_git_blob_matches_main_review(self):
        self.assertEqual(self.source_blob(), PIN)

    def test_c95_runner_pin_matches_exact_reviewed_script(self):
        workflow = WORKFLOW.read_text("utf-8")
        self.assertIn(
            'test "$(git hash-object -- scripts/mojprop_live_intake_source_drift_readonly_c95.py)" = "' +
            PIN + '"', workflow
        )
        self.assertNotIn(OLD, workflow)

    def test_c95_runner_uses_only_one_script_pin(self):
        source = WORKFLOW.read_text("utf-8")
        pins = re.findall(
            r'git hash-object -- scripts/mojprop_live_intake_source_drift_readonly_c95.py\)" = "([a-f0-9]{40})"',
            source
        )
        self.assertEqual(pins, [PIN])

    def test_c95_source_no_change_to_customer_or_payment(self):
        source = SOURCE.read_text("utf-8")
        for forbidden in (
            "requests.post(", "objects.create(", "send_mail(", "wallet_transfer(",
            "os.remove(", "shutil.rmtree(", "subprocess.run(", "customer_email",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertIn('\"production_release_permitted\": False', source)

    def test_c95_runner_never_requests_buyer_post_or_deployment(self):
        source = WORKFLOW.read_text("utf-8")
        self.assertIn("permissions:\n  contents: read", source)
        self.assertIn("persist-credentials: false", source)
        self.assertNotIn("curl -X POST", source)
        self.assertNotIn("rsync ", source)
        self.assertNotIn("git push", source)
        self.assertIn("No POST, customer data, payment, database migration or site release", source)

    def test_c95_local_source_and_public_transport_evidence_distinct(self):
        source = SOURCE.read_text("utf-8")
        self.assertIn('\"public_runtime_equals_cli_runtime_proven\": False', source)
        self.assertIn('\"browser_public_endpoint_post_verified\": False', source)
        self.assertIn('\"customer_lead_created\": False', source)

    def test_c95_runner_sha_is_just_identity_not_live_success(self):
        source = SOURCE.read_text("utf-8")
        self.assertIn("source identity only, not a live Passenger release", source)
        self.assertIn("different live source must report DRIFT", source)


if __name__ == "__main__":
    unittest.main()
