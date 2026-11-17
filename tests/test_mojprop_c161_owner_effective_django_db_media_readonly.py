"""C161 synthetic-only privacy/restore tests; never connect to a customer DB."""
from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import mojprop_c161_owner_effective_django_db_media_readonly as c


def fake_db(engine="django.db.backends.mysql", host="localhost",
            name="private_database", password="secret-that-must-not-leak"):
    return SimpleNamespace(DATABASES={"default": {
        "ENGINE": engine, "HOST": host, "NAME": name, "PASSWORD": password,
        "USER": "private_sql_user"}})


class C161EffectiveConfigPrivacy(unittest.TestCase):
    def test_01_mysql_engine_and_local_host_only(self):
        out=c.classify_database(fake_db())
        self.assertTrue(out["configured"])
        self.assertEqual(out["engine"], "mysql")
        self.assertTrue(out["name_configured"])
        self.assertEqual(out["host_class"], "local_or_default")
        self.assertFalse(out["connection_opened"])

    def test_02_remote_db_host_never_disclosed(self):
        result=c.classify_database(fake_db(host="private-host.example.com"))
        self.assertEqual(result["host_class"], "remote_or_unknown")
        for forbidden in ("private-host","private_database","private_sql_user","secret-that"):
            self.assertNotIn(forbidden, json.dumps(result))

    def test_03_socket_classification_without_socket_path(self):
        d=c.classify_database(fake_db(host="/run/mysqld/private.sock"))
        self.assertEqual(d["host_class"],"local_socket_or_path")
        self.assertNotIn("/run/mysqld",json.dumps(d))

    def test_04_supported_db_types_and_missing_config(self):
        for engine,label in (("django.db.backends.sqlite3","sqlite"),
                             ("django.db.backends.postgresql","postgresql"),
                             ("django.db.backends.oracle","oracle"),
                             ("custom.backend","other_or_unknown")):
            self.assertEqual(c.classify_database(fake_db(engine=engine))["engine"],label)
        self.assertFalse(c.classify_database(SimpleNamespace(DATABASES={} ))["configured"])

    def test_05_in_memory_sqlite_not_a_persistent_backup(self):
        d=c.classify_database(fake_db(engine="django.db.backends.sqlite3", name=":memory:"))
        self.assertFalse(d["name_configured"])
        self.assertFalse(d["connection_opened"])

    def test_06_missing_media_root_is_unproven_not_empty_inventory(self):
        out=c.class_media_path(SimpleNamespace(MEDIA_ROOT="",STORAGES={}), os.geteuid())
        self.assertEqual(out["root_state"],"not_configured")
        self.assertFalse(out["metadata"]["bounded_direct_scan_complete"])
        self.assertFalse(out["complete_media_inventory_proven"])

    def test_07_local_and_custom_storage_backend_labels_only(self):
        self.assertEqual(c.storage_type(SimpleNamespace(
            STORAGES={"default":{"BACKEND":"django.core.files.storage.FileSystemStorage",
                                  "OPTIONS":{"secret":"do-not-emit"}}})),
            "django_filesystem_storage")
        s=c.storage_type(SimpleNamespace(
            STORAGES={"default":{"BACKEND":"private.storage.Cloud",
                                 "OPTIONS":{"access_key":"secret"}}}))
        self.assertEqual(s,"other_or_external_storage")
        self.assertNotIn("private.storage",s)

    def test_08_unsafe_external_media_root_not_scanned(self):
        x=c.class_media_path(SimpleNamespace(MEDIA_ROOT="/etc",
                                              STORAGES={}),os.geteuid())
        self.assertEqual(x["root_state"],"outside_or_overbroad_owner_home")
        self.assertFalse(x["within_owner_home"])

    def test_09_relative_media_root_not_scanned(self):
        x=c.class_media_path(SimpleNamespace(MEDIA_ROOT="uploads",
                                              STORAGES={}),os.geteuid())
        self.assertEqual(x["root_state"],"relative_path_unverified")

    def test_10_bounded_owner_media_metadata_counts_files_without_open(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            root=home/"Saeit-staging"
            root.mkdir(mode=0o700)
            media=root/"media"
            media.mkdir(mode=0o700)
            (media/"private.bin").write_bytes(b"opaque-no-customer-test")
            os.chmod(media/"private.bin",0o600)
            (media/"nested").mkdir(mode=0o700)
            with patch.object(c,"HOME",home),patch.object(c,"ROOT",root):
                out=c.class_media_path(SimpleNamespace(MEDIA_ROOT=media,
                                                        STORAGES={}),os.geteuid())
        self.assertEqual(out["root_state"],"owner_safe_directory")
        self.assertTrue(out["within_staging"])
        self.assertTrue(out["metadata"]["bounded_direct_scan_complete"])
        self.assertEqual(out["metadata"]["direct_files"],1)
        self.assertEqual(out["metadata"]["direct_subdirectories"],1)
        self.assertFalse(out["metadata"]["media_file_content_read"])
        self.assertNotIn("private.bin",json.dumps(out))

    def test_11_media_symlink_to_other_location_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            root=home/"Saeit-staging"
            root.mkdir(mode=0o700)
            (root/"media").symlink_to("/etc")
            with patch.object(c,"HOME",home),patch.object(c,"ROOT",root):
                d=c.class_media_path(SimpleNamespace(MEDIA_ROOT=root/"media",
                                                     STORAGES={}),os.geteuid())
        self.assertEqual(d["root_state"],"unsafe_root")

    def test_12_group_writable_media_parent_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            root=home/"Saeit-staging"
            root.mkdir(mode=0o700)
            os.chmod(root,0o770)  # mkdir mode alone is reduced by CI umask
            (root/"media").mkdir(mode=0o700)
            with patch.object(c,"HOME",home),patch.object(c,"ROOT",root):
                d=c.class_media_path(SimpleNamespace(MEDIA_ROOT=root/"media",
                                                     STORAGES={}),os.geteuid())
        self.assertEqual(d["root_state"],"unsafe_or_missing_ancestor")

    def test_13_more_than_64_entries_cannot_claim_complete_media_inventory(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            root=home/"Saeit-staging"
            root.mkdir(mode=0o700)
            media=root/"media"
            media.mkdir(mode=0o700)
            for i in range(c.MAX_DIRECT_ENTRIES+1):
                (media/f"item{i}").mkdir(mode=0o700)
            with patch.object(c,"HOME",home),patch.object(c,"ROOT",root):
                out=c.class_media_path(SimpleNamespace(MEDIA_ROOT=media,
                                                        STORAGES={}),os.geteuid())
        self.assertFalse(out["metadata"]["bounded_direct_scan_complete"])
        self.assertFalse(out["complete_media_inventory_proven"])

    def test_14_wrong_owner_never_imports_or_reads_staging_config(self):
        with patch.object(c.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name="not-zomorod2")), \
             patch.object(c,"staging_source_safe") as source:
            r=c.report()
        source.assert_not_called()
        self.assertFalse(r["owner_identity_verified"])
        self.assertFalse(r["db_connection_opened"])
        self.assertFalse(r["owner_secret_values_emitted"])

    def test_15_never_claim_live_passenger_or_backup_from_cli_settings(self):
        with patch.object(c.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name="not-zomorod2")):
            out=c.report()
        for key in ("actual_live_passenger_worker_parity_proven",
                    "offhost_db_media_backup_verified",
                    "full_app_db_media_restore_verified",
                    "production_release_authorized",
                    "new_financial_commitment",
                    "database_name_or_credentials_emitted"):
            self.assertFalse(out[key])

    def test_16_no_sql_customer_file_media_content_or_backup_write_calls(self):
        src=Path(c.__file__).read_text("utf-8")
        for forbidden in ("subprocess.", "requests.", "urllib.", "socket.",
                          "connection.cursor(", "sqlite3.connect(", "cursor(",
                          ".read_bytes(", ".read_text(", "os.system(",
                          "shutil.copy", "tarfile.open", "remove("):
            self.assertNotIn(forbidden,src)
        self.assertEqual(c.MAX_DIRECT_ENTRIES,64)

if __name__=="__main__":
    unittest.main()
