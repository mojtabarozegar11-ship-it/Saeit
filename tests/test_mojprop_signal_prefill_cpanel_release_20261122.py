"""Offline strict candidate release tests. All writes use TemporaryDirectory.

The real effective cPanel source is NEVER written/read by these tests.
The reference main-branch candidate is reversed in memory for the fixture.
"""
from pathlib import Path
import importlib.util
import json
import stat
import tempfile
from unittest import TestCase
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/mojprop_signal_prefill_cpanel_release_20261122.py"
spec = importlib.util.spec_from_file_location("mojprop_intake_release_candidate", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ExactMojPropFreeSignalSourceTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Preserve the exact historic input/output of this old release
        # utility as a fixture; current main has a newer form UX contract.
        cls.after = (ROOT / "tests/fixtures/mojprop_signal_prefill_reviewed_source_c8e6de.py.txt").read_bytes()
        cls.current = (ROOT / "core/mojprop_accessible_intake.py").read_bytes()
        cls.before = cls.after.replace(mod.ADDITION + mod.ANCHOR, mod.ANCHOR, 1)

    def test_01_exact_reviewed_source_candidate_and_back_reversal(self):
        self.assertEqual(self.after.count(mod.ADDITION + mod.ANCHOR), 1)
        self.assertEqual(mod.git_blob(self.before), mod.BASE_BLOB)
        self.assertEqual(mod.sha256(self.before), mod.BASE_SHA256)
        self.assertEqual(mod.git_blob(self.after), mod.NEXT_BLOB)
        self.assertEqual(mod.sha256(self.after), mod.NEXT_SHA256)
        self.assertEqual(mod.candidate(self.before), self.after)

    def test_current_starter30_form_cannot_be_accepted_by_older_signal_release(self):
        # Exact current reviewed form is a different source version: the
        # historical one-off signal script remains fail-closed in production.
        self.assertEqual(mod.git_blob(self.current),
                         "dbe747c0f451f0d173872fdd2929a71b3267fadd")
        self.assertNotEqual(self.current, self.after)
        self.assertIn(b"Starter30", self.current)
        self.assertIn(b"no payment", self.current)
        with self.assertRaisesRegex(RuntimeError, "PINNED_MAINLINE_SOURCE_DRIFT"):
            mod.candidate(self.current)

    def test_02_signals_only_no_fee_invoice_or_other_service_changed(self):
        addition = mod.ADDITION
        self.assertIn(b'if service == "signals" and not packages:', addition)
        self.assertIn(b"not a paid", addition)
        self.assertIn(b"real contact details, CSRF, validation", addition)
        self.assertNotIn(b"wallet", addition)
        self.assertNotIn(b"invoice", addition)
        self.assertEqual(self.after.replace(addition + mod.ANCHOR, mod.ANCHOR, 1),
                         self.before)

    def test_03_rejects_duplicate_unreviewed_bytes_or_pretend_already_live(self):
        for bad in (self.after, self.before + b"unrelated",
                    self.before.replace(mod.ANCHOR, b"unknown"),
                    self.before + mod.ADDITION):
            with self.subTest(length=len(bad)):
                with self.assertRaises(RuntimeError):
                    mod.candidate(bad)

    def test_04_check_is_readonly_then_scoped_backup_apply_and_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "mojprop_accessible_intake.py"
            private = root / "private"
            private.mkdir(mode=0o700)
            target_dir = private / "signal"
            source.write_bytes(self.before)
            source.chmod(0o644)
            kwargs = dict(TARGET=source, PRIVATE_ROOT=private,
                          BACKUP_DIR=target_dir,
                          BACKUP=target_dir / "source.before",
                          MANIFEST=target_dir / "manifest.json")
            with patch.object(mod.getpass, "getuser", return_value="zomorod2"):
                with patch.multiple(mod, **kwargs):
                    mod.execute("--check")
                    self.assertEqual(source.read_bytes(), self.before)
                    self.assertFalse(target_dir.exists())
                    mod.execute("--apply")
                    self.assertEqual(source.read_bytes(), self.after)
                    self.assertEqual(stat.S_IMODE((target_dir / "source.before").stat().st_mode), 0o600)
                    self.assertEqual(stat.S_IMODE((target_dir / "manifest.json").stat().st_mode), 0o600)
                    m = json.loads((target_dir / "manifest.json").read_text())
                    self.assertFalse(m["passenger_reloaded"])
                    self.assertFalse(m["invoice_or_payment_enabled"])
                    with self.assertRaisesRegex(RuntimeError, "PINNED_MAINLINE_SOURCE_DRIFT"):
                        mod.execute("--apply")
                    mod.execute("--rollback")
                    self.assertEqual(source.read_bytes(), self.before)

    def test_05_rollback_refuses_altered_target_after_approved_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source.py"
            private = root / "private"
            private.mkdir(mode=0o700)
            bdir = private / "signal"
            source.write_bytes(self.before)
            kwargs = dict(TARGET=source, PRIVATE_ROOT=private, BACKUP_DIR=bdir,
                          BACKUP=bdir / "before",
                          MANIFEST=bdir / "manifest.json")
            with patch.object(mod.getpass, "getuser", return_value="zomorod2"):
                with patch.multiple(mod, **kwargs):
                    mod.execute("--apply")
                    source.write_bytes(self.after + b"concurrent operator change")
                    with self.assertRaisesRegex(RuntimeError, "ROLLBACK_BUNDLE_OR_EFFECTIVE_SOURCE_CHANGED"):
                        mod.execute("--rollback")
                    self.assertEqual(source.read_bytes(), self.after + b"concurrent operator change")

    def test_06_refuses_wrong_owner_without_reading_target(self):
        with patch.object(mod.getpass, "getuser", return_value="not-owner"):
            with self.assertRaisesRegex(RuntimeError, "INVALID_CPANEL_OWNER"):
                mod.execute("--check")


if __name__ == "__main__":
    import unittest
    unittest.main()
