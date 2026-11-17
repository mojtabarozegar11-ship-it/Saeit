"""C162 synthetic-only, no real database, safe MySQL metadata regression."""
from __future__ import annotations
from decimal import Decimal
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import mojprop_c162_owner_mysql_metadata_size_readonly as q


class FakeCursor:
    def __init__(self, row):
        self.row = row
        self.executed = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, sql):
        self.executed.append(sql)
    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, row):
        self.fake_cursor = FakeCursor(row)
    def cursor(self):
        return self.fake_cursor


class MySQLMetadataOnlyTests(unittest.TestCase):
    def test_01_realistic_mysql_stats_are_approximate_not_dump_size(self):
        r=q.classify_aggregate((42, 250000, 100000))
        self.assertEqual(r["visible_base_tables"],42)
        self.assertEqual(r["approx_total_bytes"],350000)
        self.assertFalse(r["dump_size_predicted_exactly"])
        self.assertTrue(r["metadata_only"])

    def test_02_fixed_query_only_information_schema(self):
        conn=FakeConnection((10,12345,6789))
        out=q.read_one_mysql_aggregate(conn)
        self.assertEqual(out["approx_total_bytes"],19134)
        self.assertEqual(conn.fake_cursor.executed,[q.SQL])
        self.assertIn("information_schema.TABLES",q.SQL)
        self.assertIn("TABLE_SCHEMA = DATABASE()",q.SQL)
        self.assertIn("TABLE_TYPE = 'BASE TABLE'",q.SQL)

    def test_03_no_customer_table_queries_or_dynamic_db_name(self):
        lower=q.SQL.lower()
        for bad in ("core_customer","select *","delete ","insert ",
                    "update ","create ","drop ","truncate ","lock tables"):
            self.assertNotIn(bad,lower)
        self.assertEqual(q.SQL.count("SELECT "),1)

    def test_04_decimal_mysql_result_exact_integer_allowed(self):
        r=q.classify_aggregate((Decimal("5"),Decimal("1500"),Decimal("250")))
        self.assertEqual(r["approx_total_bytes"],1750)

    def test_05_fractional_mysql_metadata_rejected(self):
        for row in ((1,1.1,2),(1,Decimal("2.5"),1),(1,3,Decimal("NaN"))):
            self.assertIsNone(q.classify_aggregate(row))

    def test_06_bad_row_shapes_fail_closed(self):
        for row in (None,[],["a",2,3],(1,2),(1,2,3,4),{"tables":3}):
            self.assertIsNone(q.classify_aggregate(row))

    def test_07_negative_and_huge_values_fail_closed(self):
        for row in ((-1,0,0),(1,-1,0),(1,0,-1),
                    (200001,0,0),(1,q.MAX_ESTIMATED_BYTES,1)):
            self.assertIsNone(q.classify_aggregate(row))

    def test_08_boolean_row_never_counts_as_table_count(self):
        for row in ((True,100,1),(1,True,1),(1,100,False)):
            self.assertIsNone(q.classify_aggregate(row))

    def test_09_empty_visible_tables_not_a_database_backup(self):
        r=q.classify_aggregate((0,0,0))
        self.assertEqual(r["visible_base_tables"],0)
        self.assertFalse(r["dump_size_predicted_exactly"])

    def test_10_fixed_staging_root_safe_requires_owner(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            root=home/"Saeit-staging"
            cfg=root/"config"
            cfg.mkdir(parents=True,mode=0o700)
            (cfg/"settings.py").write_text("only fake test")
            os.chmod(cfg/"settings.py",0o600)
            with patch.object(q,"HOME",home),patch.object(q,"ROOT",root):
                self.assertTrue(q.safe_staging(os.geteuid()))
                self.assertFalse(q.safe_staging(os.geteuid()+9999))

    def test_11_symlinked_settings_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            cfg=home/"Saeit-staging/config"
            cfg.mkdir(parents=True,mode=0o700)
            (cfg/"settings.py").symlink_to("/etc/passwd")
            with patch.object(q,"HOME",home),patch.object(q,"ROOT",cfg.parent):
                self.assertFalse(q.safe_staging(os.geteuid()))

    def test_12_world_writable_settings_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            cfg=home/"Saeit-staging/config"
            cfg.mkdir(parents=True,mode=0o700)
            os.chmod(cfg,0o777)
            (cfg/"settings.py").write_text("safe fake test only")
            with patch.object(q,"HOME",home),patch.object(q,"ROOT",cfg.parent):
                self.assertFalse(q.safe_staging(os.geteuid()))

    def test_13_wrong_os_user_never_attempts_sql_or_import_django(self):
        with patch.object(q.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name="not-owner")), \
             patch.object(q,"safe_staging") as preflight:
            result=q.report()
        preflight.assert_not_called()
        self.assertFalse(result["owner_identity_verified"])
        self.assertFalse(result["connection_attempted"])

    def test_14_no_PII_password_or_db_identity_in_sanitized_report(self):
        with patch.object(q.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name="not-owner")):
            result=q.report()
        raw=json.dumps(result)
        self.assertNotIn("database_name", result)
        for private in ("db_password", '"database_name":', "username",
                        "customer_email", "host_name", "secret_key",
                        "file_path", "production_uri"):
            self.assertNotIn(private,raw)

    def test_15_never_infer_backup_restore_from_metadata_counts(self):
        with patch.object(q.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name="not-owner")):
            result=q.report()
        for key in ("mysql_dump_or_archive_created",
                    "mysql_consistent_snapshot_proven",
                    "offhost_encrypted_database_backup_verified",
                    "independent_full_db_app_media_restore_proven",
                    "actual_live_passenger_db_identity_proven",
                    "production_release_authorized",
                    "payment_created","cost_incurred"):
            self.assertFalse(result[key])

    def test_16_no_dump_backup_or_customer_data_IO_api_calls(self):
        src=Path(q.__file__).read_text("utf-8")
        for forbidden in ("subprocess.", "urllib.", "requests.",
                          "socket.", "os.system(", "mysqldump ",
                          "migrate(", "shutil.copy", "tarfile.open",
                          ".read_bytes(", ".read_text(", "DELETE FROM ",
                          "INSERT INTO ", "UPDATE core_", "DROP TABLE"):
            self.assertNotIn(forbidden,src)

if __name__ == "__main__":
    unittest.main()
