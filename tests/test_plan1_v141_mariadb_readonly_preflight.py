"""Python 3.11 source-level and fake-cursor proofs for READ-ONLY preflight.

These do not establish a live MariaDB server. The tests prove that this
preflight cannot report release authorization and issues SELECT-only SQL.
"""
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

from prop_firm.plan1_v141_mariadb_preflight import (
    inspect_v141_mariadb_read_only,
    PARENT, TARGET, STATES,
)

ROOT = Path(__file__).resolve().parents[1]


class ReadOnlyCursor:
    def __init__(self, con):
        self.con = con
        self.current = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, parameters=None):
        self.con.statements.append((sql, parameters))
        self.current = len(self.con.statements)
        if self.con.fail_at == self.current:
            raise RuntimeError("DO_NOT_LEAK_SQL_OR_SECRET=super-secret-value")
        if not sql.strip().upper().startswith("SELECT "):
            raise AssertionError("Mutating statement in supposedly read-only preflight")

    def fetchone(self):
        assert self.current == 1
        return self.con.header

    def fetchall(self):
        if self.current == 2:
            return [(x,) for x in self.con.applied]
        assert self.current == 3
        return list(self.con.table_rows)


class ReadOnlyConnection:
    vendor = "mysql"
    def __init__(self, *, version="11.8.9-MariaDB", selected_db="factory_dev",
                 engine="InnoDB", autocommit=1,
                 sql_mode="STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO",
                 applied=(PARENT,), tables=(), locks=True, transactions=True,
                 fail_at=0, header_override=None, vendor="mysql"):
        self.vendor = vendor
        self.features = SimpleNamespace(has_select_for_update=locks,
                                        supports_transactions=transactions)
        self.header = (version,selected_db,engine,autocommit,sql_mode) if header_override is None else header_override
        self.applied = applied
        self.table_rows = tables
        self.statements = []
        self.fail_at = fail_at

    def cursor(self):
        return ReadOnlyCursor(self)


def verdict(**overrides):
    con=ReadOnlyConnection(**overrides)
    return inspect_v141_mariadb_read_only(con),con


