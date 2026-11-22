"""Pure, offline and exact-source regression tests for production module parity."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import contextlib
import importlib.util
import io

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/mpw_mojprop_source_bundle_parity_20261122.py"
SPEC = importlib.util.spec_from_file_location("mpw_mojprop_parity_reader", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class MojPropProductionSourceBundleEvidenceTests(TestCase):
    def fill(self, root: Path) -> None:
        for relative in MOD.REQUIRED:
            dst = root / relative
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes((ROOT / relative).read_bytes())

    def test_01_exact_five_mainline_blobs_are_pinned(self):
        self.assertEqual(len(MOD.REQUIRED), MOD.EXPECTED_COUNT)
        self.assertEqual(set(MOD.REQUIRED), {
            "prop_firm/simulation_policy.py",
            "prop_firm/starter30_paid_admission.py",
            "prop_firm/policy_integrity.py",
            "prop_firm/starter30_live.py",
            "prop_firm/customer_portal_views.py",
        })
        for relative, digest in MOD.REQUIRED.items():
            with self.subTest(relative=relative):
                self.assertEqual(MOD.git_blob((ROOT / relative).read_bytes()), digest)

    def test_02_empty_app_is_blocked_as_all_missing(self):
        with TemporaryDirectory() as tmp:
            report = MOD.check_bundle(Path(tmp))
            self.assertFalse(report["source_bundle_matches"])
            self.assertEqual(report["missing"], 5)
            self.assertEqual(report["matched"], 0)
            self.assertEqual(report["written_live_changes"], 0)

    def test_03_all_five_exact_files_match_with_no_side_effect(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fill(root)
            before = {rel: (root / rel).stat().st_mtime_ns for rel in MOD.REQUIRED}
            report = MOD.check_bundle(root)
            self.assertTrue(report["source_bundle_matches"])
            self.assertEqual(report["matched"], 5)
            self.assertFalse(report["worker_reload_proven"])
            self.assertFalse(report["financial_release_proven"])
            after = {rel: (root / rel).stat().st_mtime_ns for rel in MOD.REQUIRED}
            self.assertEqual(before, after)

    def test_04_single_changed_policy_fails_entire_bundle(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fill(root)
            policy = root / "prop_firm/simulation_policy.py"
            policy.write_bytes(policy.read_bytes() + b"# drift\n")
            report = MOD.check_bundle(root)
            self.assertEqual(report["drift"], 1)
            self.assertEqual(report["matched"], 4)
            self.assertFalse(report["source_bundle_matches"])

    def test_05_absent_buyer_admission_fails_even_when_other_files_match(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fill(root)
            (root / "prop_firm/starter30_paid_admission.py").unlink()
            report = MOD.check_bundle(root)
            self.assertEqual(report["missing"], 1)
            self.assertEqual(report["matched"], 4)
            self.assertFalse(report["source_bundle_matches"])

    def test_06_symlink_replacement_is_not_silently_accepted(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fill(root)
            path = root / "prop_firm/policy_integrity.py"
            path.unlink()
            path.symlink_to(root / "prop_firm/simulation_policy.py")
            report = MOD.check_bundle(root)
            self.assertEqual(report["unsafe_or_unreadable"], 1)
            self.assertFalse(report["source_bundle_matches"])

    def test_07_cli_check_is_read_only_and_machine_readable(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fill(root)
            buf = io.StringIO()
            with patch.object(MOD, "PUBLIC_EFFECTIVE_ROOT", root):
                with contextlib.redirect_stdout(buf):
                    status = MOD.main(["--check"])
            self.assertEqual(status, 0)
            self.assertIn('"source_bundle_matches": true', buf.getvalue())
            self.assertEqual(len(list(root.rglob("*.py"))), 5)

    def test_08_no_mutation_mode_is_available(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(MOD, "PUBLIC_EFFECTIVE_ROOT", root):
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(MOD.main(["--apply"]), 64)
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    import unittest
    unittest.main()
