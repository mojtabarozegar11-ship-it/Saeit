"""Synthetic, no-network S-01 cPanel checkout provenance regression tests."""
import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from scripts.s01_checkout_cpanel_provenance_readonly_20261030 import callable_delta, probe


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.staging = self.home / "Saeit-staging/mpw_commerce/product_checkout_page.py"
        self.prod = self.home / "Saeit/mpw_commerce/product_checkout_page.py"
        self.private = self.home / ".private_mojplaywin_main_agents"
        for parent in (self.staging.parent, self.prod.parent, self.private):
            parent.mkdir(parents=True)
        self.private.chmod(0o700)
        self.approved = b"price = 5\n"
        self.pin = hashlib.sha256(self.approved).hexdigest()
        self.staging.write_bytes(self.approved)

    def verdict(self):
        return probe(self.home, expected=self.pin, owner_uid=os.getuid())

    def test_matching_staging_not_release(self):
        r = self.verdict()
        self.assertEqual(r["classification"], "SOURCE_PIN_MATCH_RELEASE_STILL_BLOCKED")
        self.assertFalse(r["release_permitted"])
        self.assertFalse(r["off_vps_restore_verified"])

    def test_drift_without_approved(self):
        self.staging.write_bytes(b"price = 6\n")
        self.assertEqual(self.verdict()["classification"], "SOURCE_SHA_DRIFT_NO_APPROVED_COPY")

    def test_production_ast_equivalent(self):
        self.staging.write_bytes(b"# comment\nprice = 5\n")
        self.prod.write_bytes(self.approved)
        r = self.verdict()
        self.assertEqual(r["classification"], "SOURCE_SHA_DRIFT_AST_EQUIVALENT")
        self.assertEqual(r["approved_reference_label"], "production_tree")

    def test_private_semantic_difference(self):
        self.staging.write_bytes(b"price = 6\n")
        path = self.private / ("mpw-checkout-csp-preimage-" + self.pin[:16] + ".bak")
        path.write_bytes(self.approved)
        path.chmod(0o600)
        r = self.verdict()
        self.assertEqual(r["classification"], "SOURCE_SHA_DRIFT_SEMANTIC_OR_SYNTAX_DIFFERENCE")
        self.assertFalse(r["ast_equivalent"])

    def test_exact_approved_candidate_is_recognized_but_not_release_authorized(self):
        candidate = b"price = 6\\n"
        candidate_sha = hashlib.sha256(candidate).hexdigest()
        self.staging.write_bytes(candidate)
        backup = self.private / ("mpw-checkout-csp-preimage-" + self.pin[:16] + ".bak")
        backup.write_bytes(self.approved)
        backup.chmod(0o600)
        with patch(
            "scripts.s01_checkout_cpanel_provenance_readonly_20261030.APPROVED_CANDIDATE_SHA256",
            candidate_sha,
        ):
            r = self.verdict()
        self.assertEqual(
            r["classification"], "APPROVED_CANDIDATE_PRESENT_RELEASE_STILL_BLOCKED"
        )
        self.assertFalse(r["source_matches_pin"])
        self.assertTrue(r["source_matches_approved_candidate"])
        self.assertTrue(r["approved_reference_found"])
        self.assertFalse(r["release_permitted"])

    def test_callable_delta_reports_only_bounded_names_and_states(self):
        approved = b'def invoice():\n    return "approved-secret"\nclass Handler: pass\n'
        current = b'def invoice():\n    return "current-secret"\ndef settle(): return 1\n'
        delta = callable_delta(approved, current)
        self.assertEqual(
            {(row["name"], row["state"]) for row in delta},
            {("invoice", "MODIFIED"), ("Handler", "REMOVED"), ("settle", "ADDED")},
        )
        self.assertNotIn("approved-secret", str(delta))
        self.assertNotIn("current-secret", str(delta))

    def test_private_permissions_refused(self):
        self.staging.write_bytes(b"price = 6\n")
        path = self.private / ("mpw-checkout-csp-preimage-" + self.pin[:16] + ".bak")
        path.write_bytes(self.approved)
        path.chmod(0o644)
        self.assertEqual(self.verdict()["candidate_states"]["private_preimage"], "UNAVAILABLE_OR_UNSAFE")

    def test_symlink_candidate_refused(self):
        self.staging.write_bytes(b"price = 6\n")
        self.prod.symlink_to(self.staging)
        self.assertEqual(self.verdict()["candidate_states"]["production_tree"], "UNAVAILABLE_OR_UNSAFE")

    def test_hardlink_source_refused(self):
        os.link(self.staging, self.home / "hardlink")
        self.assertEqual(self.verdict()["source_status"], "UNAVAILABLE_OR_UNSAFE")

    def test_invalid_pin(self):
        with self.assertRaises(ValueError):
            probe(self.home, expected="invalid")

    def test_secret_never_printed(self):
        self.staging.write_bytes(b'price = "SECRET_CUSTOMER_ABC"\n')
        self.prod.write_bytes(self.approved)
        self.assertNotIn("SECRET_CUSTOMER_ABC", str(self.verdict()))

    def test_missing_source_blocked(self):
        self.staging.unlink()
        self.assertEqual(self.verdict()["classification"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
