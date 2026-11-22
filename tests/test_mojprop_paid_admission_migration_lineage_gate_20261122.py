"""Fail-closed, offline regression of isolated MojProp migration lineage gate.

All data are fictional: no owner database, customer, payment, email, worker
or live service is contacted or changed.
"""
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from prop_firm import starter30_paid_admission as admission
from prop_firm import starter30_live


NEW = set(admission._REQUIRED_ISOLATED_MIGRATIONS)
PAYMENT = "prop_firm_propsimulationpayment"
ROOTS = set(admission._LEGACY_SOURCE_TABLES)


def make_connection(*, applied, tables):
    cursor = Mock()
    cursor.fetchall.return_value = [(name,) for name in sorted(applied)]
    fake = SimpleNamespace(
        cursor=lambda: nullcontext(cursor),
        introspection=SimpleNamespace(table_names=lambda actual_cursor: sorted(tables)),
    )
    return fake, cursor


class MojPropPaidAdmissionMigrationLineageTests(SimpleTestCase):
    def test_01_current_new_migrations_plus_physical_payment_table_are_admissible(self):
        self.assertEqual(
            admission._isolated_migration_lineage_defects(
                applied_names=set(NEW), physical_tables={PAYMENT}
            ), ()
        )

    def test_02_orphaned_legacy_initial_marker_blocks(self):
        defects = admission._isolated_migration_lineage_defects(
            applied_names=NEW | {"0001_initial"}, physical_tables={PAYMENT}
        )
        self.assertIn("historical_migrations_not_backed_by_isolated_schema", defects)

    def test_03_valid_legacy_root_does_not_raise_a_false_orphan(self):
        self.assertEqual(
            admission._isolated_migration_lineage_defects(
                applied_names=NEW | {"0001_initial"},
                physical_tables=ROOTS | {PAYMENT},
            ), ()
        )

    def test_04_unapplied_unique_receiver_migration_refused(self):
        defects = admission._isolated_migration_lineage_defects(
            applied_names=NEW - {"0006_unique_invoice_receivers"},
            physical_tables={PAYMENT}
        )
        self.assertIn("isolated_native_trx_unique_receiver_migration_incomplete", defects)

    def test_05_missing_simulation_payment_table_refused(self):
        defects = admission._isolated_migration_lineage_defects(
            applied_names=set(NEW), physical_tables=set()
        )
        self.assertIn("isolated_native_trx_payment_table_missing", defects)

    def test_06_non_string_or_unavailable_names_are_never_trusted(self):
        for applied, tables in ((None, set()), (set(), None), ({1}, {PAYMENT})):
            with self.subTest(applied=applied, tables=tables):
                defects = admission._isolated_migration_lineage_defects(
                    applied_names=applied, physical_tables=tables
                )
                self.assertIn("isolated_migration_provenance_unavailable", defects)

    def test_07_real_gate_reads_only_parameterized_migration_names(self):
        from config.mojprop_db_router import MOJPROP_DB_ALIAS
        db, cursor = make_connection(applied=NEW, tables={PAYMENT})
        with patch("django.db.connections", {MOJPROP_DB_ALIAS: db}):
            self.assertIsNone(admission.require_live_isolated_migration_lineage())
        cursor.execute.assert_called_once_with(
            "SELECT name FROM django_migrations WHERE app = %s",
            ["prop_firm"],
        )
        cursor.fetchall.assert_called_once()

    def test_08_false_applied_legacy_root_refuses_new_paid_invoice(self):
        from config.mojprop_db_router import MOJPROP_DB_ALIAS
        db, _ = make_connection(applied=NEW | {"0001_initial"}, tables={PAYMENT})
        with patch("django.db.connections", {MOJPROP_DB_ALIAS: db}):
            with self.assertRaisesRegex(
                admission.Starter30PaidAdmissionHold, "coherent isolated migration"
            ):
                admission.require_live_isolated_migration_lineage()

    def test_09_db_read_error_refuses_without_leaking_database_details(self):
        from config.mojprop_db_router import MOJPROP_DB_ALIAS
        db = SimpleNamespace(
            cursor=Mock(side_effect=RuntimeError("secret-internal-database-name")),
        )
        with patch("django.db.connections", {MOJPROP_DB_ALIAS: db}):
            with self.assertRaises(admission.Starter30PaidAdmissionHold) as found:
                admission.require_live_isolated_migration_lineage()
        self.assertNotIn("secret-internal-database-name", str(found.exception))

    def test_10_preinvoice_checks_migration_after_attestations_and_unique_index(self):
        def enabled(*args, **kwargs):
            return None
        with (
            patch.object(starter30_live, "require_release"),
            patch.object(starter30_live, "_provider_pair",
                         return_value=(object(), object())),
            patch.object(starter30_live, "approved_recipient",
                         return_value="offline-fictional-public-address"),
            patch.object(starter30_live, "_hex_recipient",
                         return_value="41" + "0" * 40),
            patch.object(starter30_live, "attested_receivers",
                         return_value=("offline-fictional-public-address",)),
            patch("prop_firm.starter30_checkout_email.require_email_verification_release"),
            patch.object(admission, "require_paid_admission_readiness",
                         side_effect=enabled) as financial,
            patch.object(admission, "require_live_unique_invoice_recipient_schema",
                         side_effect=enabled) as unique,
            patch.object(admission, "require_live_isolated_migration_lineage",
                         side_effect=admission.Starter30PaidAdmissionHold(
                             "migration history requires independent reconciliation")
                         ) as migration,
        ):
            with self.assertRaises(admission.Starter30PaidAdmissionHold):
                starter30_live.verify_pre_invoice_configuration()
        financial.assert_called_once_with()
        unique.assert_called_once_with()
        migration.assert_called_once_with()

    def test_11_new_gate_never_issues_or_persists_an_invoice(self):
        import inspect
        source = inspect.getsource(admission.require_live_isolated_migration_lineage)
        for token in ("schema_editor(", "MigrationExecutor(", ".save(",
                      "CREATE DATABASE", "ALTER TABLE", "DELETE FROM",
                      "UPDATE ", "INSERT INTO", "migrate(",
                      "send_mail(", "TRX", "subprocess."):
            self.assertNotIn(token, source)
        self.assertIn("SELECT name FROM django_migrations WHERE app = %s", source)


if __name__ == "__main__":
    import unittest
    unittest.main()
