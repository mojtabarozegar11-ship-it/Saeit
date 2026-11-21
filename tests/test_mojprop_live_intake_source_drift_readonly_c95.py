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
                if relative == "config/urls.py":
                    source = root / "docs/mojprop/historical-static-evidence" / (expected + ".py.txt")
                self.assertTrue(source.is_file(), relative)
                self.assertFalse(source.is_symlink(), relative)
                self.assertEqual(exact_git_blob(source.read_bytes()), expected)

    def test_current_url_source_exact_delta_without_changing_historical_auditor(self):
        root = Path(__file__).resolve().parents[1]
        old_pin = "bdf2b2048c6a3605808cd5029c68b931d10aeaed"
        self.assertEqual(EXPECTED["config/urls.py"], old_pin)
        archive = root / "docs/mojprop/historical-static-evidence" / (old_pin + ".py.txt")
        current = root / "config/urls.py"
        self.assertEqual(exact_git_blob(archive.read_bytes()), old_pin)
        self.assertEqual(exact_git_blob(current.read_bytes()), "325a9c358e94bed5ee3ba673fbd85f836f067c07")
        prior = iter(archive.read_text(encoding="utf-8").splitlines())
        expected_line = next(prior, None)
        additions = []
        for line in current.read_text(encoding="utf-8").splitlines():
            if expected_line is not None and line == expected_line:
                expected_line = next(prior, None)
            else:
                additions.append(line)
        self.assertIsNone(expected_line)
        self.assertEqual(additions, [
            "from core.mpw_legacy_guest_checkout_redirect import legacy_guest_checkout",
            "from prop_firm.starter30_views import starter30_checkout, starter30_status",
            "from services.mpw_trx_public_pages import support_page, terms_page, privacy_page, cookies_page",
            "    path(\"store/product/<int:product_id>/checkout/\", legacy_guest_checkout, name=\"mpw_legacy_guest_checkout_redirect\"),",
            "    path(\"support/\", support_page, name=\"mpw_support\"),",
            "    path(\"terms/\", terms_page, name=\"mpw_terms\"),",
            "    path(\"privacy/\", privacy_page, name=\"mpw_privacy\"),",
            "    path(\"cookies/\", cookies_page, name=\"mpw_cookies\"),",
            "    path(\"mojprop-starter30-checkout/\", starter30_checkout, name=\"mojprop_starter30_checkout\"),",
            "    path(\"mojprop-starter30-status/\", starter30_status, name=\"mojprop_starter30_status\"),",
            "# A source merge cannot expose the paid learner portal. All four independent",
            "# owner-verified production gates must be set explicitly; none defaults on.",
            "if all(",
            "    getattr(_mojprop_settings, flag, False) is True",
            "    for flag in (",
            "        \"MPW_MOJPROP_BUYER_PORTAL_APPROVED\",",
            "        \"MPW_MOJPROP_BUYER_TRANSACTIONAL_EMAIL_APPROVED\",",
            "        \"MPW_MOJPROP_BUYER_SHARED_RATE_LIMIT_VERIFIED\",",
            "        \"MPW_MOJPROP_BUYER_DELIVERY_RECOVERY_VERIFIED\",",
            "    )",
            "):",
            "    from prop_firm.customer_portal_views import buyer_portal",
            "",
            "    urlpatterns += [",
            "        path(\"mojprop-buyer-portal/\", buyer_portal, name=\"mojprop_buyer_portal\"),",
            "    ]",
            "",
        ])
        # Neither a source diff nor a matching historical fixture proves live
        # deployment. The original auditor still reports drift for new bytes.
        self.assertNotEqual(exact_git_blob(current.read_bytes()), old_pin)


if __name__ == "__main__":
    unittest.main()
