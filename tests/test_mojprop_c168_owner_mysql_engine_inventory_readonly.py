"""No network, MySQL, filesystem or production side effects."""
import importlib.util
import pathlib
import unittest
from unittest.mock import Mock

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts/mojprop_c168_owner_mysql_engine_inventory_readonly.py"
spec = importlib.util.spec_from_file_location("mojprop_c168_engine", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class AggregationTests(unittest.TestCase):
    def test_all_innodb(self):
        d = mod.classify_engines([("InnoDB", 101)])
        self.assertTrue(d["single_transaction_candidate_only"])
        self.assertFalse(d["consistent_snapshot_proven"])
        self.assertFalse(d["production_identity_proven"])
        self.assertEqual(d["innodb_tables"], 101)

    def test_mixed_engine_halts(self):
        d = mod.classify_engines([("InnoDB", 100), ("MyISAM", 1)])
        self.assertFalse(d["single_transaction_candidate_only"])
        self.assertEqual(d["other_engine_tables"], 1)

    def test_unknown_engine_halts(self):
        d = mod.classify_engines([("InnoDB", 100), (None, 1)])
        self.assertFalse(d["single_transaction_candidate_only"])
        self.assertEqual(d["unknown_engine_tables"], 1)

    def test_non_innodb_halts(self):
        for name in ("MyISAM", "MEMORY", "Aria", "CSV", "BLACKHOLE", "MyRocks", "XtraDB"):
            with self.subTest(name=name):
                self.assertFalse(mod.classify_engines([(name, 101)])["single_transaction_candidate_only"])

    def test_zero_empty_results_halt(self):
        self.assertIsNone(mod.classify_engines([]))

    def test_invalid_outer_containers_halt(self):
        for r in (None, {}, "InnoDB", 5):
            self.assertIsNone(mod.classify_engines(r))

    def test_invalid_row_shapes_halt(self):
        for r in ([("InnoDB",)], [("InnoDB", 1, 3)], ["InnoDB"], [{"InnoDB": 1}]):
            self.assertIsNone(mod.classify_engines(r))

    def test_invalid_engine_values_halt(self):
        for x in (False, 12, b"InnoDB", "", "X" * 49):
            self.assertIsNone(mod.classify_engines([(x, 1)]))

    def test_invalid_counts_halt(self):
        for x in (-1, 0, 1.0, True, None, "1", 200001):
            self.assertIsNone(mod.classify_engines([("InnoDB", x)]))

    def test_duplicate_engine_case_halt(self):
        self.assertIsNone(mod.classify_engines([("INNODB", 4), ("InnoDB", 2)]))

    def test_more_than_max_groups_halt(self):
        self.assertIsNone(mod.classify_engines([(f"engine{i}", 1) for i in range(mod.MAX_ENGINE_TYPES+1)]))

    def test_excessive_table_sum_halt(self):
        self.assertIsNone(mod.classify_engines([("InnoDB", 199999), ("MyISAM", 2)]))

    def test_sql_is_metadata_only(self):
        sql = mod.SQL.upper()
        self.assertIn("INFORMATION_SCHEMA.TABLES", sql)
        self.assertIn("TABLE_SCHEMA = DATABASE()", sql)
        self.assertIn("TABLE_TYPE = 'BASE TABLE'", sql)
        for word in ("INSERT", "UPDATE", "DELETE", "ALTER", "DROP", "CREATE", "FLUSH", "LOCK TABLES", "JOIN CORE", "INTO OUTFILE", "DATABASES"):
            self.assertNotIn(word, sql)

    def test_single_cursor_fixed_query(self):
        cursor = Mock()
        cursor.fetchmany.return_value = [("InnoDB", 101)]
        connection = Mock()
        connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        connection.cursor.return_value.__exit__ = Mock(return_value=False)
        data = mod.read_engines(connection)
        cursor.execute.assert_called_once_with(mod.SQL)
        cursor.fetchmany.assert_called_once_with(mod.MAX_ENGINE_TYPES + 1)
        self.assertEqual(data["visible_base_tables"], 101)

    def test_output_no_table_names_and_no_recovery_claim(self):
        d = mod.classify_engines([("InnoDB", 101)])
        self.assertNotIn("table_names", d)
        self.assertNotIn("database", d)
        self.assertFalse(d["consistent_snapshot_proven"])
        self.assertFalse(d["production_identity_proven"])

    def test_owner_home_paths_pinned(self):
        self.assertEqual(str(mod.HOME), "/home/zomorod2")
        self.assertEqual(str(mod.ROOT), "/home/zomorod2/Saeit-staging")
        self.assertEqual(mod.OWNER, "zomorod2")

    def test_unprivileged_execution_fails_closed(self):
        from unittest.mock import patch
        with patch.object(mod.pwd, "getpwuid", return_value=Mock(pw_name="unprivileged")), patch.object(mod.os, "geteuid", return_value=1234):
            d = mod.report()
        self.assertFalse(d["owner_identity_verified"])
        self.assertFalse(d["database_query_attempted"])
        self.assertFalse(d["production_release_authorized"])


if __name__ == "__main__":
    unittest.main()
