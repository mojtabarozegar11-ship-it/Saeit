"""Capacity preflight only inspects metadata and never performs expansion."""

import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/mojtaba_vps_expansion_preflight.py"
spec = importlib.util.spec_from_file_location("mojtaba_vps_preflight", SCRIPT)
mod = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class VpsExpansionPreflightTests(unittest.TestCase):
    def test_reported_low_space_blocks_expansion(self):
        snap = mod.CapacitySnapshot(20 * mod.GIB, int(1.06 * mod.GIB),
                                    19 * mod.GIB, 300 * mod.MIB)
        report = mod.evaluate_capacity(snap)
        self.assertFalse(report["safe_for_scoped_vps_expansion"])
        self.assertGreater(report["shortfall_bytes"], 0)
        self.assertEqual(report["next_action"],
                         "pause_expansion_review_storage_or_plan_server_migration")
        self.assertFalse(report["hardware_purchase_authorized"])

    def test_enough_free_space_only_opens_approval_gate(self):
        snap = mod.CapacitySnapshot(40 * mod.GIB, 12 * mod.GIB,
                                    28 * mod.GIB, 500 * mod.MIB)
        report = mod.evaluate_capacity(snap)
        self.assertTrue(report["safe_for_scoped_vps_expansion"])
        self.assertEqual(report["next_action"], "review_and_approve_scoped_software_expansion")
        self.assertFalse(report["deployment_performed"])
        self.assertFalse(report["financial_commitment_created"])

    def test_backup_and_reserve_are_both_counted(self):
        snap = mod.CapacitySnapshot(20 * mod.GIB, 3 * mod.GIB,
                                    17 * mod.GIB, mod.GIB)
        result = mod.evaluate_capacity(snap, planned_growth_bytes=0)
        self.assertTrue(result["safe_for_scoped_vps_expansion"])
        self.assertEqual(result["required_available_bytes"], 3 * mod.GIB)

    def test_rejects_negative_or_inconsistent_capacity(self):
        for snap in (
            mod.CapacitySnapshot(0, 0, 0, 0),
            mod.CapacitySnapshot(10, 11, 0, 0),
            mod.CapacitySnapshot(10, 5, 11, 0),
            mod.CapacitySnapshot(10, 5, 2, -1),
        ):
            with self.subTest(snapshot=snap), self.assertRaises(ValueError):
                mod.evaluate_capacity(snap)

    def test_symlinked_database_or_operations_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ops = root / "ops"
            ops.mkdir()
            db = root / "db.sqlite3"
            db.write_bytes(b"sqlite-metadata-only")
            alias = root / "alias"
            alias.symlink_to(db)
            with self.assertRaisesRegex(ValueError, "UNSAFE_SYMLINKED_PATH"):
                mod.collect_capacity(ops, alias)
            ops_alias = root / "ops-alias"
            ops_alias.symlink_to(ops, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "UNSAFE_SYMLINKED_PATH"):
                mod.collect_capacity(ops_alias, db)

    def test_cli_does_not_modify_database_or_create_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / "db.sqlite3"
            db.write_bytes(b"content-stays-untouched")
            before = set(root.iterdir())
            output = io.StringIO()
            with redirect_stdout(output):
                code = mod.main(["--operations-dir", str(root), "--database-file", str(db)])
            report = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(before, set(root.iterdir()))
            self.assertEqual(db.read_bytes(), b"content-stays-untouched")
            self.assertEqual(report["schema"], mod.SCHEMA)


if __name__ == "__main__":
    unittest.main()
