"""Contract tests for private MojPlayWin-only source and series."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import tempfile
import unittest

from command_center.mpw_private_telemetry import (
    FIVE, SIX, ROLE_CODES, TENANT, EVO, snapshot, collect
)


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = datetime(2026, 10, 18, 14, tzinfo=timezone.utc)

    def write(self, rel, value):
        target = self.root / rel
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        raw = {"tenant": TENANT, **value}
        target.write_text(json.dumps(raw), encoding="utf-8")
        target.chmod(0o600)
        return target

    def filled(self, stamp=None):
        stamp = (stamp or self.now).isoformat()
        self.write("v91_verified_main_port_20261018/operator_state/heartbeat.json",
                   {"status": "active_private", "last_master_callback_utc": stamp})
        self.write(EVO + "/gen65_operational_report.json",
                   {"status": "gen65_operational_private", "active_private_generation": 65, "observed_utc": stamp})
        self.write("site_health_v11_port_20261018/last_scan.json",
                   {"observed_utc": stamp, "runs": [{"code": c, "status": "ok"} for c in ROLE_CODES]})
        self.write(EVO + "/robots_execution_20261018.json",
                   {"observed_utc": stamp, "roles": [{"name": n, "status": "ok"} for n in FIVE]})
        self.write(EVO + "/extended_robots_status_20261018.json",
                   {"observed_utc": stamp, "roles": [{"name": n, "status": "ok"} for n in SIX]})
        self.write(EVO + "/all_77_modules_last_run.json",
                   {"observed_utc": stamp, "per_module_capability_registry":
                    [{"module": "module." + str(i), "loaded": True} for i in range(77)]})

    def test_missing_reports_are_never_healthy(self):
        result = snapshot(self.root, self.now)
        self.assertEqual(result["summary"]["healthy"], 0)
        self.assertEqual(result["summary"]["unknown"], 26)
        self.assertFalse(result["history_available"])

    def test_all_77_modules_11_robots_11_roles_and_two_generations(self):
        self.filled()
        result = snapshot(self.root, self.now)
        self.assertEqual(result["summary"]["total"], 103)
        self.assertEqual(sum(x["kind"] == "module" for x in result["items"]), 77)
        self.assertEqual(sum(x["kind"] == "robot" for x in result["items"]), 11)
        self.assertEqual(sum(x["id"].startswith("role_") for x in result["items"]), 11)
        self.assertEqual(result["summary"]["healthy"], 101)
        self.assertEqual(result["summary"]["unknown"], 2)

    def test_old_reports_never_claim_healthy(self):
        self.filled(self.now - timedelta(hours=4))
        result = snapshot(self.root, self.now)
        self.assertEqual(result["summary"]["healthy"], 0)
        self.assertEqual(result["summary"]["stale"], 101)

    def test_cross_tenant_reports_rejected(self):
        self.filled()
        path = self.root / EVO / "gen65_operational_report.json"
        path.write_text(json.dumps({"tenant": "another-site", "status": "gen65_operational_private",
                                     "observed_utc": self.now.isoformat()}))
        self.assertEqual(next(x["state"] for x in snapshot(self.root, self.now)["items"]
                              if x["id"] == "agent_gen65"), "unknown")

    def test_history_collect_and_safe_replay(self):
        self.filled()
        first = collect(self.root, self.now)
        self.assertEqual(first["observed"], 103)
        data = snapshot(self.root, self.now)
        self.assertTrue(data["history_available"])
        self.assertEqual(data["items"][0]["history"][0]["value"], 1)
        collect(self.root, self.now + timedelta(minutes=15))
        data = snapshot(self.root, self.now + timedelta(minutes=15))
        self.assertEqual(len(data["items"][0]["history"]), 2)
        self.assertEqual(data["items"][0]["history"][-1]["value"], 1)

    def test_private_symlinks_refused(self):
        self.filled()
        path = self.root / EVO / "gen65_operational_report.json"
        path.unlink()
        path.symlink_to(self.root / "v91_verified_main_port_20261018/operator_state/heartbeat.json")
        self.assertEqual(next(x["state"] for x in snapshot(self.root, self.now)["items"]
                              if x["id"] == "agent_gen65"), "unknown")
        out = self.root / EVO / "agent_dashboard_telemetry.json"
        out.symlink_to(path)
        with self.assertRaisesRegex(RuntimeError, "SYMLINK"):
            collect(self.root, self.now)


if __name__ == "__main__":
    unittest.main()
