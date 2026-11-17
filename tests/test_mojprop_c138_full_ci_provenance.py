"""C138 global CI recovery: immutable C136 parents, C95 source pin and commerce.

Synthetic source-only checks. No network, SSH, database, customer POST, TRX
invoice, broker or deployment. A green result is not a production release.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
C136 = ROOT / "tests/test_mojprop_c136_preserve_main_merge_resolver.py"
C137 = ROOT / ".github/workflows/mojprop-c137-integrated-main-full-ci-20261117.yml"
DRIFT = ROOT / "scripts/mojprop_live_intake_source_drift_readonly_c95.py"
C95 = ROOT / ".github/workflows/mojprop-live-intake-source-readonly-c95.yml"
TELEMETRY = ROOT / "tests/test_mpw_guest_telemetry_isolation_20261108.py"


class GlobalProofContractTests(unittest.TestCase):
    def test_real_reviewed_merge_has_two_exact_parents(self):
        raw = subprocess.run(
            ["git", "show", "-s", "--format=%P",
             "2ee98ecfab950903e9cb550908f8242255c39e9d"],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(raw.returncode, 0, raw.stderr)
        self.assertEqual(raw.stdout.strip().split(), [
            "0af1a0415bb75354cb119a8653230486f95e1a96",
            "70c6607142d8ad90efe5e98bdcda04504b58c59b",
        ])

    def test_c136_regressions_validate_actual_merge_not_synthetic_sha(self):
        source = C136.read_text("utf-8")
        ast.parse(source)
        self.assertIn("ancestry.stdout.strip().split()", source)
        self.assertIn("reviewed_main", source)
        self.assertIn("reviewed_prop", source)
        self.assertIn("if bool(env_main) != bool(env_prop):", source)
        self.assertIn('raise RuntimeError("C136 both source SHAs required together")', source)

    def test_full_ci_reads_ancestry_and_does_not_override_database_url(self):
        workflow = C137.read_text("utf-8")
        self.assertIn("fetch-depth: 0", workflow)
        self.assertNotIn("DATABASE_URL:", workflow)
        self.assertIn("python3 -m pytest -q", workflow)
        self.assertIn("python3 manage.py makemigrations --check --dry-run", workflow)
        self.assertIn("python3 manage.py migrate --noinput", workflow)

    def test_c95_source_pin_is_reviewed_new_combined_url_map(self):
        import hashlib
        from scripts.mojprop_live_intake_source_drift_readonly_c95 import (
            EXPECTED, exact_git_blob
        )
        urls = (ROOT / "config/urls.py").read_bytes()
        self.assertEqual(
            EXPECTED["config/urls.py"],
            exact_git_blob(urls),
        )
        self.assertIn(b'/moj-prop-interest/form/', urls)
        self.assertIn(b'/moj-prop-intake/', urls)

    def test_c95_identity_has_no_side_effect_and_matches_runner_pin(self):
        import hashlib
        data = DRIFT.read_bytes()
        source_sha = hashlib.sha1(
            b"blob " + str(len(data)).encode() + b"\0" + data
        ).hexdigest()
        workflow = C95.read_text("utf-8")
        needle = (
            'test "$(git hash-object -- '
            'scripts/mojprop_live_intake_source_drift_readonly_c95.py)" = "'
            + source_sha + '"'
        )
        self.assertIn(needle, workflow)
        self.assertIn("production_release_permitted", DRIFT.read_text("utf-8"))
        self.assertIn('"public_runtime_equals_cli_runtime_proven": False',
                      DRIFT.read_text("utf-8"))

    def test_checkout_metrics_do_not_count_201_or_rejection(self):
        code = TELEMETRY.read_text("utf-8")
        self.assertIn("HTTP 201 (without exact signed", code)
        self.assertIn('self.assertEqual(record.call_count, 0)', code)
        self.assertIn('"/commerce/trx-easy/invoice/8/"', code)
        # At least one independent positive redirect case remains testable.
        self.assertIn("def test_only_server_issued_invoice_redirect_creates_funnel_event", code)

    def test_no_insecure_git_checkout_or_background_deployment(self):
        source = C137.read_text("utf-8")
        self.assertIn("persist-credentials: false", source)
        self.assertIn("contents: read", source)
        self.assertNotIn("rsync ", source)
        self.assertNotIn("ssh ", source)
        self.assertNotIn("git push", source)
        self.assertNotIn("curl -X POST", source)


if __name__ == "__main__":
    unittest.main()
