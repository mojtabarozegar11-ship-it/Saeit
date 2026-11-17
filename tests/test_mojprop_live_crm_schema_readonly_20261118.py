"""Pure database-metadata-only proof for production CRM schema checker."""
import unittest

from scripts.mojprop_live_crm_schema_readonly_20261118 import (
    REQUIRED, TABLE, evaluate, inspect,
)


class SchemaCompatibilityTests(unittest.TestCase):
    def test_existing_schema_and_one_column_unique_key_can_support_crm_intake(self):
        result = evaluate(list(REQUIRED) + ["updated_at", "internal_note"],
                          [("request_id_uniq", 0, "request_id", 1),
                           ("by_status", 1, "status", 1)])
        self.assertTrue(result["table_exists"])
        self.assertTrue(result["required_columns_present"])
        self.assertTrue(result["single_column_unique_request_id_present"])
        self.assertTrue(result["schema_allows_existing_intake_without_new_migration"])
        self.assertFalse(result["customer_rows_queried"])
        self.assertFalse(result["data_written"])

    def test_absent_table_or_missing_consent_prohibits_compatibility(self):
        absent = evaluate([], [])
        self.assertFalse(absent["table_exists"])
        self.assertFalse(absent["schema_allows_existing_intake_without_new_migration"])
        partial = evaluate(REQUIRED - {"consent"},
                           [("unique", 0, "request_id", 1)])
        self.assertFalse(partial["required_columns_present"])
        self.assertFalse(partial["schema_allows_existing_intake_without_new_migration"])

    def test_composite_unique_or_nonunique_cannot_protect_idempotency(self):
        for indexes in (
            [("combo", 0, "request_id", 1), ("combo", 0, "email", 2)],
            [("not_unique", 1, "request_id", 1)],
            [("broken_position", 0, "request_id", 2)],
        ):
            with self.subTest(indexes=indexes):
                result = evaluate(REQUIRED, indexes)
                self.assertFalse(result["single_column_unique_request_id_present"])
                self.assertFalse(result["schema_allows_existing_intake_without_new_migration"])

    def test_malformed_metadata_fails_closed(self):
        for columns, indexes in (
            (None, []),
            (REQUIRED, [("bad", "no", "request_id", 1)]),
            (REQUIRED, [("bad", 0, 12, 1)]),
            (REQUIRED, [("bad", 0, "request_id")]),
        ):
            with self.subTest(case=(str(columns)[:10], indexes)):
                with self.assertRaises(ValueError):
                    evaluate(columns, indexes)

    def test_inspect_queries_only_metadata_and_uses_select_guard(self):
        class Connection:
            vendor = "mysql"
            def __init__(self):
                self.queries = []
                self.guard = None
                self.connected = False
            def ensure_connection(self):
                self.connected = True
            def execute_wrapper(self, guard):
                self.guard = guard
                class Wrap:
                    def __enter__(inner): return inner
                    def __exit__(inner, *args): return False
                return Wrap()
            def cursor(self):
                outer = self
                class Cursor:
                    def __enter__(self): return self
                    def __exit__(self, *args): return False
                    def execute(self, sql, params):
                        assert outer.connected
                        assert outer.guard is not None
                        assert outer.guard(lambda x, p, *args: None, sql,
                                           params, False, {}) is None
                        assert sql.strip().upper().startswith("SELECT ")
                        assert params == [TABLE]
                        assert "information_schema." in sql
                        outer.queries.append(sql)
                    def fetchall(self):
                        if len(outer.queries) == 1:
                            return [(name,) for name in REQUIRED]
                        return [("unique_request", 0, "request_id", 1)]
                return Cursor()
        connection = Connection()
        result = inspect(connection)
        self.assertEqual(len(connection.queries), 2)
        self.assertTrue(result["schema_allows_existing_intake_without_new_migration"])
        with self.assertRaises(PermissionError):
            connection.guard(lambda *args: None, "DELETE FROM x", [], False, {})

    def test_non_mysql_database_denied(self):
        class Fake:
            vendor = "sqlite"
        with self.assertRaises(ValueError):
            inspect(Fake())


if __name__ == "__main__":
    unittest.main()
