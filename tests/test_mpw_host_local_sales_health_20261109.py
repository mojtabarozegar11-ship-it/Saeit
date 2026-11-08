"""Purely offline checks; no SSH, hosted database, payment, or email access."""

import json
from pathlib import Path
import tempfile
import unittest

import mpw_host_local_sales_health_20261109 as health


class LocalHealthContract(unittest.TestCase):
    def test_discard_sensitive_paid_rows(self):
        result = health.summarize("paid", {
            "paid_intent_count": 2,
            "walletless_persisted_credit_verified": 2,
            "rows": [{"tx_hash": "a_private_hash", "customer_email": "private@example.com"}],
            "sku_scope_counts_examined": {"historical_trial_779": 2},
        })
        data = json.dumps(result)
        self.assertNotIn("a_private_hash", data)
        self.assertNotIn("private@example.com", data)
        self.assertEqual(result["sku_scope_counts_examined"]["historical_trial_779"], 2)

    def test_reject_arbitrary_sku_counts(self):
        with self.assertRaises(ValueError):
            health.summarize("paid", {"sku_scope_counts_examined": {"private@email": 2}})

    def test_parse_marker_requires_exactly_one(self):
        self.assertEqual(health.parse_marker('MPW_PAID_PROVENANCE_READONLY={"ok": true}',
                                             "MPW_PAID_PROVENANCE_READONLY"), {"ok": True})
        with self.assertRaises(ValueError):
            health.parse_marker("unrelated", "MPW_PAID_PROVENANCE_READONLY")

    def test_repeated_marker_is_error(self):
        with self.assertRaises(ValueError):
            health.parse_marker('X={}\nX={}', "X")

    def test_missing_source_returns_status_not_data(self):
        with tempfile.TemporaryDirectory() as dirname:
            result = health.run_probe("cron", "absent.py", "MARKER", 1,
                                      source_dir=Path(dirname))
            self.assertEqual(result, {"status": "missing_verified_source"})

    def test_minimal_fake_probes_produce_aggregate(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            pins = {}
            for name, filename, marker, _ in health.PROBES:
                (root / filename).write_text(
                    "import json\nprint('" + marker + "='+json.dumps(" +
                    repr({"result": "completed", "heartbeat_fresh": True, "paid_intent_count": 0}) + "))\n",
                    encoding="utf-8")
                pins[filename] = health.git_blob_id((root / filename).read_bytes())
            report = health.build_report(source_dir=root, pins=pins)
            self.assertTrue(report["monitor_completed"])
            self.assertFalse(report["operational_evidence_fresh"])
            self.assertFalse(report["commercial_sale_or_customer_delivery_inferred"])

    def test_current_heartbeat_required_for_operational_freshness(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            pins = {}
            for name, filename, marker, _ in health.PROBES:
                (root / filename).write_text(
                    "import json\nprint('" + marker + "='+json.dumps(" +
                    repr({"cron_readable": True, "entry_once_per_minute": True,
                          "heartbeat_fresh": True}) + "))\n",
                    encoding="utf-8")
                pins[filename] = health.git_blob_id((root / filename).read_bytes())
            report = health.build_report(source_dir=root, pins=pins)
            self.assertTrue(report["operational_evidence_fresh"])

    def test_changed_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            file = root / "probe.py"
            file.write_text("print('MARKER={}')", encoding="utf-8")
            previous_pin = health.git_blob_id(file.read_bytes())
            file.write_text("print('MARKER={\"altered\":true}')", encoding="utf-8")
            result = health.run_probe("cron", "probe.py", "MARKER", 1,
                                      source_dir=root, pins={"probe.py": previous_pin})
            self.assertEqual(result["status"], "source_revision_mismatch")

    def test_missing_pin_fails_closed(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "probe.py").write_text("print('MARKER={}')", encoding="utf-8")
            result = health.run_probe("cron", "probe.py", "MARKER", 1,
                                      source_dir=root, pins={})
            self.assertEqual(result["status"], "source_pin_missing")

    def test_atomic_report_private_mode(self):
        with tempfile.TemporaryDirectory() as dirname:
            target = Path(dirname) / "report.json"
            health.write_private_atomic({"monitor_completed": True}, destination=target)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertTrue(json.loads(target.read_text(encoding="utf-8"))["monitor_completed"])

    def test_refuse_symlink_report_target(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            dest = root / "dest.json"
            dest.symlink_to(root / "other.json")
            with self.assertRaises(RuntimeError):
                health.write_private_atomic({}, destination=dest)

    def test_refuse_symlink_source(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            real = root / "real.py"
            real.write_text("print('MARKER={}')", encoding="utf-8")
            link = root / "probe.py"
            link.symlink_to(real)
            self.assertEqual(
                health.run_probe("cron", "probe.py", "MARKER", 1, source_dir=root)["status"],
                "missing_verified_source",
            )


if __name__ == "__main__":
    unittest.main()
