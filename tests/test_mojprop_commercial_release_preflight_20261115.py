"""Static 0042-0045 and owner-gated deployment checks are fail closed."""
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from scripts.mojprop_commercial_release_preflight import (
    _MIGRATIONS, _REQUIRED, _WORKFLOW, CommercialSchemaPreflightDenied,
    main as cli, source_readiness,
)

SOURCE = Path(__file__).resolve().parents[1]


class CommercialReleasePreflightTests(TestCase):
    def setUp(self):
        self.t = TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        for relative in list(_REQUIRED) + [
            "core/migrations/" + file for file, _ in _MIGRATIONS
        ] + [_WORKFLOW]:
            origin = SOURCE / relative
            assert origin.exists(), relative
            dst = self.root / relative
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, dst)

    def test_complete_source_reports_not_production_ready(self):
        report = source_readiness(self.root)
        self.assertTrue(report["source_ready"])
        self.assertFalse(report["production_release_ready"])
        self.assertEqual(len(report["required_migrations"]), 4)
        self.assertIn(_WORKFLOW, report["checked_files"])

    def test_any_missing_commercial_migration_denies_source(self):
        for file, _ in _MIGRATIONS:
            with self.subTest(file=file):
                path = self.root / "core/migrations" / file
                saved = path.read_bytes()
                path.unlink()
                with self.assertRaises(CommercialSchemaPreflightDenied):
                    source_readiness(self.root)
                path.write_bytes(saved)

    def test_wrong_ordered_migration_parent_cannot_pass(self):
        path = self.root / "core/migrations/0044_mojprop_acceptance_evidence.py"
        original = path.read_text("utf-8")
        path.write_text(original.replace(
            "0043_mojprop_digital_inquiry", "0042_mojprop_offer"
        ), "utf-8")
        with self.assertRaisesRegex(
            CommercialSchemaPreflightDenied, "broken commercial migration parent"
        ):
            source_readiness(self.root)

    def test_mojprop_release_job_cannot_be_triggered_by_plain_push(self):
        path = self.root / _WORKFLOW
        content = path.read_text("utf-8")
        path.write_text(content.replace(
            "if: github.event_name == 'workflow_dispatch' && inputs.owner_approved_static_release == true",
            "if: github.event_name == 'push'",
        ), "utf-8")
        with self.assertRaisesRegex(
            CommercialSchemaPreflightDenied, "unsafe automatic"
        ):
            source_readiness(self.root)

    def test_removed_owner_static_approval_denies_release(self):
        path = self.root / _WORKFLOW
        path.write_text(path.read_text("utf-8").replace(
            "&& inputs.owner_approved_static_release == true", ""
        ), "utf-8")
        with self.assertRaises(CommercialSchemaPreflightDenied):
            source_readiness(self.root)

    def test_missing_models_or_public_quote_route_denies(self):
        for name, marker in (
            ("core/models.py", "class MojPropDeliveryEvidence("),
            ("config/urls.py", "moj-prop-quote/<str:token>/"),
            ("core/admin.py", "validate_status_change("),
        ):
            with self.subTest(name=name):
                path = self.root / name
                old = path.read_text("utf-8")
                path.write_text(old.replace(marker, "INCOMPATIBLE"), "utf-8")
                with self.assertRaises(CommercialSchemaPreflightDenied):
                    source_readiness(self.root)
                path.write_text(old, "utf-8")

    def test_symlink_source_or_root_denies(self):
        path = self.root / "core/models.py"
        path.unlink()
        path.symlink_to(SOURCE / "core/models.py")
        with self.assertRaises(CommercialSchemaPreflightDenied):
            source_readiness(self.root)

    def test_command_line_denies_unsigned_db_release(self):
        with patch("sys.stdout"):
            status = cli(["--repo-root", str(self.root), "--verify-release"])
        self.assertEqual(status, 3)

    def test_source_only_cli_is_not_live_authorization(self):
        with patch("sys.stdout") as stream:
            status = cli(["--repo-root", str(self.root)])
        self.assertEqual(status, 0)
        report = json.loads(stream.write.call_args.args[0].rstrip())
        self.assertFalse(report["production_release_ready"])


if __name__ == "__main__":
    import unittest
    unittest.main()
