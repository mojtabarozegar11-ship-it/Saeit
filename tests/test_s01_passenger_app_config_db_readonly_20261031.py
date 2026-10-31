import unittest

from scripts.s01_passenger_app_config_db_readonly_20261031 import readonly_select1


class Cursor:
    def __init__(self, fail_on=None, row=(1,)):
        self.statements = []
        self.fail_on = fail_on
        self.row = row
        self.closed = False

    def execute(self, sql):
        self.statements.append(sql)
        if sql == self.fail_on:
            raise OSError("synthetic failure")

    def fetchone(self):
        return self.row

    def close(self):
        self.closed = True


class Connection:
    def __init__(self, cursor):
        self.value = cursor

    def cursor(self):
        return self.value


class PassengerAppConfigDbReadonlyTests(unittest.TestCase):
    def test_mysql_only_runs_read_only_transaction_select_and_rollback(self):
        cursor = Cursor()
        result = readonly_select1(
            Connection(cursor), "django.db.backends.mysql", "zomorod2_sites_main"
        )
        self.assertTrue(result["app_settings_readonly_select1_verified"])
        self.assertFalse(result["passenger_worker_db_authority_verified"])
        self.assertFalse(result["database_modified"])
        self.assertFalse(result["migrations_run"])
        self.assertEqual(cursor.statements, [
            "START TRANSACTION READ ONLY", "SELECT 1", "ROLLBACK"
        ])
        self.assertTrue(cursor.closed)

    def test_sqlite_enforces_connection_query_only_and_rolls_back(self):
        cursor = Cursor()
        result = readonly_select1(
            Connection(cursor), "django.db.backends.sqlite3", "zomorod2_sites_main"
        )
        self.assertTrue(result["app_settings_readonly_select1_verified"])
        self.assertEqual(cursor.statements, [
            "PRAGMA query_only = ON", "BEGIN", "SELECT 1", "ROLLBACK"
        ])

    def test_database_scope_mismatch_does_not_connect(self):
        cursor = Cursor()
        result = readonly_select1(
            Connection(cursor), "django.db.backends.mysql", "other_database"
        )
        self.assertEqual(result["failure_class"], "database_scope_mismatch")
        self.assertEqual(cursor.statements, [])

    def test_unknown_backend_does_not_connect(self):
        cursor = Cursor()
        result = readonly_select1(Connection(cursor), "custom.backend", "zomorod2_sites_main")
        self.assertEqual(result["failure_class"], "unsupported_database_backend")
        self.assertEqual(cursor.statements, [])

    def test_failed_readonly_transaction_attempts_rollback(self):
        cursor = Cursor(fail_on="SELECT 1")
        result = readonly_select1(
            Connection(cursor), "django.db.backends.mysql", "zomorod2_sites_main"
        )
        self.assertFalse(result["app_settings_readonly_select1_verified"])
        self.assertFalse(result["database_modified"])
        self.assertEqual(cursor.statements[-1], "ROLLBACK")

    def test_unexpected_result_fails_closed_and_rolls_back(self):
        cursor = Cursor(row=(0,))
        result = readonly_select1(
            Connection(cursor), "django.db.backends.mysql", "zomorod2_sites_main"
        )
        self.assertFalse(result["app_settings_readonly_select1_verified"])
        self.assertEqual(cursor.statements[-1], "ROLLBACK")


if __name__ == "__main__":
    unittest.main()
