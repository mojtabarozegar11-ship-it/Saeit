"""True-source contract tests for the read-only cPanel Moj Prop intake audit."""
import hashlib
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from scripts.mojprop_live_intake_source_drift_readonly_c95 import (
    EXPECTED, MAX_SOURCE, exact_git_blob, safe_source_state
)


class MojPropLiveIntakeDriftTests(unittest.TestCase):
    def test_git_empty_blob_matches_standard_git(self):
        self.assertEqual(exact_git_blob(b""),
                         "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")

    def test_nonempty_git_blob_framing_matches_independent_hash(self):
        data = b"source\n"
        expected = hashlib.sha1(
            b"blob " + str(len(data)).encode() + bytes((0,)) + data
        ).hexdigest()
        self.assertEqual(exact_git_blob(data), expected)

    def test_fails_closed_on_invalid_source_or_oversize(self):
        for item in ("abc", bytearray(), None, b"x" * (MAX_SOURCE + 1)):
            with self.subTest(what=type(item).__name__):
                with self.assertRaises(ValueError):
                    exact_git_blob(item)

    def test_exact_safe_file_and_changed_file_are_distinct(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "core").mkdir()
            target = root / "core" / "mojprop_views.py"
            data = b"clean source\n"
            target.write_bytes(data)
            target.chmod(0o600)
            ref = exact_git_blob(data)
            self.assertEqual(safe_source_state(root, "core/mojprop_views.py", ref), "matches")
            target.write_bytes(b"unreviewed changes\n")
            self.assertEqual(safe_source_state(root, "core/mojprop_views.py", ref), "drifted")

    def test_missing_source_is_explicitly_missing_not_implicitly_matching(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(
                safe_source_state(Path(d), "core/nonexistent.py", "0" * 40),
                "missing"
            )

    def test_unreadable_existing_source_is_not_classified_as_missing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = root / "existing.py"
            target.write_bytes(b"present but unreadable")
            target.chmod(0o600)
            with patch.object(Path, "open", side_effect=PermissionError):
                self.assertEqual(
                    safe_source_state(root, "existing.py",
                                      exact_git_blob(b"present but unreadable")),
                    "unavailable"
                )

    def test_nested_symlink_is_denied_without_following_content(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            outside = root / "outside"
            outside.mkdir()
            (outside / "private.py").write_text("secret")
            (root / "core").symlink_to(outside, target_is_directory=True)
            self.assertEqual(
                safe_source_state(root, "core/private.py", "0" * 40),
                "unavailable"
            )

    def test_source_world_writable_is_denied(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "core").mkdir()
            target = root / "core" / "view.py"
            target.write_text("ok")
            target.chmod(0o606)
            self.assertEqual(
                safe_source_state(root, "core/view.py", exact_git_blob(b"ok")),
                "unsafe"
            )

    def test_source_list_fixed_to_reviewed_mojprop_files(self):
        self.assertEqual(set(EXPECTED), {
            "core/mojprop_views.py",
            "core/mojprop_receipts.py",
            "core/mojprop_accessible_intake.py",
            "config/urls.py",
            "core/management/commands/mojprop_sales_action_queue.py",
        })
        self.assertTrue(all(len(value) == 40 for value in EXPECTED.values()))
        # A stale four-file pin returned misleading "drift" after current-main
        # source was actually merged. Public HTML must be audited as well.
        self.assertEqual(EXPECTED["core/mojprop_views.py"],
                         "12ee5e408f2a50e0571d5e6d91a760644ec210a9")
        self.assertEqual(EXPECTED["core/mojprop_receipts.py"],
                         "9fe6eb1ad13857143440517b14b3f2ebcfef6db3")
        self.assertEqual(EXPECTED["core/mojprop_accessible_intake.py"],
                         "9642945352357f824cb6ac3b15816b134cb22dec")


    def test_all_pins_match_exact_reviewed_source_bytes_in_this_commit(self):
        # A source-only PR must not quietly ship an old git blob identity.
        # The live host probe compares these fixed hashes without uploading
        # credentials or customer data. A changed source must update its pin.
        root = Path(__file__).resolve().parents[1]
        for relative, expected in EXPECTED.items():
            with self.subTest(source=relative):
                source = root / relative
                self.assertTrue(source.is_file(), relative)
                self.assertFalse(source.is_symlink(), relative)
                self.assertEqual(exact_git_blob(source.read_bytes()), expected)


    def test_live_status_url_is_present_in_reviewed_source_but_not_live_proof(self):
        # A local route in source is not proof that public Passenger has
        # reloaded the code. Observe both separately in the owner C95 job.
        root = Path(__file__).resolve().parents[1]
        urls = (root / "config/urls.py").read_text("utf-8")
        views = (root / "core/mojprop_views.py").read_text("utf-8")
        self.assertIn('path("moj-prop-intake/", mojprop_intake', urls)
        self.assertIn('path("moj-prop-status/", mojprop_receipt_status', urls)
        self.assertIn('def mojprop_receipt_status(request):', views)
        self.assertIn('if request.method == "GET":', views)
        self.assertIn('return status_form(request)', views)

    def test_owner_probe_never_claims_live_web_worker_or_accepted_customer(self):
        root = Path(__file__).resolve().parents[1]
        code = (root / "scripts/mojprop_live_intake_source_drift_readonly_c95.py").read_text("utf-8")
        for marker in (
            '"browser_public_endpoint_post_verified": False',
            '"public_runtime_equals_cli_runtime_proven": False',
            '"customer_lead_created": False',
            '"production_release_permitted": False',
            '"customer_data_accessed": False',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, code)
        self.assertNotIn("requests.post(", code)
        self.assertNotIn("objects.create(", code)


if __name__ == "__main__":
    unittest.main()
