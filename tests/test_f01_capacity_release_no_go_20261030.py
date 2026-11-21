"""Synthetic regression for read-only release triage; no VPS access."""
import datetime as dt
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from f01_capacity_release_no_go_20261030 import evaluate

NOW = dt.datetime(2026, 10, 29, 20, 0, tzinfo=dt.timezone.utc)

def sample():
    return {"schema":"f01-vps-console-readonly.v1", "read_only":True,
            "observed_utc":"2026-10-29T19:55:00+00:00",
            "filesystem":{"target_1":{"state":"OBSERVED","available_bytes":0,"free_bytes":2159009792}},
            "guest":{"cpu_count":3,"loadavg":[138.52,142.57,138.45],"memory":{"MemTotal_kib":4030372}},
            "process_pressure":{"all_process_states":{"D":31},"init_parent_executable_categories":{"shell":142}},
            "cron":{"state":"OBSERVED","factory_per_minute_entries":3,"exact_duplicate_entries":0},
            "queue":{"target_1":{"state":"OBSERVED","entries_at_least":69,"truncated":False}},
            "worker":{"state":"OBSERVED","truncated":False},
            "locks":{"target_1":{"state":"PRESENT"}},
            "sqlite":{"target_1":{"state":"PRESENT"}},
            "backup":{"target_1":{"state":"PRESENT"}},
            "offhost_backup_restored":"NOT_VERIFIED","worker_running_verified":False}

class Triage(unittest.TestCase):
    def test_realistic_blocked_case_and_reserved_gap(self):
        r = evaluate(sample(), NOW)
        self.assertEqual(r["status"], "NO_GO")
        self.assertEqual(r["estimated_privileged_reserved_gap_bytes"], 2159009792)
        self.assertIn("ORDINARY_USER_CAPACITY_BELOW_5GIB_RESERVE", r["reasons"])
        self.assertIn("OFFHOST_RESTORE_NOT_PROVEN", r["reasons"])
        self.assertFalse(r["restart_authorized"])

    def test_stale_snapshot(self):
        s = sample()
        s["observed_utc"] = "2026-10-28T00:00:00+00:00"
        self.assertIn("SNAPSHOT_STALE_OR_FUTURE", evaluate(s, NOW)["reasons"])

    def test_missing_untrusted_data_fails_closed(self):
        r = evaluate({}, NOW)
        self.assertIn("SNAPSHOT_SCHEMA_OR_READONLY_INVALID", r["reasons"])
        self.assertIn("FILESYSTEM_UNOBSERVED", r["reasons"])

    def test_even_healthy_synthetic_data_never_authorizes_restart(self):
        s = sample()
        s["filesystem"]["target_1"].update(available_bytes=8*1024**3,free_bytes=8*1024**3)
        s["guest"].update(cpu_count=8,loadavg=[1,1,1],memory={"MemTotal_kib":8*1024**2})
        s["process_pressure"]["all_process_states"]["D"]=0
        s["process_pressure"]["init_parent_executable_categories"]["shell"]=0
        s["queue"]["target_1"]["entries_at_least"]=0
        s["offhost_backup_restored"]="VERIFIED"
        s["worker_running_verified"]=True
        r = evaluate(s,NOW)
        self.assertEqual(r["reasons"],[])
        self.assertFalse(r["deployment_authorized"])
        self.assertFalse(r["restart_authorized"])

    def test_malformed_nested_telemetry_is_no_go_not_exception(self):
        s = sample()
        s["filesystem"] = ["unexpected"]
        s["guest"] = ["unexpected"]
        s["process_pressure"] = ["unexpected"]
        r = evaluate(s, NOW)
        self.assertIn("FILESYSTEM_UNOBSERVED", r["reasons"])
        self.assertIn("CPU_PRESSURE_UNOBSERVED", r["reasons"])
        self.assertIn("D_STATE_UNOBSERVED", r["reasons"])
        self.assertFalse(r["deployment_authorized"])

    def test_nonfinite_load_and_boolean_resource_values_rejected(self):
        s = sample()
        s["guest"]["loadavg"] = [float("nan")]
        s["guest"]["cpu_count"] = True
        s["guest"]["memory"]["MemTotal_kib"] = True
        s["filesystem"]["target_1"]["available_bytes"] = True
        s["process_pressure"]["all_process_states"]["D"] = True
        r = evaluate(s, NOW)
        self.assertIn("CPU_PRESSURE_UNOBSERVED", r["reasons"])
        self.assertIn("FILESYSTEM_UNOBSERVED", r["reasons"])
        self.assertIn("D_STATE_UNOBSERVED", r["reasons"])
        self.assertIn("PAID_8GIB_RAM_NOT_OBSERVED", r["reasons"])

    def test_missing_cron_queue_lock_db_backup_probes_are_explicit(self):
        s = sample()
        for key in ("cron", "queue", "locks", "sqlite", "backup", "worker"):
            s.pop(key)
        reasons = evaluate(s, NOW)["reasons"]
        for expected in ("CRON_UNOBSERVED", "QUEUE_UNOBSERVED",
                         "LOCK_PROBE_NOT_CONFIGURED", "DB_HEADER_PROBE_NOT_CONFIGURED",
                         "LOCAL_BACKUP_PROBE_NOT_CONFIGURED", "WORKER_SCAN_INCOMPLETE"):
            self.assertIn(expected, reasons)

    def test_orphan_storm_backlog_and_duplicate_cron_are_no_go(self):
        s = sample()
        s["cron"]["exact_duplicate_entries"] = 2
        s["queue"]["target_1"]["truncated"] = True
        s["worker"]["truncated"] = True
        s["guest"]["memory"]["MemAvailable_kib"] = 193256
        reasons = evaluate(s, NOW)["reasons"]
        for expected in ("ORPHAN_SHELL_STORM", "NONEMPTY_QUEUE_NEEDS_WORKER_RECEIPT",
                         "QUEUE_SCAN_TRUNCATED", "CRON_DUPLICATE_ENTRIES",
                         "WORKER_SCAN_INCOMPLETE", "AVAILABLE_RAM_BELOW_512MIB"):
            self.assertIn(expected, reasons)

    def test_malformed_cron_and_queue_cannot_raise_or_authorize(self):
        s = sample()
        s["cron"] = {"state":"OBSERVED", "factory_per_minute_entries":True,
                     "exact_duplicate_entries":-1}
        s["queue"] = {"target_1":{"state":"OBSERVED","entries_at_least":True}}
        r = evaluate(s, NOW)
        self.assertIn("FACTORY_MINUTE_CRON_UNCONFIRMED", r["reasons"])
        self.assertIn("CRON_DUPLICATE_COUNT_UNOBSERVED", r["reasons"])
        self.assertIn("QUEUE_UNOBSERVED", r["reasons"])
        self.assertFalse(r["deployment_authorized"])

    def test_cli_never_returns_go(self):
        p = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1]/"scripts"/"f01_capacity_release_no_go_20261030.py"), "-"], input=json.dumps(sample()), text=True, capture_output=True)
        self.assertEqual(p.returncode,2)
        self.assertEqual(json.loads(p.stdout)["status"],"NO_GO")

if __name__ == "__main__":
    unittest.main()
