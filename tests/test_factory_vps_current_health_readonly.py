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

    def test_quality_returns_separate_active_from_historical_without_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            private = Path(tmp)
            state = {
                "active_product_slot_recipes": ["farm_enterprise_economics"],
                "quality_returns_to_production": {"orders": [
                    {"recipe": "farm_enterprise_economics"},
                    {"recipe": "old_product_a"},
                    {"recipe": "old_product_b"}], "invalid_orders": 2},
                "quality_return_build_candidates": [
                    {"recipe": "farm_enterprise_economics",
                     "status": "source_repair_still_required"},
                    {"recipe": "old_product_a",
                     "status": "awaiting_independent_reinspection"}],
            }
            (private / "production-state.json").write_text(json.dumps(state))
            result = audit.quality_return_scope(private)
            self.assertEqual(result["total_open_quality_returns"], 3)
            self.assertEqual(result["active_product_quality_returns"], 1)
            self.assertEqual(result["other_product_quality_returns"], 2)
            self.assertEqual(result["active_product_build_candidate_status_counts"],
                             {"source_repair_still_required": 1})
            self.assertNotIn("old_product_a", json.dumps(result))
            self.assertNotIn("farm_enterprise_economics", json.dumps(result))


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



    def test_wrapper_schedule_is_classified_as_autonomous_cycle(self):
        rows = ["23 * * * * /bin/bash /private/worker.sh # SAEIT_AUTONOMOUS_PRODUCTS_V2"]
        self.assertEqual(audit.cron_production_channels(rows)["autonomous_cycle"], 1)

    def test_single_product_runner_cron_is_counted_separately(self):
        rows = ["* * * * * /private/single-product-runtime/run-single-product-cycle.sh "
                "# SAEIT_SINGLE_PRODUCT_FACTORY_V1"]
        groups = audit.cron_production_channels(rows)
        self.assertEqual(groups["single_product_runner"], 1)
        self.assertNotIn("/private/", json.dumps(groups))

    def test_single_product_runner_report_does_not_invoke_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "factory-runtime"
            private = base / "private/autonomous-product-cycle"
            ops = base / "operations/production-instructions"
            orders = private / "production-instructions/orders"
            runner = base / "operations/single-product-runtime/run-single-product-cycle.sh"
            runner.parent.mkdir(parents=True)
            runner.write_text("#!/bin/sh\nexit 41\n", encoding="utf8")
            ops.mkdir(parents=True)
            orders.mkdir(parents=True)
            with patch.object(audit, "BASE", base), patch.object(audit, "PRIVATE", private), \
                 patch.object(audit, "OPS", ops), patch.object(audit, "ORDERS", orders), \
                 patch.object(audit.os, "geteuid", return_value=1000), \
                 patch.object(audit, "command", return_value=(
                     "* * * * * /private/single-product-runtime/run-single-product-cycle.sh "
                     "# SAEIT_SINGLE_PRODUCT_FACTORY_V1")):
                result = audit.inventory()
            self.assertEqual(result["single_product_cron_marker_count"], 1)
            self.assertTrue(result["native_single_product_runner"]["present"])
            self.assertEqual(result["native_single_product_runner"]["executable"], False)
            self.assertEqual(result["server_written_bytes"], 0)

    def test_stalled_runner_log_reports_only_redacted_error_classes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ops = base / "operations"
            ops.mkdir()
            log = ops / "single-product-cycle.log"
            secret = "private key path /home/user/secrettoken"
            log.write_text("Traceback (most recent call last):\n"
                           "ModuleNotFoundError: " + secret + "\n"
                           "No such file or directory: " + secret + "\n", encoding="utf8")
            before = log.read_bytes()
            result = audit.native_single_product_log_diagnostic(base)
            self.assertEqual(result["state"], "readable")
            self.assertEqual(result["tail_error_group_counts"]["python_traceback"], 1)
            self.assertEqual(result["tail_error_group_counts"]["module_not_found"], 1)
            self.assertNotIn(secret, json.dumps(result))
            self.assertEqual(log.read_bytes(), before)

    def test_cron_journal_reports_aggregates_and_never_command_text(self):
        raw = ("(githubops) CMD (/private/single-product-runtime/run-single-product-cycle.sh "
               "--secret do-not-print)\n(root) CMD (other)\n"
               "(githubops) CMD (/usr/bin/true)\n")
        with patch.object(audit, "command", return_value=raw):
            result = audit.cron_recent_journal_diagnostic()
        self.assertEqual(result["recent_entry_count"], 3)
        self.assertEqual(result["githubops_job_count"], 2)
        self.assertEqual(result["single_product_job_count"], 1)
        self.assertNotIn("do-not-print", json.dumps(result))

    def test_cron_wrapper_classifier_reports_guards_without_sensitive_path(self):
        runner = ("/home/githubops/factory-runtime/operations/"
                  "single-product-runtime/run-single-product-cycle.sh")
        log = "/home/githubops/factory-runtime/operations/single-product-cycle.log"
        secret = "secret-private-guard"
        row = ("* * * * * test -f /" + secret + " && /usr/bin/timeout 55s "
               + runner + " >> " + log + " 2>&1 # SAEIT_SINGLE_PRODUCT_FACTORY_V1")
        result = audit.single_product_cron_wrapper_diagnostic([row])
        self.assertEqual(result["state"], "classified")
        self.assertEqual(result["extra_shell_and_count"], 1)
        self.assertTrue(result["contains_test_guard"])
        self.assertNotIn(secret, json.dumps(result))

    def test_heartbeat_real_counter_only_and_no_server_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            private = Path(tmp)
            sample = {"schema": "saeit.factory.production-health.v1",
                      "last_cycle_finished_at_utc": "2026-10-27T09:00:00+00:00",
                      "completed_cycles": 47, "new_or_updated_artifacts_this_cycle": 0,
                      "cycle_status": "degraded",
                      "private_token": "NEVER_EMIT"}
            path = private / "production-health.json"
            path.write_text(json.dumps(sample), encoding="utf8")
            before = path.read_bytes()
            report = audit.production_heartbeat(private)
            self.assertEqual(report["completed_cycles"], 47)
            self.assertEqual(report["cycle_status"], "degraded")
            self.assertNotIn("NEVER_EMIT", json.dumps(report))
            self.assertEqual(path.read_bytes(), before)



    def test_actual_cycle_error_categories_do_not_expose_private_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            private = Path(tmp)
            doc = {"schema_version": 1, "cycle_status": "needs_rework",
                   "designer_failures": [
                       {"type": "engineering_rework", "reason": "internal path secret"},
                       {"type": "source_evolution", "reason": "private contents"},
                   ],
                   "research_failures": [{"reason": "raw unpublished study"}],
                   "recipe_admission_failures": [], "quality_failures_this_cycle": [],
                   "built_product_count": 0, "quality_returns_unresolved": 135,
                   "runtime_health": {"status": "ok",
                                      "expected_design_backlog_count": 2,
                                      "fatal_design_failure_count": 0,
                                      "backlog_retained": True,
                                      "secret": "MUST_NOT_ESCAPE"}}
            path = private / "production-state.json"
            path.write_text(json.dumps(doc), encoding="utf8")
            original = path.read_bytes()
            report = audit.cycle_error_buckets(private)
            self.assertEqual(report["designer_failure_types"],
                             {"engineering_rework": 1, "source_evolution": 1})
            self.assertEqual(report["research_failures_count"], 1)
            self.assertEqual(report["quality_returns_unresolved"], 135)
            self.assertEqual(report["runtime_health"]["status"], "ok")
            self.assertEqual(report["runtime_health"]["expected_design_backlog_count"], 2)
            self.assertNotIn("MUST_NOT_ESCAPE", json.dumps(report))
            self.assertNotIn("private contents", json.dumps(report))
            self.assertNotIn("unpublished study", json.dumps(report))
            self.assertEqual(path.read_bytes(), original)



if __name__ == "__main__":
    unittest.main()
