"""Purely offline checks; no SSH, hosted database, payment, or email access."""

import ast
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

import mpw_host_local_sales_health_20261109 as health


def good_summary(name):
    if name == "cron":
        return {"cron_readable": True, "entry_once_per_minute": True,
                "heartbeat_fresh": True, "observed_run_count_last_five_minutes": 3,
                "cron_heartbeat_distinguished_from_manual": True,
                "last_reconciler_success": True}
    if name == "paid":
        return {"paid_intent_count": 2, "rows_examined": 2,
                "walletless_persisted_credit_verified": 1, "truncated": False,
                "customer_download_e2e_performed": False,
                "independent_mainnet_recheck_performed": False,
                "production_db_writes": False}
    if name == "flags":
        return {"checkout_scope": "cryptocurrency_only",
                "payment_flow_assessment": "NOT_TESTED_BY_READ_ONLY_PROBE",
                "live_paid_end_to_end_verified_by_this_probe": False,
                "private_data_emitted": False,
                "crypto_runtime_feature_flags": {"downloads": True, "settlement": False}}
    raise ValueError("unexpected_probe")


class LocalHealthContract(unittest.TestCase):
    def test_discard_sensitive_paid_rows(self):
        payload = good_summary("paid") | {
            "rows": [{"tx_hash": "a_private_hash", "customer_email": "private@example.com"}],
            "sku_scope_counts_examined": {"historical_trial_779": 2},
        }
        result = health.summarize("paid", payload)
        data = json.dumps(result)
        self.assertNotIn("a_private_hash", data)
        self.assertNotIn("private@example.com", data)
        self.assertEqual(result["sku_scope_counts_examined"]["historical_trial_779"], 2)

    def test_reject_arbitrary_sku_counts(self):
        with self.assertRaises(ValueError):
            health.summarize("paid", good_summary("paid") |
                             {"sku_scope_counts_examined": {"private@email": 2}})

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
                payload = good_summary(name)
                if name == "cron":
                    payload["heartbeat_fresh"] = False
                (root / filename).write_text(
                    "import json\nprint('" + marker + "='+json.dumps(" +
                    repr(payload) + "))\n",
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
                    repr(good_summary(name)) + "))\n",
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

    def test_reject_email_in_numeric_count(self):
        with self.assertRaises(ValueError):
            health.summarize("paid", good_summary("paid") |
                             {"paid_intent_count": "private@example.invalid"})

    def test_reject_negative_rows(self):
        with self.assertRaises(ValueError):
            health.summarize("paid", good_summary("paid") | {"rows_examined": -10})

    def test_reject_nested_private_flags(self):
        with self.assertRaises(ValueError):
            health.summarize("flags", good_summary("flags") |
                             {"checkout_scope": {"email": "private@example.invalid"}})

    def test_reject_unexpected_dynamic_results(self):
        with self.assertRaises(ValueError):
            health.summarize("paid", good_summary("paid") |
                             {"production_db_writes": {"subject": "private"}})

    def test_reject_missing_required_paid_fields(self):
        with self.assertRaises(ValueError):
            health.summarize("paid", {})

    def test_reject_write_claim_even_if_other_probes_complete(self):
        with self.assertRaises(ValueError):
            health.summarize("paid", good_summary("paid") | {"production_db_writes": True})

    def test_cron_provenance_and_success_required(self):
        from unittest.mock import patch
        def fake_probe(name, *args, **kwargs):
            payload = good_summary(name)
            if name == "cron":
                payload["cron_heartbeat_distinguished_from_manual"] = False
                payload["last_reconciler_success"] = False
            return {"status": "completed", "summary": health.summarize(name, payload)}
        with patch.object(health, "run_probe", side_effect=fake_probe):
            report = health.build_report()
        self.assertFalse(report["operational_evidence_fresh"])

    def test_refuse_world_readable_private_directory(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            os.chmod(root, 0o777)
            try:
                with self.assertRaises(RuntimeError):
                    health.write_private_atomic({}, destination=root / "report.json")
            finally:
                os.chmod(root, 0o700)

    def test_intake_mail_and_visitor_probe_not_executed(self):
        self.assertEqual({name for name, *_ in health.PROBES}, {"cron", "paid", "flags"})

    def test_new_probe_sources_are_revision_pinned(self):
        root = Path(__file__).resolve().parents[1] / "scripts"
        for filename in ("mpw_payment_cron_heartbeat_readonly.py",
                         "mpw_paid_aggregate_readonly_c31.py"):
            self.assertEqual(health.git_blob_id((root / filename).read_bytes()),
                             health.PINNED_SOURCE_BLOBS[filename])

    def test_paid_aggregate_source_only_emits_counts(self):
        """Execute only the parsed pure run() function with synthetic ORM stubs."""
        source = (Path(__file__).resolve().parents[1] / "scripts" /
                  "mpw_paid_aggregate_readonly_c31.py").read_text(encoding="utf-8")
        func = next(n for n in ast.parse(source).body
                    if isinstance(n, ast.FunctionDef) and n.name == "run")

        class Intent:
            provider = "test-provider"
            order = "PRIVATE_ORDER_DO_NOT_LOG"

        class FakeQuery:
            def filter(self, **kwargs): return self
            def select_related(self, *args): return self
            def order_by(self, *args): return self
            def count(self): return 2
            def __getitem__(self, key): return [Intent(), Intent()]

        class FakeModel:
            objects = FakeQuery()

        namespace = {"PaymentIntent": FakeModel, "PROVIDER": "test-provider",
                     "verified_walletless_credit": lambda order, intent: True,
                     "json": json}
        exec(compile(ast.Module(body=[func], type_ignores=[]), "aggregate_run", "exec"),
             namespace)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            namespace["run"]()
        line = output.getvalue()
        self.assertNotIn("PRIVATE_ORDER_DO_NOT_LOG", line)
        self.assertTrue(line.startswith("MPW_PAID_AGGREGATE_READONLY="))
        payload = json.loads(line.split("=", 1)[1])
        self.assertEqual(payload["walletless_persisted_credit_verified"], 2)
        self.assertEqual(set(payload), set(health.REQUIRED["paid"]))

    def test_cron_log_classification_rejects_disabled_and_failures(self):
        source = (Path(__file__).resolve().parents[1] / "scripts" /
                  "mpw_payment_cron_heartbeat_readonly.py").read_text(encoding="utf-8")
        func = next(n for n in ast.parse(source).body
                    if isinstance(n, ast.FunctionDef)
                    and n.name == "classify_reconciler_line")
        namespace = {}
        exec(compile(ast.Module(body=[func], type_ignores=[]), "cron_classify", "exec"),
             namespace)
        classify = namespace["classify_reconciler_line"]
        self.assertEqual(classify("reconcile_MPW_COMMERCE_RECONCILE_state=idle"),
                         (True, False))
        self.assertEqual(classify("reconcile_MPW_COMMERCE_RECONCILE_state=scanned"),
                         (True, False))
        self.assertEqual(classify("reconcile_MPW_COMMERCE_RECONCILE_state=disabled"),
                         (False, True))
        self.assertEqual(classify("reconcile_MPW_COMMERCE_RECONCILE_state=scanned reconcile_exception"),
                         (False, True))


if __name__ == "__main__":
    unittest.main()

