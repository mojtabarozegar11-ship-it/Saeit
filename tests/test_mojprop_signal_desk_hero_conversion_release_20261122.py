"""Offline byte-exact Signal Desk SEO and manual consented enquiry release tests.

No live website, production database, emails, wallets, workers or files used.
"""
import io
from contextlib import redirect_stdout
from unittest import TestCase
from unittest.mock import patch

from scripts import mojprop_signal_desk_hero_conversion_release_20261122 as change


def synthetic_page() -> tuple[bytes, bytes]:
    before = (
        b'<main><section class="hero">' + change.H1_OLD
        + b'<a href="/moj-prop-intake/?format=html&amp;service=signals">Manual</a>'
        + change.EDGE_OLD + b'<footer>Other products must remain untouched</footer>'
    )
    after = before.replace(change.H1_OLD, change.H1_NEW, 1)
    after = after.replace(change.EDGE_OLD, change.EDGE_NEW, 1)
    return before, after


class SignalDeskHeroConversionTests(TestCase):
    def test_01_real_source_and_candidate_sha_pinned(self):
        self.assertEqual(change.BASE_BYTES, 5544)
        self.assertEqual(change.NEXT_BYTES, 6223)
        self.assertEqual(change.BASE_SHA256,
                         "7ebd4931efb3594f334ee5867ab5974db4275742c11b277ae918b94dd32df4c6")
        self.assertEqual(change.NEXT_SHA256,
                         "7ee5d3fb4f57edb3147c304e96c9d15302f480b24f4d3e06fdedfd5e424e3492")

    def test_02_single_hero_change_is_fully_reversible(self):
        before, after = synthetic_page()
        with (
            patch.object(change, "BASE_SHA256", change.digest(before)),
            patch.object(change, "NEXT_SHA256", change.digest(after)),
            patch.object(change, "BASE_BYTES", len(before)),
            patch.object(change, "NEXT_BYTES", len(after)),
        ):
            self.assertEqual(change.candidate_bytes(before), after)
            self.assertEqual(
                after.replace(change.H1_NEW, change.H1_OLD, 1)
                     .replace(change.EDGE_NEW, change.EDGE_OLD, 1),
                before,
            )
        self.assertIn(b"Other products must remain untouched", after)

    def test_03_changed_source_hash_fails_closed(self):
        before, after = synthetic_page()
        with self.assertRaisesRegex(ValueError, "LIVE_SIGNAL_DESK_DRIFT"):
            change.candidate_bytes(before)
        with (
            patch.object(change, "BASE_SHA256", change.digest(before)),
            patch.object(change, "BASE_BYTES", len(before)),
        ):
            with self.assertRaisesRegex(ValueError, "LIVE_SIGNAL_DESK_DRIFT"):
                change.candidate_bytes(before + b"unreviewed")

    def test_04_absent_or_duplicate_headline_fails(self):
        before, after = synthetic_page()
        duplicate = before + change.H1_OLD
        with (
            patch.object(change, "BASE_SHA256", change.digest(duplicate)),
            patch.object(change, "BASE_BYTES", len(duplicate)),
        ):
            with self.assertRaisesRegex(ValueError, "headline"):
                change.candidate_bytes(duplicate)

    def test_05_duplicate_section_anchor_fails(self):
        before, after = synthetic_page()
        duplicate = before + change.EDGE_OLD
        with (
            patch.object(change, "BASE_SHA256", change.digest(duplicate)),
            patch.object(change, "BASE_BYTES", len(duplicate)),
        ):
            with self.assertRaisesRegex(ValueError, "section boundary"):
                change.candidate_bytes(duplicate)

    def test_06_absent_consent_form_url_fails(self):
        before, after = synthetic_page()
        untrusted = before.replace(
            b"/moj-prop-intake/?format=html&amp;service=signals",
            b"/unknown-collection-endpoint/",
        )
        with (
            patch.object(change, "BASE_SHA256", change.digest(untrusted)),
            patch.object(change, "BASE_BYTES", len(untrusted)),
        ):
            with self.assertRaisesRegex(ValueError, "consent form"):
                change.candidate_bytes(untrusted)

    def test_07_check_never_creates_backup_or_writes_public_html(self):
        before, after = synthetic_page()
        stdout = io.StringIO()
        with (
            patch.object(change, "_read_target", return_value=(before, 0o644)),
            patch.object(change, "BASE_SHA256", change.digest(before)),
            patch.object(change, "NEXT_SHA256", change.digest(after)),
            patch.object(change, "BASE_BYTES", len(before)),
            patch.object(change, "NEXT_BYTES", len(after)),
            patch.object(change, "_create_exclusive_private_file") as create,
            patch.object(change, "_atomic_replace") as replace,
            redirect_stdout(stdout),
        ):
            change.execute("--check")
        create.assert_not_called()
        replace.assert_not_called()
        self.assertIn("READ_ONLY_SOURCE_MATCH", stdout.getvalue())

    def test_08_only_supported_actions_accepted(self):
        for mode in ("", "--force", "--migrate", "--pay", "--remove", "--send"):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                change.execute(mode)

    def test_09_public_hero_says_educational_and_not_active(self):
        self.assertIn(b"Educational trading signal examples", change.H1_NEW)
        self.assertIn(b"No payment", change.EDGE_NEW)
        self.assertIn(b"automatic subscription", change.EDGE_NEW)
        self.assertIn(b"explicit consent", change.EDGE_NEW)
        self.assertIn(b"Request written Signal Desk proposal", change.EDGE_NEW)
        self.assertNotIn(b"profit guaranteed", change.EDGE_NEW.lower())

    def test_10_hero_links_to_existing_nonfinancial_intake_and_attribution(self):
        self.assertIn(b"/moj-prop-intake/?format=html&amp;service=signals", change.EDGE_NEW)
        self.assertIn(b"utm_campaign=signal_desk_primary_cta_20261122", change.EDGE_NEW)
        self.assertNotIn(b"/trx-easy/", change.EDGE_NEW)
        self.assertNotIn(b"/mojprop-starter30-checkout", change.EDGE_NEW)

    def test_11_new_text_does_not_add_unapproved_free_challenge_plan(self):
        self.assertNotIn(b"free plan", change.EDGE_NEW.lower())
        self.assertNotIn(b"free challenge", change.EDGE_NEW.lower())
        self.assertNotIn(b"live signal feed is active", change.EDGE_NEW.lower())
        self.assertNotIn(b"funded trading account", change.EDGE_NEW.lower())

    def test_12_backup_paths_are_exclusively_private_and_versioned(self):
        self.assertEqual(change.TARGET.name, "index.html")
        self.assertEqual(change.BUNDLE.parent, change.BACKUP_ROOT)
        self.assertEqual(change.BEFORE.parent, change.BUNDLE)
        self.assertEqual(change.MANIFEST.parent, change.BUNDLE)
        self.assertIn("signal-desk-hero-conversion", change.BUNDLE.name)

    def test_13_rollback_refuses_missing_or_untrusted_private_bundle(self):
        before, after = synthetic_page()
        with (
            patch.object(change, "_read_target", return_value=(after, 0o644)),
            patch.object(change, "BUNDLE") as mock_bundle,
            patch.object(change, "_atomic_replace") as replace,
        ):
            mock_bundle.is_symlink.return_value = False
            mock_bundle.is_dir.return_value = False
            with self.assertRaisesRegex(ValueError, "rollback bundle absent"):
                change.execute("--rollback")
            replace.assert_not_called()

    def test_14_static_release_never_starts_or_reloads_django(self):
        import inspect
        source = inspect.getsource(change)
        for forbidden in (
            "schema_editor(", "subprocess.run(", "send_mail(",
            "from django", "DROP TABLE", "os.system(",
            "pkill ", "systemctl ", "migrate(",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    import unittest
    unittest.main()
