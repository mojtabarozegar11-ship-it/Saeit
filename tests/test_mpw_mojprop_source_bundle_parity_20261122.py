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

    def test_01_twelve_mainline_blobs_are_pinned(self):
        self.assertEqual(len(MOD.REQUIRED), MOD.EXPECTED_COUNT)
        self.assertEqual(set(MOD.REQUIRED), {
            "prop_firm/simulation_policy.py",
            "prop_firm/rules.py",
            "prop_firm/simulation_payout.py",
            "prop_firm/starter30_paid_admission.py",
            "prop_firm/policy_integrity.py",
            "prop_firm/starter30_live.py",
            "prop_firm/customer_portal_views.py",
            "prop_firm/models.py",
            "prop_firm/simulation_identity_adapter.py",
            "prop_firm/starter30_checkout_email.py",
            "prop_firm/starter30_receiver_pool.py",
            "config/mojprop_db_router.py",
        })
        for relative, digest in MOD.REQUIRED.items():
            with self.subTest(relative=relative):
                self.assertEqual(MOD.git_blob((ROOT / relative).read_bytes()), digest)

    def test_02_empty_app_is_blocked_as_all_missing(self):
        with TemporaryDirectory() as tmp:
            report = MOD.check_bundle(Path(tmp))
            self.assertFalse(report["source_bundle_matches"])
            self.assertEqual(report["missing"], 12)
            self.assertEqual(report["matched"], 0)
            self.assertEqual(report["written_live_changes"], 0)

    def test_03_all_twelve_exact_files_match_with_no_side_effect(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fill(root)
            before = {rel: (root / rel).stat().st_mtime_ns for rel in MOD.REQUIRED}
            report = MOD.check_bundle(root)
            self.assertTrue(report["source_bundle_matches"])
            self.assertEqual(report["matched"], 12)
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
            self.assertEqual(report["matched"], 11)
            self.assertFalse(report["source_bundle_matches"])

    def test_05_absent_buyer_admission_fails_even_when_other_files_match(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fill(root)
            (root / "prop_firm/starter30_paid_admission.py").unlink()
            report = MOD.check_bundle(root)
            self.assertEqual(report["missing"], 1)
            self.assertEqual(report["matched"], 11)
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
            wsgi = root / "owner-public-wsgi-shim.txt"
            wsgi.write_text(
                "APP='" + str(root) + "'\n"
                "if APP not in sys.path: sys.path.insert(0, APP)\n"
                "os.chdir(APP)\n", encoding="utf-8"
            )
            with patch.object(MOD, "PUBLIC_EFFECTIVE_ROOT", root), patch.object(MOD, "PUBLIC_WSGI", wsgi):
                with contextlib.redirect_stdout(buf):
                    status = MOD.main(["--check"])
            self.assertEqual(status, 0)
            self.assertIn('"source_bundle_matches": true', buf.getvalue())
            self.assertEqual(len(list(root.rglob("*.py"))), 12)

    def test_08_no_mutation_mode_is_available(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(MOD, "PUBLIC_EFFECTIVE_ROOT", root):
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(MOD.main(["--apply"]), 64)
            self.assertEqual(list(root.iterdir()), [])


    def test_09_changed_model_blocks_even_if_policy_matches(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fill(root)
            model = root / "prop_firm/models.py"
            model.write_bytes(model.read_bytes() + b"# mismatched schema\\n")
            report = MOD.check_bundle(root)
            self.assertEqual(report["matched"], 11)
            self.assertEqual(report["drift"], 1)
            self.assertFalse(report["source_bundle_matches"])

    def test_10_missing_identity_adapter_blocks_customer_portal_release(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fill(root)
            (root / "prop_firm/simulation_identity_adapter.py").unlink()
            report = MOD.check_bundle(root)
            self.assertEqual(report["matched"], 11)
            self.assertEqual(report["missing"], 1)
            self.assertFalse(report["source_bundle_matches"])


    def test_11_wrong_public_wsgi_target_fails_even_when_all_sources_match(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fill(root)
            wsgi = root / "mismatched-wsgi-shim.txt"
            wsgi.write_text(
                "APP='/home/zomorod2/old-unreviewed-tree'\n"
                "if APP not in sys.path: sys.path.insert(0, APP)\n"
                "os.chdir(APP)\n", encoding="utf-8"
            )
            buf = io.StringIO()
            with patch.object(MOD, "PUBLIC_EFFECTIVE_ROOT", root), patch.object(MOD, "PUBLIC_WSGI", wsgi):
                with contextlib.redirect_stdout(buf):
                    status = MOD.main(["--check"])
            self.assertEqual(status, 2)
            self.assertIn("effective_public_wsgi_root_unverified", buf.getvalue())
            self.assertEqual(len(list(root.rglob("*.py"))), 12)

    def test_12_wsgi_binding_summary_exposes_only_safe_app_metadata(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "candidate"
            root.mkdir()
            wsgi = Path(tmp) / "passenger_wsgi.py"
            wsgi.write_text(
                "APP='" + str(root) + "'\\n"
                "if APP not in sys.path: sys.path.insert(0, APP)\\n"
                "os.chdir(APP)\\n", encoding="utf-8"
            )
            with patch.object(MOD.os, "geteuid", return_value=wsgi.stat().st_uid):
                summary = MOD.wsgi_binding_summary(wsgi, root)
            self.assertTrue(summary["single_app_assignment"])
            self.assertTrue(summary["matches_expected_root"])
            self.assertEqual(summary["app_root"], str(root))
            self.assertNotIn("contents", summary)

    def test_13_effective_reviewed_root_is_the_cpanel_passenger_target(self):
        self.assertEqual(MOD.PUBLIC_EFFECTIVE_ROOT,
            Path("/home/zomorod2/Saeit-mojprop-candidate-20261122"))
        self.assertEqual(MOD.PUBLIC_WSGI,
            Path("/home/zomorod2/mojplaywin.com/passenger_wsgi.py"))

    def test_14_reviewed_new_invoice_receiver_is_exclusively_owner_approved(self):
        source = (ROOT / "prop_firm/starter30_receiver_pool.py").read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            MOD.REQUIRED["prop_firm/starter30_receiver_pool.py"],
            "505a78b499d1f2f41f77de1c3396f80c826261bd",
        )
        self.assertIn('if getattr(settings, "MPW_MOJPROP_SINGLE_RECEIVER_MODE", False) is not True:', source)
        self.assertIn("return (approved_recipient(),)", source)
        self.assertNotIn("return tuple(values)", source)
        self.assertIn("multiple invoice receivers prohibited", source)
        self.assertIn("non-owner invoice recipient prohibited", source)



if __name__ == "__main__":
    import unittest
    unittest.main()
