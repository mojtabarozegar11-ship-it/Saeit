"""Offline regression for the actual MariaDB migration/receiver release hold.

Only temporary synthetic local archives and pure assessment functions.
Never accesses customer identities, databases, actual TRON, workers or email.
"""
from __future__ import annotations

import gzip
import hashlib
import inspect
import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from scripts import mojprop_unique_receiver_migration_preflight_readonly_20261121 as audit


class MojPropUniqueReceiverPreflightTests(SimpleTestCase):
    @staticmethod
    def _healthy():
        return dict(
            known_nodes={"0005_optional_payer_wallet", "0006_unique_invoice_receivers"},
            applied={"0005_optional_payer_wallet", "0006_unique_invoice_receivers"},
            target_dependencies={"0005_optional_payer_wallet"},
            model_recipient_unique=True,
            db_recipient_unique=True,
            duplicate_recipient_groups=0,
            backup_archive_verified=True,
            isolated_restore_verified=True,
        )

    def test_clean_isolated_proofs_have_no_schema_blockers(self):
        self.assertEqual(audit._migration_issues(**self._healthy()), ())

    def test_current_live_orphaned_historical_migration_names_block_release(self):
        fixture = self._healthy()
        fixture["applied"].add("0006_ten_plan_enrollment")
        issues = audit._migration_issues(**fixture)
        self.assertIn("historical_applied_migrations_without_installed_sources", issues)

    def test_missing_git_0006_and_missing_applied_0005_block(self):
        fixture = self._healthy()
        fixture["known_nodes"].remove("0006_unique_invoice_receivers")
        fixture["applied"].remove("0005_optional_payer_wallet")
        issues = audit._migration_issues(**fixture)
        self.assertIn("exclusive_receiver_migration_not_present_in_effective_source", issues)
        self.assertIn("fifth_migration_not_both_installed_and_applied", issues)

    def test_wrong_dependency_blocks_release(self):
        fixture = self._healthy()
        fixture["target_dependencies"] = {"0003_payment_table_router_alignment"}
        self.assertIn(
            "exclusive_receiver_migration_dependency_mismatch",
            audit._migration_issues(**fixture),
        )

    def test_current_live_no_unique_recipient_index_blocks_release(self):
        fixture = self._healthy()
        fixture["db_recipient_unique"] = False
        fixture["model_recipient_unique"] = False
        issues = audit._migration_issues(**fixture)
        self.assertIn("live_payment_table_has_no_unique_recipient_index", issues)
        self.assertIn("effective_django_model_allows_reused_recipient", issues)

    def test_unique_txid_or_unique_composite_not_enough(self):
        self.assertFalse(audit._exact_recipient_unique({
            "txid": {"unique": True, "columns": ["txid"]},
            "payer_pair": {"unique": True, "columns": ["recipient", "txid"]},
            "recipient_nonunique": {"unique": False, "columns": ["recipient"]},
        }))
        self.assertTrue(audit._exact_recipient_unique({
            "recipient": {"unique": True, "columns": ["recipient"]},
        }))

    def test_existing_recipient_collision_blocks_without_deduplication(self):
        fixture = self._healthy()
        fixture["duplicate_recipient_groups"] = 2
        self.assertIn(
            "existing_recipient_collisions_need_private_remediation",
            audit._migration_issues(**fixture),
        )

    def test_checksumed_private_logical_dump_is_not_a_restoration(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            sql = (
                b"CREATE TABLE `a` (x int);\n"
                b"CREATE TABLE `b` (y int);\n"
                b"INSERT INTO `a` VALUES (1);\n"
            )
            archive = root / "mojprop-full-logical.sql.gz"
            archive.write_bytes(gzip.compress(sql))
            blob = archive.read_bytes()
            manifest = {
                "gzip_sha256": hashlib.sha256(blob).hexdigest(),
                "sql_sha256": hashlib.sha256(sql).hexdigest(),
                "compressed_bytes": len(blob),
                "uncompressed_bytes": len(sql),
                "tables_in_live_schema": 2,
                "create_table_statements": 2,
                "isolated_restore_verified": True,
            }
            file = root / "manifest.json"
            file.write_text(json.dumps(manifest), encoding="utf-8")
            check = audit._verify_local_backup_manifest(str(file))
            self.assertTrue(check["verified"])
            self.assertFalse(check["restore_verified"])
            fixture = self._healthy()
            fixture["isolated_restore_verified"] = check["restore_verified"]
            self.assertIn(
                "private_isolated_database_restore_not_proven",
                audit._migration_issues(**fixture),
            )
            archive.write_bytes(blob + b"tampered")
            self.assertFalse(audit._verify_local_backup_manifest(str(file))["verified"])

    def test_no_backup_or_fake_restore_receipt_can_authorize_release(self):
        self.assertEqual(
            audit._verify_local_backup_manifest(None),
            {"verified": False, "restore_verified": False},
        )
        fixture = self._healthy()
        fixture["isolated_restore_verified"] = False
        fixture["backup_archive_verified"] = False
        issues = audit._migration_issues(**fixture)
        self.assertIn("complete_independent_logical_backup_not_verified", issues)
        self.assertIn("private_isolated_database_restore_not_proven", issues)

    def test_audit_has_no_ddl_dml_side_effects_or_customer_data_output(self):
        source = inspect.getsource(audit.audit)
        self.assertIn("MigrationLoader(", source)
        self.assertIn("conn.introspection.get_constraints(", source)
        self.assertIn("connections[_DB_ALIAS]", source)
        for forbidden in (
            "schema_editor(", "MigrationExecutor(", ".save(",
            "CREATE DATABASE", "ALTER TABLE", "DELETE FROM", "UPDATE ",
            "INSERT INTO", "migrate(", "send_mail(", "broadcast(", "settings.DATABASES['default']",
        ):
            self.assertNotIn(forbidden, source)
