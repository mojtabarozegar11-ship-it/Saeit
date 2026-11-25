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
                         "c792eab57e13044dcb20e71a46dd378e8b946675")


    def test_all_pins_match_exact_reviewed_source_bytes_in_this_commit(self):
        # The C95 production-facing auditor is immutable under its workflow
        # integrity pin. Preserve its historical URL reference as actual bytes.
        # All other unchanged sources still match their original fixed pins.
        root = Path(__file__).resolve().parents[1]
        for relative, expected in EXPECTED.items():
            with self.subTest(source=relative):
                source = root / relative
                if relative in ("config/urls.py", "core/mojprop_accessible_intake.py",
                                "core/mojprop_views.py"):
                    source = root / "docs/mojprop/historical-static-evidence" / (expected + ".py.txt")
                self.assertTrue(source.is_file(), relative)
                self.assertFalse(source.is_symlink(), relative)
                self.assertEqual(exact_git_blob(source.read_bytes()), expected)

    def test_current_intake_view_is_separately_reviewed_without_moving_c95_pin(self):
        # The immutable C95 cPanel evidence still points to its original bytes.
        # A newer source file containing bounded UTM fields, first-party
        # conversion tracking and bounded CRM source labels is inspected
        # separately, not called deployed.
        root = Path(__file__).resolve().parents[1]
        old_pin = EXPECTED["core/mojprop_views.py"]
        archive = root / "docs/mojprop/historical-static-evidence" / (old_pin + ".py.txt")
        current = root / "core/mojprop_views.py"
        self.assertEqual(exact_git_blob(archive.read_bytes()), old_pin)
        self.assertEqual(exact_git_blob(current.read_bytes()),
                         "d69ec8fbf2fb167e716d55ced8abf7952ddcd6aa")
        self.assertNotEqual(exact_git_blob(current.read_bytes()), old_pin)
        src = current.read_text(encoding="utf-8")
        self.assertIn("utm_source", src)
        self.assertIn("utm_campaign", src)
        self.assertIn("record_funnel_event(request, \"lead_submit\")", src)
        self.assertIn("@csrf_protect", src)
        self.assertIn("The endpoint records a request for manual review only.", src)

    def test_current_lead_form_source_references_reviewed_snapshot_without_moving_c95_pin(self):
        root = Path(__file__).resolve().parents[1]
        old_ref = EXPECTED["core/mojprop_accessible_intake.py"]
        historical = root / "docs/mojprop/historical-static-evidence" / (old_ref + ".py.txt")
        current = root / "core/mojprop_accessible_intake.py"
        self.assertEqual(exact_git_blob(historical.read_bytes()), old_ref)
        # The archived C95 reference remains the true source used for the
        # original production comparison; the new PR is NOT a cPanel release.
        # The updated reviewed source additionally allows three bounded unpaid
        # product enquiries; immutable historical C95 deployment pin stays fixed.
        candidate = current.read_bytes()
        # The live-facing form adds catalog-backed signal-plan selection.
        # The historical C95 audit and old release bytes remain immutable.
        self.assertEqual(exact_git_blob(candidate),
                         "dbe747c0f451f0d173872fdd2929a71b3267fadd")
        self.assertIn(b"Starter30", candidate)
        self.assertIn(b"csrfmiddlewaretoken", candidate)
        self.assertIn(b"consent", candidate)
        old_reviewed_signal = (root / "tests/fixtures/mojprop_signal_prefill_reviewed_source_c8e6de.py.txt").read_bytes()
        self.assertEqual(exact_git_blob(old_reviewed_signal),
                         "c8e6de24ce4d9573395a64222d198be48d989f1b")
        self.assertNotEqual(candidate, old_reviewed_signal)
        # Prove the older signal-only release version still reverses exactly
        # to its original reviewed base. Do NOT pin it to the new UI version.
        approved_addition = ("    if service == \"signals\" and not packages:\n        # This is user-editable suggested copy for a FREE enquiry only.\n        # The submitted CRM request still requires explicit consent,\n        # real contact details, CSRF, validation and server-side acceptance.\n        return service, (\n            \"Please send the free written terms for the educational Signal Desk: \"\n            \"covered markets, market-scenario examples, risk disclosures, \"\n            \"delivery frequency, proposed pricing and cancellation conditions. \"\n            \"I understand this is only a request for information, not a paid \"\n            \"subscription, executed trade or guaranteed trading result.\"\n        )\n").encode("utf-8")
        self.assertEqual(old_reviewed_signal.count(approved_addition), 1)
        previous = old_reviewed_signal.replace(approved_addition, b"", 1)
        self.assertEqual(exact_git_blob(previous),
                         "ee4374977fa82cf80df1244f4617dc1a689c061b")
        self.assertNotEqual(exact_git_blob(current.read_bytes()), old_ref)

    def test_current_url_source_exact_delta_without_changing_historical_auditor(self):
        root = Path(__file__).resolve().parents[1]
        old_pin = "bdf2b2048c6a3605808cd5029c68b931d10aeaed"
        self.assertEqual(EXPECTED["config/urls.py"], old_pin)
        archive = root / "docs/mojprop/historical-static-evidence" / (old_pin + ".py.txt")
        current = root / "config/urls.py"
        self.assertEqual(exact_git_blob(archive.read_bytes()), old_pin)
        self.assertEqual(exact_git_blob(current.read_bytes()),
                         "780d2d78d9feeadb63bb488ae301c36d36caadab")
        source = current.read_text(encoding="utf-8")
        self.assertIn("def _host_aware_home(request):", source)
        self.assertIn('if host in {"mojprop.top", "www.mojprop.top"}:', source)
        self.assertIn('path("", _host_aware_home, name="home")', source)

