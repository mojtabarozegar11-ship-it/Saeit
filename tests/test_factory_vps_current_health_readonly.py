"""Offline regressions for the aggregate-only, read-only factory VPS census."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "scripts/factory_vps_current_health_readonly_20261026.py"
spec = importlib.util.spec_from_file_location("factory_vps_health", SOURCE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class ReadOnlyFactoryHealthTests(unittest.TestCase):
    def test_current_deleted_intake_is_reported_without_regeneration(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "factory-runtime"
            private = base / "private/autonomous-product-cycle"
            ops = base / "operations/production-instructions"
            orders = private / "production-instructions/orders"
            ops.mkdir(parents=True)
            orders.mkdir(parents=True)
            index = private / "production-instructions/owner-agri200-p0-index.json"
            ids = ["WO-00000001", "WO-00000002"]
            index.write_text(json.dumps({"order_ids_ranked": ids}), encoding="utf8")
            (orders / "WO-00000001.json").write_text(json.dumps({
                "id": ids[0], "status": "issued", "fingerprint": "a" * 64
            }), encoding="utf8")
            (ops / "strict-serial-fullcycle-v1.py").write_text("# benign\n", encoding="utf8")
            with patch.object(audit, "BASE", base), patch.object(audit, "PRIVATE", private), \
                 patch.object(audit, "OPS", ops), patch.object(audit, "ORDERS", orders), \
                 patch.object(audit, "INDEX", index), \
                 patch.object(audit.os, "geteuid", return_value=1000), \
                 patch.object(audit, "command", return_value=""):
                result = audit.inventory()
                # An array is valid JSON syntax but never a valid order object.
                (orders / "WO-00000001.json").write_text("[]", encoding="utf8")
                malformed = audit.inventory()
            self.assertEqual(malformed["agri_invalid"], 1)
            self.assertEqual(malformed["current_order_unsafe"], 1)
            self.assertTrue(result["read_only"])
            self.assertEqual(result["server_written_bytes"], 0)
            self.assertEqual(result["agri_index_entries"], 2)
            self.assertEqual(result["agri_existing_valid"], 1)
            self.assertEqual(result["agri_missing"], 1)
            self.assertEqual(result["agri_invalid"], 0)
            self.assertEqual(result["current_order_file_status_counts"], {"issued": 1})
            self.assertFalse((orders / "WO-00000002.json").exists())
            self.assertEqual(len(tuple(orders.iterdir())), 1)
            self.assertNotIn("WO-00000001", json.dumps(result))

    def test_missing_private_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "nonexistent"
            with patch.object(audit, "BASE", root), patch.object(audit, "PRIVATE", root), \
                 patch.object(audit, "OPS", root), patch.object(audit, "ORDERS", root), \
                 patch.object(audit.os, "geteuid", return_value=1000):
                with self.assertRaisesRegex(RuntimeError, "UNSAFE_OR_MISSING"):
                    audit.inventory()


    def test_line41_diagnoses_stale_full_slot_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary)
            slot = private / "quality-excellence/product-flow/active-slots/current.json"
            slot.parent.mkdir(parents=True)
            slot.write_text(json.dumps({
                "schema": audit.SLOT_SCHEMA, "line_id": 41, "capacity": 1,
                "active": [{"recipe": "synth_aaaaaaaaaaaaaaaaaaaaaaaa"}],
                "waiting": ["sheet_bbbbbbbbbbbbbbbbbbbbbbbb"], "exited": {}
            }), encoding="utf8")
            home = private / "generated-product-recipes/synth_aaaaaaaaaaaaaaaaaaaaaaaa"
            home.mkdir(parents=True)
            (home / "design_receipt.json").write_text(json.dumps({
                "schema": "saeit.factory.synthesis-receipt.v1",
                "generator_capability_revision": "verified-one-percent-sensitivity-v6"
            }), encoding="utf8")
            before = slot.read_bytes()
            result = audit.line41_diagnostic(private)
            self.assertEqual(result["slot_state"], "valid")
            self.assertEqual(result["active_count"], 1)
            self.assertEqual(result["waiting_count"], 1)
            self.assertTrue(result["active_details"][0]["compiler_owned"])
            self.assertEqual(result["active_details"][0]["generator_capability_revision"],
                             "verified-one-percent-sensitivity-v6")
            self.assertEqual(before, slot.read_bytes())
            self.assertFalse((private / "digital-products").exists())

    def test_cron_classifier_does_not_emit_private_commands(self):
        sample = ["* * * * * python /private/autonomous-product-runtime # sample",
                  "* * * * * python stage2-research.py --secret=shhh"]
        output = audit.cron_production_channels(sample)
        self.assertEqual(output["autonomous_cycle"], 1)
        self.assertEqual(output["science_stage_workers"], 1)
        self.assertNotIn("shhh", json.dumps(output))



if __name__ == "__main__":
    unittest.main()
