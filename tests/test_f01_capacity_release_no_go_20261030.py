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
            "process_pressure":{"all_process_states":{"D":31}},
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
        s["offhost_backup_restored"]="VERIFIED"
        s["worker_running_verified"]=True
        r = evaluate(s,NOW)
        self.assertEqual(r["reasons"],[])
        self.assertFalse(r["deployment_authorized"])
        self.assertFalse(r["restart_authorized"])

    def test_cli_never_returns_go(self):
        p = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1]/"scripts"/"f01_capacity_release_no_go_20261030.py"), "-"], input=json.dumps(sample()), text=True, capture_output=True)
        self.assertEqual(p.returncode,2)
        self.assertEqual(json.loads(p.stdout)["status"],"NO_GO")

if __name__ == "__main__":
    unittest.main()
