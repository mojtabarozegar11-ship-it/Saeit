"""Protect the exact Moj Prop 0041–0047 schema target before live writes.

This is source-only and does not attempt a database, hosting or mail operation.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import deploy_mojplaywin_moj_prop_backend as installer
from scripts.mojprop_schema_preflight_c83 import MIGRATIONS, _dependency

CHAIN = [
    "0041_mojprop_request",
    "0042_mojprop_offer",
    "0043_mojprop_digital_inquiry",
    "0044_mojprop_acceptance_evidence",
    "0045_mojprop_delivery_evidence",
    "0046_signal_free_subscription",
    "0047_mpw_guest_email_recovery",
]


class ReviewedMigrationHeadTests(unittest.TestCase):
    def test_reviewed_head_matches_source_graph(self):
        self.assertEqual(list(MIGRATIONS), CHAIN)
        root = Path(__file__).resolve().parents[1]
        for parent, child in zip(CHAIN, CHAIN[1:]):
            with self.subTest(child=child):
                self.assertTrue(
                    _dependency(root / "core/migrations" / (child + ".py"), parent)
                )

    def test_full_target_is_explicit_not_partial_0046(self):
        source = (Path(__file__).resolve().parents[1] /
                  "scripts/deploy_mojplaywin_moj_prop_backend.py").read_text()
        self.assertIn('migration_target = "0047_mpw_guest_email_recovery"', source)
        self.assertIn('"core", migration_target, "--noinput"', source)
        self.assertNotIn('"core", "0046_signal_free_subscription", "--noinput"', source)
        self.assertIn("schema target is stale; release denied", source)

    def test_0047_database_changes_are_guest_email_models_only(self):
        source = (Path(__file__).resolve().parents[1] /
                  "core/migrations/0047_mpw_guest_email_recovery.py").read_text()
        for model in ("GuestOrderEmail", "GuestRecoveryToken", "GuestRecoveryRate"):
            self.assertIn('name="' + model + '"', source)
        self.assertNotIn("RunSQL(", source)
        self.assertNotIn("RunPython(", source)


class PrewriteMigrationMismatchTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.live = root / "live"
        self.staged = root / "staged"
        self.doc = root / "website"
        self.backups = root / "backups"
        for path in (self.live, self.staged, self.doc):
            path.mkdir()
        (self.doc / "passenger_wsgi.py").write_text("path=/Saeit-staging", encoding="utf8")
        for rel in installer.ALL_FILES:
            path = self.staged / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"dummy staged file\n")
        for name, obj in (("ROOT", self.live), ("DOCROOT", self.doc),
                          ("BACKUP_ROOT", self.backups)):
            ctx = patch.object(installer, name, obj)
            ctx.start()
            self.addCleanup(ctx.stop)
        for name in ("backup_target", "run_checked", "restart_passenger",
                     "patch_models", "patch_admin", "atomic_replace"):
            ctx = patch.object(installer, name)
            mock = ctx.start()
            setattr(self, name + "_mock", mock)
            self.addCleanup(ctx.stop)

    def check_denied_without_any_write(self, chain):
        with patch.object(installer, "check_schema_closure",
                          return_value={"source_chain": chain,
                                        "live_db_restored": False,
                                        "manual_deploy_authorized": False}):
            with self.assertRaisesRegex(RuntimeError, "schema target is stale"):
                installer.deploy("123456", "a" * 40, self.staged)
        self.assertFalse(self.backups.exists())
        self.backup_target_mock.assert_not_called()
        self.run_checked_mock.assert_not_called()
        self.atomic_replace_mock.assert_not_called()

    def test_0046_only_does_not_write_or_migrate(self):
        self.check_denied_without_any_write(CHAIN[:-1])

    def test_unknown_0048_head_does_not_write_or_migrate(self):
        self.check_denied_without_any_write(CHAIN + ["0048_unreviewed"])

    def test_reordered_or_duplicate_middle_migration_denied(self):
        self.check_denied_without_any_write(
            CHAIN[:2] + [CHAIN[1]] + CHAIN[2:]
        )

    def test_full_exact_chain_passes_source_prewrite_gate_only(self):
        def halt_before_first_backup(*args, **kwargs):
            raise RuntimeError("STOP_BEFORE_BACKUP_WRITES")
        with patch.object(installer, "check_schema_closure",
                          return_value={"source_chain": list(CHAIN),
                                        "live_db_restored": False,
                                        "manual_deploy_authorized": False}):
            self.backup_target_mock.side_effect = halt_before_first_backup
            with self.assertRaisesRegex(RuntimeError, "STOP_BEFORE_BACKUP_WRITES"):
                installer.deploy("123456", "a" * 40, self.staged)
        self.run_checked_mock.assert_not_called()
        self.atomic_replace_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