class MariaDBReadOnlyPreflightTests(unittest.TestCase):
    def test_01_expected_parent_only_reports_pending_0009(self):
        x,_=verdict()
        self.assertTrue(x.connected)
        self.assertEqual(x.schema_status,"PENDING")
        self.assertEqual(x.reasons,())

    def test_02_green_read_checks_never_authorize_release_or_migration(self):
        x,_=verdict()
        self.assertTrue(x.read_only_sql_completed)
        self.assertFalse(x.release_authorized)
        self.assertFalse(x.migration_authorized)

    def test_03_no_backup_restore_or_live_db_proof_fabricated(self):
        x,_=verdict()
        self.assertFalse(x.off_host_backup_restored_and_verified)
        self.assertFalse(x.db_disk_capacity_verified)
        self.assertFalse(x.real_mariadb_concurrency_test_verified)
        self.assertFalse(x.migration_rehearsal_verified)

    def test_04_only_select_statements_are_executed(self):
        _,con=verdict()
        self.assertTrue(all(sql.lstrip().upper().startswith("SELECT ") for sql,_ in con.statements))

    def test_05_exact_three_database_read_queries(self):
        _,con=verdict()
        self.assertEqual(len(con.statements),3)

    def test_06_sql_migrations_query_uses_parameter_binding(self):
        _,con=verdict()
        self.assertEqual(con.statements[1][1],("prop_firm",PARENT,TARGET))

    def test_07_schema_table_names_use_parameter_binding(self):
        _,con=verdict()
        self.assertEqual(con.statements[2][1],tuple(sorted(STATES)))

    def test_08_recorded_0009_with_both_tables_is_reported_applied(self):
        x,_=verdict(applied=(PARENT,TARGET),
                    tables=tuple((n,"InnoDB") for n in STATES))
        self.assertEqual(x.schema_status,"APPLIED")
        self.assertEqual(x.reasons,())
        self.assertFalse(x.release_authorized)

    def test_09_missing_table_despite_applied_0009_is_blocked(self):
        x,_=verdict(applied=(PARENT,TARGET),
                    tables=(("prop_firm_propv141simstate","InnoDB"),))
        self.assertIn("recorded_migration_missing_v141_tables",x.reasons)

    def test_10_0009_tables_existing_before_recorded_migration_blocked(self):
        x,_=verdict(tables=(("prop_firm_propv141simstate","InnoDB"),))
        self.assertIn("unregistered_v141_table_collision",x.reasons)

    def test_11_myisam_v141_receipt_table_is_not_acceptable(self):
        x,_=verdict(applied=(PARENT,TARGET),
                    tables=(("prop_firm_propv141simstate","InnoDB"),
                            ("prop_firm_propv141simreceipt","MyISAM")))
        self.assertIn("v141_receipt_tables_not_innodb",x.reasons)

    def test_12_missing_historical_migration_0008_is_blocked(self):
        x,_=verdict(applied=())
        self.assertIn("historical_parent_migration_0008_not_applied",x.reasons)

    def test_13_mysql_8_is_not_mariadb(self):
        x,_=verdict(version="8.4.2-MySQL")
        self.assertIn("actual_server_is_not_mariadb",x.reasons)

    def test_14_mariadb_below_10_6_is_rejected(self):
        x,_=verdict(version="10.5.29-MariaDB")
        self.assertIn("mariadb_10_6_or_newer_required",x.reasons)

    def test_15_mariadb_10_6_boundary_accepted(self):
        x,_=verdict(version="10.6.0-MariaDB")
        self.assertNotIn("mariadb_10_6_or_newer_required",x.reasons)

    def test_16_mariadb_12_series_accepted_when_version_metadata_valid(self):
        x,_=verdict(version="12.0.2-MariaDB")
        self.assertEqual(x.reasons,())

    def test_17_non_mysql_django_backend_rejected_before_opening_cursor(self):
        x,con=verdict(vendor="sqlite")
        self.assertIn("mysql_django_backend_required",x.reasons)
        self.assertEqual(con.statements,[])

    def test_18_row_level_for_update_must_be_supported(self):
        x,_=verdict(locks=False)
        self.assertIn("row_lock_support_not_proven",x.reasons)

    def test_19_rollback_transactions_must_be_supported(self):
        x,_=verdict(transactions=False)
        self.assertIn("database_transaction_support_not_proven",x.reasons)

    def test_20_sql_mode_must_be_strict(self):
        x,_=verdict(sql_mode="NO_ENGINE_SUBSTITUTION")
        self.assertIn("strict_sql_mode_required",x.reasons)

    def test_21_strict_all_tables_mode_also_valid(self):
        x,_=verdict(sql_mode="STRICT_ALL_TABLES")
        self.assertNotIn("strict_sql_mode_required",x.reasons)

    def test_22_default_storage_engine_must_be_innodb(self):
        x,_=verdict(engine="MyISAM")
        self.assertIn("innodb_default_engine_required",x.reasons)

    def test_23_no_selected_db_is_blocked(self):
        x,_=verdict(selected_db=None)
        self.assertIn("no_schema_selected",x.reasons)

    def test_24_autocommit_response_requires_bounded_boolean_like_value(self):
        x,_=verdict(autocommit="not-trusted")
        self.assertIn("autocommit_metadata_unexpected",x.reasons)

    def test_25_metadata_query_exception_fails_closed(self):
        x,_=verdict(fail_at=1)
        self.assertFalse(x.connected)
        self.assertIn("database_read_only_inspection_failed",x.reasons)

    def test_26_migration_table_query_exception_fails_closed(self):
        x,_=verdict(fail_at=2)
        self.assertFalse(x.read_only_sql_completed)

    def test_27_information_schema_query_exception_fails_closed(self):
        x,_=verdict(fail_at=3)
        self.assertFalse(x.read_only_sql_completed)

    def test_28_error_messages_do_not_disclose_secret_driver_exception(self):
        x,_=verdict(fail_at=2)
        self.assertNotIn("super-secret-value",repr(x))
        self.assertFalse(x.release_authorized)

    def test_29_malformed_server_metadata_response_blocks(self):
        x,_=verdict(header_override=("MariaDB",))
        self.assertIn("unexpected_server_metadata_response",x.reasons)

    def test_30_probe_result_is_immutable(self):
        x,_=verdict()
        with self.assertRaises(FrozenInstanceError):
            x.release_authorized=True

    def test_31_probe_does_not_echo_database_name_in_report(self):
        x,_=verdict(selected_db="SECRET_TENANT_DB_NAME")
        self.assertNotIn("SECRET_TENANT_DB_NAME",repr(x))

    def test_32_manual_management_command_compiles_without_executing(self):
        path=ROOT/"prop_firm/management/commands/mojprop_v141_db_preflight.py"
        compile(path.read_text("utf-8"),str(path),"exec")

    def test_33_manual_command_has_no_migration_executor(self):
        path=ROOT/"prop_firm/management/commands/mojprop_v141_db_preflight.py"
        code=path.read_text("utf-8")
        self.assertNotIn("call_command(",code)
        self.assertNotIn("MigrationExecutor(",code)
        self.assertIn("inspect_v141_mariadb_read_only(connection)",code)

    def test_34_preflight_module_compiles_as_python(self):
        path=ROOT/"prop_firm/plan1_v141_mariadb_preflight.py"
        compile(path.read_text("utf-8"),str(path),"exec")

    def test_35_broad_readiness_false_is_explicit(self):
        x,_=verdict()
        self.assertFalse(x.contract_and_broker_legality_verified)
        self.assertFalse(x.migration_authorized)

if __name__=="__main__":
    unittest.main()
