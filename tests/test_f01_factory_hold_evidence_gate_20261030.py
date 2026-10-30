import datetime as dt
import importlib.util
import pathlib
import unittest

p = pathlib.Path(__file__).parents[1] / "scripts" / "f01_factory_hold_evidence_gate_20261030.py"
spec = importlib.util.spec_from_file_location("hold_gate", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
NOW = dt.datetime(2026, 10, 30, 2, 0, tzinfo=dt.timezone.utc)

def fixture():
    a = {"schema": "f01.factory_stop_operator_evidence.v1",
         "operator": {"authorized_console": True, "independent_of_automation": True},
         "escrow": {"sha256": "a" * 64, "offhost_readback": True}, "polls": []}
    for minute in (56, 58):
        row = {"observed_utc": f"2026-10-30T01:{minute}:00Z"}
        row.update({k: 0 for k in m.ZERO_FIELDS})
        row.update({k: True for k in m.REQUIRED_TRUE})
        a["polls"].append(row)
    return a

class GateTests(unittest.TestCase):
    def test_valid_evidence_never_certifies_actual_stop(self):
        r = m.validate(fixture(), NOW)
        self.assertEqual(r["decision"], "REVIEW_READY_ONLY")
        self.assertFalse(r["full_factory_stop_verified"])
    def test_missing_supervisor_inventory_fails_closed(self):
        a = fixture(); a["polls"][1]["supervisor_inventory_complete"] = False
        self.assertEqual(m.validate(a, NOW)["decision"], "NO_GO")
    def test_live_cron_fails_closed(self):
        a = fixture(); a["polls"][1]["active_factory_cron"] = 1
        self.assertEqual(m.validate(a, NOW)["decision"], "NO_GO")
    def test_boolean_is_not_integer_zero(self):
        a = fixture(); a["polls"][0]["active_factory_workers"] = False
        self.assertEqual(m.validate(a, NOW)["decision"], "NO_GO")
    def test_escrow_absent_fails_closed(self):
        a = fixture(); a["escrow"]["offhost_readback"] = False
        self.assertEqual(m.validate(a, NOW)["decision"], "NO_GO")
    def test_poll_too_close_fails_closed(self):
        a = fixture(); a["polls"][1]["observed_utc"] = "2026-10-30T01:56:30Z"
        self.assertEqual(m.validate(a, NOW)["decision"], "NO_GO")
    def test_stale_poll_fails_closed(self):
        a = fixture(); a["polls"][0]["observed_utc"] = "2026-10-29T01:56:00Z"
        self.assertEqual(m.validate(a, NOW)["decision"], "NO_GO")
    def test_no_independent_operator_fails_closed(self):
        a = fixture(); a["operator"]["independent_of_automation"] = False
        self.assertEqual(m.validate(a, NOW)["decision"], "NO_GO")
    def test_wal_unstable_fails_closed(self):
        a = fixture(); a["polls"][0]["db_and_wal_stable"] = False
        self.assertEqual(m.validate(a, NOW)["decision"], "NO_GO")

if __name__ == "__main__":
    unittest.main()
