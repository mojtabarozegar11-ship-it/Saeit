"""Regression and failure-safety tests for MojPlayWin's tenant-only one-pass QA."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import tempfile
import unittest

from scripts.mpw_onepass_private_evolution_20261019 import (
    TENANT, EVO, OWN, OUTPUT, ISSUES, FIVE, SIX, ROLES,
    evaluate, run_once, evolve_ledger,
)


class OnePassQualityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "main-private"
        self.root.mkdir(mode=0o700)
        (self.root / EVO).mkdir(mode=0o700)
        self.now = datetime(2026, 10, 19, 11, 0, tzinfo=timezone.utc)

    def write(self, relative, values, tenant=TENANT):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_text(json.dumps({"tenant": tenant, **values}))
        path.chmod(0o600)

    def populate(self, when=None):
        stamp = (when or self.now).isoformat()
        self.write("v91_verified_main_port_20261018/operator_state/heartbeat.json",
                   {"status": "active_private", "last_master_callback_utc": stamp})
        self.write(EVO + "/gen65_operational_report.json",
                   {"status": "gen65_operational_private", "observed_utc": stamp})
        self.write("site_health_v11_port_20261018/last_scan.json",
                   {"observed_utc": stamp, "runs": [{"code": k, "status": "ok"} for k in ROLES]})
        self.write(EVO + "/robots_execution_20261018.json",
                   {"observed_utc": stamp, "roles": [{"name": k, "status": "ok"} for k in FIVE]})
        self.write(EVO + "/extended_robots_status_20261018.json",
                   {"observed_utc": stamp, "roles": [{"name": k, "status": "ok"} for k in SIX]})
        self.write(EVO + "/all_77_modules_last_run.json",
                   {"observed_utc": stamp, "modules_hash_verified": 77,
                    "functional_probes_executed": 14,
                    "per_module_capability_registry": [
                        {"module": "vendor.module_" + str(n), "loaded": True}
                        for n in range(77)]})

    def test_missing_reports_never_marked_healthy(self):
        report = evaluate(self.root, self.now)
        self.assertEqual(report["summary"]["total"], 103)
        self.assertEqual(report["summary"]["healthy"], 0)
        self.assertEqual(report["module_import_count"], 0)
        self.assertEqual(report["summary"]["unknown"], 103)
        self.assertFalse(report["evolution_generation_promoted"])
        self.assertIsNone(report["product_produced_count_verified"])

    def test_real_imports_separate_from_functional_execution(self):
        self.populate()
        report = evaluate(self.root, self.now)
        self.assertEqual(report["summary"]["healthy"], 24)
        self.assertEqual(report["summary"]["loaded_only"], 77)
        self.assertEqual(report["summary"]["unknown"], 2)
        self.assertEqual(report["module_import_count"], 77)
        self.assertEqual(report["legacy_curated_functional_probes"], 14)
        self.assertEqual(report["module_independent_functional_proof_count"], 0)
        self.assertFalse(report["autonomous_master_dispatch_verified"])

    def test_stale_and_cross_tenant_reports_fail_closed(self):
        self.populate(self.now - timedelta(hours=8))
        report = evaluate(self.root, self.now)
        self.assertEqual(report["summary"]["healthy"], 0)
        self.assertEqual(report["summary"]["stale"], 101)
        self.write(EVO + "/all_77_modules_last_run.json",
                   {"observed_utc": self.now.isoformat()}, tenant="other-site")
        report = evaluate(self.root, self.now)
        self.assertEqual(report["module_import_count"], 0)
        self.assertEqual(report["summary"]["unknown"], 79)

    def test_duplicate_and_malformed_inputs_not_success(self):
        self.populate()
        self.write(EVO + "/all_77_modules_last_run.json",
                   {"observed_utc": self.now.isoformat(),
                    "per_module_capability_registry": [
                        {"module": "duplicate", "loaded": True},
                        {"module": "duplicate", "loaded": True},
                        {"module": "x", "loaded": True}]})
        self.write(EVO + "/extended_robots_status_20261018.json",
                   {"observed_utc": self.now.isoformat(), "roles": "bad"})
        report = evaluate(self.root, self.now)
        self.assertEqual(report["summary"]["loaded_only"], 2)
        self.assertEqual(report["summary"]["total"], 103)
        self.assertEqual(report["summary"]["unknown"], 83)

    def test_rework_is_persistent_deduplicated_and_not_fake_execution(self):
        result = run_once(self.root, self.now)
        self.assertEqual(result["component_count"], 103)
        self.assertEqual(result["open_rework_items"], 103)
        ledger_path = self.root / EVO / OWN / ISSUES
        first = json.loads(ledger_path.read_text())
        self.assertEqual(len(first["issues"]), 103)
        run_once(self.root, self.now + timedelta(minutes=15))
        second = json.loads(ledger_path.read_text())
        self.assertEqual(set(first["issues"]), set(second["issues"]))
        self.assertEqual(second["task_executions_claimed"], 0)
        self.assertTrue(second["history_is_never_discarded_for_quality_failure"])
        self.assertEqual(json.loads((ledger_path.parent / OUTPUT).read_text())["tenant"], TENANT)
        self.populate(self.now + timedelta(minutes=30))
        run_once(self.root, self.now + timedelta(minutes=30))
        after = json.loads(ledger_path.read_text())
        self.assertEqual(after["open_rework_items"], 2)
        self.assertEqual(len(after["issues"]), 103)

    def test_symlink_destinations_refused(self):
        foreign = self.root / "foreign"
        foreign.mkdir(mode=0o700)
        (self.root / EVO / OWN).symlink_to(foreign, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "SYMLINK"):
            run_once(self.root, self.now)


if __name__ == "__main__":
    unittest.main()
