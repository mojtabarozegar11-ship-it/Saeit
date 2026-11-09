"""Static, read-only guardrails for the opt-in MojPlayWin product release.

This test never connects to cPanel or starts a release. It prevents a return
to the embedded-template, auto-triggered release workflow.
"""

from pathlib import Path
import re
import unittest


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/mpw-complete-product-page-20261107-v2.yml"
)


class ProductReleaseSourceGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not WORKFLOW.is_file():
            raise unittest.SkipTest("Workflow file not checked out in this partial workspace")
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_release_is_manual_only_on_main(self):
        trigger = self.source.split("permissions:", 1)[0]
        self.assertIn("  workflow_dispatch:", trigger)
        self.assertNotIn("  push:", trigger)
        self.assertNotIn("  schedule:", trigger)
        self.assertIn("github.ref == 'refs/heads/main'", self.source)

    def test_exact_reviewed_source_is_required_before_host_connection(self):
        self.assertIn("expected_source_sha256:", self.source)
        self.assertIn("SOURCE_SHA256_MISMATCH", self.source)
        self.assertIn("TRANSFER_SHA256_MISMATCH", self.source)
        self.assertIn("POST_INSTALL_SHA256_MISMATCH", self.source)
        self.assertLess(
            self.source.index("SOURCE_SHA256_MISMATCH"),
            self.source.index("      - name: Relay"),
        )

    def test_no_old_embedded_base64_template(self):
        self.assertNotRegex(self.source, r"(?m)^\s+TEMPLATE_B64:\s*['\"]")
        self.assertIn(
            'TEMPLATE_B64="$(base64 -w0 core/templates/brands/mojplaywin/product.html)"',
            self.source,
        )
        self.assertIn("core/templates/brands/mojplaywin/product.html", self.source)

    def test_ssh_fingerprints_are_explicitly_checked(self):
        self.assertIn("SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs", self.source)
        self.assertIn("SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04", self.source)
        self.assertGreaterEqual(self.source.count("ssh-keygen -lf"), 2)
        self.assertIn("StrictHostKeyChecking yes", self.source)
        self.assertNotIn("StrictHostKeyChecking no", self.source)

    def test_backup_is_private_verified_and_local_failure_restores(self):
        for marker in (
            "UNTRUSTED_EXISTING_BACKUP",
            "BACKUP_INTEGRITY_FAILED",
            "os.O_NOFOLLOW,0o600",
            "MPW_BACKUP_PATH",
            "MPW_TEMPLATE_ROLLED_BACK_AFTER_LOCAL_CHECK_FAILURE",
            "os.replace(rb,T)",
        ):
            self.assertIn(marker, self.source)

    def test_live_verification_failure_requires_exact_run_rollback(self):
        for marker in (
            'RELEASE_ID="${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"',
            "rollback_if_needed()",
            "trap rollback_if_needed ERR",
            "ROLLBACK_REFUSES_CHANGED_TARGET",
            "MPW_ROLLBACK_COMPLETE",
            "DEPLOYED=1",
            "PRODUCT_DETAILS_NOT_LIVE_",
        ):
            self.assertIn(marker, self.source)
        self.assertLess(
            self.source.index("DEPLOYED=1"),
            self.source.index("PRODUCT_DETAILS_NOT_LIVE_"),
        )

    def test_no_remote_connection_in_preflight_step(self):
        preflight = self.source.split("      - name: Pin reviewed source before any host connection", 1)[1]
        preflight = preflight.split("      - name: Relay", 1)[0]
        self.assertNotIn("ssh ", preflight)
        self.assertNotIn("curl ", preflight)
        self.assertTrue(re.search(r"raw=src\.read_bytes\(\)", preflight))


if __name__ == "__main__":
    unittest.main()
