"""Offline regression for an exact, reversible site-home signal enquiry CTA.

Uses synthetic HTML and mocks. No public site, filesystem, DB, payment,
social account, email, invoice or hosting process is touched.
"""
import inspect
import io
from contextlib import redirect_stdout
from unittest import TestCase
from unittest.mock import patch

from scripts import mpw_home_signal_proposal_currentsha_20261122 as change


def fictional_pair():
    before = (
        b'<div id="mpw-mojprop-spotlight-20261121">'
        + change.OLD
        + b'</div>'
    )
    after = before.replace(change.OLD, change.NEW, 1)
    return before, after


class HomeSignalProposalCurrentSourceTests(TestCase):
    def test_01_exact_live_origin_pin_and_reversible_expected_bytes(self):
        self.assertEqual(
            change.BASE_SHA256,
            "eadc94648806f728cf6f559932277d45f61227246c6d4ab992e1949286b4766d",
        )
        self.assertEqual(
            change.CANDIDATE_SHA256,
            "b76f16876d093900f6f855c5771f6ff3ebe374450a0c373dcb57f47635e0bc07",
        )
        self.assertEqual(change.CANDIDATE_BYTES - change.BASE_BYTES, 5)
        self.assertEqual(change.NEW.replace(
            b"Request Signal Desk proposal", b"Signal Desk information"
        ), change.OLD)

    def test_02_synthetic_one_anchor_change_has_no_other_byte_mutation(self):
        before, after = fictional_pair()
        with (
            patch.object(change, "BASE_SHA256", change.digest(before)),
            patch.object(change, "CANDIDATE_SHA256", change.digest(after)),
            patch.object(change, "BASE_BYTES", len(before)),
            patch.object(change, "CANDIDATE_BYTES", len(after)),
        ):
            self.assertEqual(change.derive(before), after)
            self.assertEqual(after.replace(change.NEW, change.OLD, 1), before)

    def test_03_wrong_live_source_fails_before_creating_any_backup(self):
        before, after = fictional_pair()
        with self.assertRaisesRegex(ValueError, "SHA"):
            change.derive(before)
        with (
            patch.object(change, "BASE_SHA256", change.digest(before)),
            patch.object(change, "BASE_BYTES", len(before)),
        ):
            with self.assertRaisesRegex(ValueError, "SHA"):
                change.derive(before + b"unreviewed-deploy")

    def test_04_duplicate_link_refused_to_prevent_double_lead_CTA(self):
        before, after = fictional_pair()
        duplicate = before + change.OLD
        with (
            patch.object(change, "BASE_SHA256", change.digest(duplicate)),
            patch.object(change, "BASE_BYTES", len(duplicate)),
        ):
            with self.assertRaisesRegex(ValueError, "absent or repeated"):
                change.derive(duplicate)

    def test_05_missing_spotlight_id_is_an_absolute_hold(self):
        before, after = fictional_pair()
        before = before.replace(b"mpw-mojprop-spotlight-20261121", b"missing-spotlight-anchor")
        with (
            patch.object(change, "BASE_SHA256", change.digest(before)),
            patch.object(change, "BASE_BYTES", len(before)),
        ):
            with self.assertRaisesRegex(ValueError, "spotlight identity"):
                change.derive(before)

    def test_06_check_mode_does_not_make_a_backup_or_replace_a_file(self):
        before, after = fictional_pair()
        output = io.StringIO()
        with (
            patch.object(change, "read_owner_home", return_value=(before, 0o644)),
            patch.object(change, "BASE_SHA256", change.digest(before)),
            patch.object(change, "CANDIDATE_SHA256", change.digest(after)),
            patch.object(change, "BASE_BYTES", len(before)),
            patch.object(change, "CANDIDATE_BYTES", len(after)),
            patch.object(change, "create_0600") as file_writer,
            patch.object(change, "atomic_replace") as replacer,
            redirect_stdout(output),
        ):
            change.execute("--check")
        file_writer.assert_not_called()
        replacer.assert_not_called()
        self.assertIn("READ_ONLY_SOURCE_MATCH", output.getvalue())

    def test_07_old_source_release_path_is_not_reused(self):
        self.assertIn("currentsha", change.BUNDLE.name)
        self.assertNotIn("home-free-signal-cta-20261122", str(change.BUNDLE))
        self.assertEqual(change.BUNDLE.parent, change.PRIVATE)
        self.assertEqual(change.BEFORE.parent, change.BUNDLE)
        self.assertEqual(change.MANIFEST.parent, change.BUNDLE)

    def test_08_unknown_action_cannot_release_or_rollback(self):
        for action in ("", "--deploy", "--force", "--migrate", "--pay"):
            with self.subTest(action=action):
                with self.assertRaises(ValueError):
                    change.execute(action)

    def test_09_no_payment_or_mutating_server_process_in_source(self):
        source = inspect.getsource(change)
        for forbidden in (
            "subprocess.run(", "schema_editor(", "send_mail(",
            "migrate(", "pkill ", "systemctl restart", "DROP TABLE",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("if mode == \"--check\":", source)
        self.assertIn("source SHA changed", source)

    def test_10_original_and_new_strings_refer_to_the_same_consent_form(self):
        self.assertIn(b"/moj-prop-intake/?format=html", change.OLD)
        self.assertIn(b"&amp;service=signals", change.NEW)
        self.assertIn(b"utm_campaign=signals_education_lead_20261121", change.NEW)
        self.assertNotIn(b"send TRX", change.NEW)
        self.assertNotIn(b"free plan", change.NEW)


if __name__ == "__main__":
    import unittest
    unittest.main()
