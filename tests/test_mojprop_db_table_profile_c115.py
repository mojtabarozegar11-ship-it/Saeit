"""C115 metadata-only MariaDB footprint; no records, DDL, cleanup or customer data."""
import json
import unittest
from decimal import Decimal
from pathlib import Path
from scripts import mojprop_quota_gap_inventory_readonly_c113 as c115

ROOT = Path(__file__).resolve().parents[1]


class AnonymousMariaDbFootprintTests(unittest.TestCase):
    def test_bucketed_top_six_never_exposes_raw_table_names(self):
        rows = [
            ("core_audit_events", 5 * 1024**3, 0),
            ("mojcoin_buildings", 2 * 1024**3, 0),
            ("core_purchase_order", 1024**3, 0),
            ("django_session", 100 * 1024**2, 0),
            ("other_private_customer_table", 2 * 1024**2, 0),
            ("core_research_reports", 100 * 1024**2, 0),
            ("core_signal_bulletin", 100 * 1024**2, 0),
        ]
        report = c115.classify_table_storage(rows)
        dumped = json.dumps(report)
        self.assertEqual(report["status"], "metadata_only")
        self.assertEqual(report["table_count_bucket"], "1-64")
        self.assertEqual(report["largest_six"][0]["class"], "event_and_audit")
        self.assertEqual(report["largest_six"][1]["class"], "gameplay")
        self.assertEqual(report["largest_six"][2]["class"], "payment_and_orders")
        self.assertEqual(report["sum_estimate_mib_bucket"], ">8192")
        for row in rows:
            self.assertNotIn(row[0], dumped)
        self.assertFalse(report["safe_to_delete_tables_identified"])
        self.assertFalse(report["isolated_restore_proven"])

    def test_integers_and_exact_decimal_metadata_only(self):
        rows = [("signal_msg", Decimal(1024**2), Decimal(100))]
        res = c115.classify_table_storage(rows)
        self.assertEqual(res["largest_six"][0]["class"], "signals_and_prop")
        self.assertEqual(res["by_class_mib_bucket"]["signals_and_prop"], "1-64")

    def test_categories_are_limited_and_unknown_names_not_logged(self):
        self.assertEqual(c115.table_class("Any customer‮ sensitive"), "other")
        self.assertEqual(c115.table_class(None), "other")
        self.assertEqual(c115.table_class("core_history_event"), "event_and_audit")
        self.assertEqual(c115.table_class("service_payments"), "payment_and_orders")
        self.assertEqual(c115.table_class("django_session"), "sessions")
        self.assertEqual(c115.table_class("auth_user"), "system_tables")
        for key in c115.TABLE_CLASSES:
            self.assertRegex(key, r"^[a-z_]+$")

    def test_metadata_malformed_shapes_fail_closed(self):
        bad = (None, {}, [], [("abc",)], [("abc", 1, 2, 3)],
               [("abc", True, 2)], [("abc", -1, 1)],
               [("abc", "1", 1)], [("abc", None, 0)],
               [("abc", float("nan"), 1)], [("abc", float("inf"), 1)],
               [(None, 100, 100)])
        for obj in bad:
            with self.subTest(obj=str(obj)[:80]), self.assertRaises(ValueError):
                c115.classify_table_storage(obj)

    def test_unbounded_table_count_cannot_blow_up_logs(self):
        with self.assertRaises(ValueError):
            c115.classify_table_storage([("many", 1, 0)] * 10001)

    def test_source_uses_only_mysql_information_schema_metadata(self):
        src = (ROOT / "scripts/mojprop_quota_gap_inventory_readonly_c113.py").read_text()
        self.assertIn("FROM information_schema.TABLES", src)
        self.assertIn("TABLE_SCHEMA = DATABASE() LIMIT 10001", src)
        self.assertIn("connection.execute_wrapper(select_only)", src)
        self.assertIn('raise PermissionError("non-SELECT metadata blocked")', src)
        self.assertNotIn("SHOW FULL PROCESSLIST", src)
        self.assertNotIn("TRUNCATE TABLE", src)
        self.assertNotIn("OPTIMIZE TABLE", src)
        self.assertNotIn("DELETE FROM", src)

    def test_profile_failure_never_overrides_capacity_hold(self):
        src = (ROOT / "scripts/mojprop_quota_gap_inventory_readonly_c113.py").read_text()
        self.assertIn('result["database_table_profile"] = {"status": "unavailable"}', src)
        self.assertIn('result["db_profile_error_class"] = type(exc).__name__', src)
        self.assertIn('"combined_quota_capacity_sufficient": False', src)
        self.assertIn('"isolated_restore_executed": False', src)
        self.assertIn('"production_deploy_authorized": False', src)

    def test_zero_byte_views_are_not_called_reclaimable_disk(self):
        report = c115.classify_table_storage([("view_without_storage", 0, 0)])
        self.assertEqual(report["largest_six"][0]["mib_bucket"], "0")
        self.assertNotIn("reclaimable", json.dumps(report))


if __name__ == "__main__":
    unittest.main()
