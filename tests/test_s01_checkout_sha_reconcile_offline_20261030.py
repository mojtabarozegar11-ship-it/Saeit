"""Synthetic, no-network tests for S-01 offline checkout SHA reconciliation."""
import hashlib
import io
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.s01_checkout_sha_reconcile_offline_20261030 import assess, main


class OfflinePreimageReconcileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        folder = self.root / "mpw_commerce"
        folder.mkdir()
        self.source = folder / "product_checkout_page.py"
        self.secret_fixture = b"synthetic-checkout-SECRET-CUSTOMER-NOT-FOR-OUTPUT"
        self.source.write_bytes(self.secret_fixture)
        self.expected = hashlib.sha256(self.secret_fixture).hexdigest()

    def test_matching_source_is_only_a_hash_match_not_release(self):
        verdict = assess(self.root, self.expected)
        self.assertEqual(verdict["status"], "MATCH")
        self.assertEqual(verdict["source_bytes"], len(self.secret_fixture))
        self.assertFalse(verdict["release_permitted"])
        self.assertFalse(verdict["offhost_restore_verified"])
        self.assertFalse(verdict["passenger_db_authority_verified"])
        self.assertNotIn("SECRET-CUSTOMER", str(verdict))

    def test_drift_reports_both_digests_without_source_text(self):
        verdict = assess(self.root, "0" * 64)
        self.assertEqual(verdict["status"], "SOURCE_SHA_DRIFT")
        self.assertEqual(verdict["observed_sha256"], self.expected)
        self.assertNotIn("SECRET-CUSTOMER", str(verdict))

    def test_symlinked_source_is_refused_and_no_backup_written(self):
        self.source.rename(self.root / "real.py")
        self.source.symlink_to(self.root / "real.py")
        with self.assertRaises((OSError, RuntimeError)):
            assess(self.root, self.expected)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["mpw_commerce", "real.py"])

    def test_invalid_hash_is_rejected(self):
        for bad in ("", "ABC", "G" * 64, "0" * 63, "a" * 65):
            with self.assertRaises(ValueError):
                assess(self.root, bad)

    def test_cli_returns_2_on_drift_and_never_prints_source(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["--root", str(self.root), "--expected", "0" * 64])
        self.assertEqual(code, 2)
        self.assertIn("SOURCE_SHA_DRIFT", out.getvalue())
        self.assertNotIn("SECRET-CUSTOMER", out.getvalue())

    def test_verified_approved_copy_does_not_hide_live_drift(self):
        approved = self.root / "approved"
        (approved / "mpw_commerce").mkdir(parents=True)
        (approved / "mpw_commerce" / "product_checkout_page.py").write_bytes(self.secret_fixture)
        self.source.write_bytes(b"synthetic-changed-checkout")
        verdict = assess(self.root, self.expected, approved_root=approved)
        self.assertEqual(verdict["status"], "SOURCE_SHA_DRIFT")
        self.assertTrue(verdict["approved_copy_verified"])
        self.assertEqual(verdict["approved_sha256"], self.expected)
        self.assertFalse(verdict["release_permitted"])
        comparison = verdict["approved_reference_comparison"]
        self.assertFalse(comparison["byte_identical"])
        self.assertEqual(comparison["first_difference_offset"], 0)
        self.assertEqual(comparison["difference_kind"], "BYTE_MISMATCH")
        self.assertEqual(comparison["approved_source_bytes"], len(self.secret_fixture))
        self.assertNotIn("SECRET-CUSTOMER", str(comparison))

    def test_approved_reference_identical_bytes_are_not_release_authorization(self):
        approved = self.root / "approved"
        (approved / "mpw_commerce").mkdir(parents=True)
        (approved / "mpw_commerce" / "product_checkout_page.py").write_bytes(self.secret_fixture)
        verdict = assess(self.root, self.expected, approved_root=approved)
        self.assertEqual(verdict["status"], "MATCH")
        self.assertEqual(verdict["approved_reference_comparison"]["difference_kind"], "IDENTICAL")
        self.assertIsNone(verdict["approved_reference_comparison"]["first_difference_offset"])
        self.assertFalse(verdict["release_permitted"])

    def test_approved_reference_prefix_reports_offset_not_source(self):
        approved = self.root / "approved"
        (approved / "mpw_commerce").mkdir(parents=True)
        (approved / "mpw_commerce" / "product_checkout_page.py").write_bytes(self.secret_fixture)
        self.source.write_bytes(self.secret_fixture + b"\n# synthetic change")
        verdict = assess(self.root, self.expected, approved_root=approved)
        self.assertEqual(verdict["status"], "SOURCE_SHA_DRIFT")
        comparison = verdict["approved_reference_comparison"]
        self.assertEqual(comparison["difference_kind"], "APPROVED_PREFIX")
        self.assertEqual(comparison["first_difference_offset"], len(self.secret_fixture))
        self.assertNotIn("synthetic change", str(verdict))
        self.assertFalse(verdict["release_permitted"])

    def test_unapproved_reference_cannot_validate_source(self):
        approved = self.root / "approved"
        (approved / "mpw_commerce").mkdir(parents=True)
        (approved / "mpw_commerce" / "product_checkout_page.py").write_bytes(b"wrong")
        verdict = assess(self.root, self.expected, approved_root=approved)
        self.assertEqual(verdict["status"], "APPROVED_COPY_SHA_MISMATCH")
        self.assertFalse(verdict["approved_copy_verified"])
        self.assertIsNone(verdict["approved_reference_comparison"])
        self.assertFalse(verdict["release_permitted"])
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["--root", str(self.root), "--expected", self.expected,
                         "--approved-root", str(approved)])
        self.assertEqual(code, 3)
        self.assertNotIn("SECRET-CUSTOMER", output.getvalue())

    def test_symlinked_approved_reference_is_refused(self):
        approved = self.root / "approved"
        approved.mkdir()
        (approved / "mpw_commerce").symlink_to(self.root / "mpw_commerce",
                                                 target_is_directory=True)
        with self.assertRaises((OSError, RuntimeError)):
            assess(self.root, self.expected, approved_root=approved)

    def test_cli_fail_closed_on_missing_file(self):
        self.source.unlink()
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["--root", str(self.root), "--expected", self.expected])
        self.assertEqual(code, 3)
        self.assertIn("BLOCKED_SOURCE_UNREADABLE_OR_INVALID", out.getvalue())


if __name__ == "__main__":
    unittest.main()
