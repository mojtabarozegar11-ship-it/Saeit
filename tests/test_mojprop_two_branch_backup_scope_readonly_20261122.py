"""Offline regression checks for migration provenance and backup scope gating."""
import gzip
import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import contextlib
import importlib.util
import io

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/mojprop_two_branch_backup_scope_readonly_20261122.py"
SPEC = importlib.util.spec_from_file_location("mojprop_archive_scope_reader", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class MojPropTwoBranchArchiveProofTests(TestCase):
    def test_01_both_historical_and_isolated_migration_chains_are_pinned(self):
        report = MOD.check_sources(ROOT)
        self.assertTrue(report["all_source_proven"], report["components"])
        self.assertEqual(report["checked"], 16)
        self.assertEqual(report["matched"], 16)
        self.assertFalse(report["restore_verified"])
        self.assertFalse(report["historical_migrations_copied_to_runtime"])

    def test_02_archived_legacy_data_not_treated_as_new_migration_branch(self):
        self.assertEqual(len(MOD.LEGACY), 10)
        self.assertEqual(len(MOD.ISOLATED), 6)
        self.assertEqual(next(iter(MOD.LEGACY)), "0001_initial")
        self.assertEqual(next(iter(MOD.ISOLATED)), "0001_simulation_isolation")
        self.assertEqual(list(MOD.ISOLATED)[-1], "0006_unique_invoice_receivers")
        self.assertNotEqual(set(MOD.LEGACY), set(MOD.ISOLATED))

    def test_03_source_drift_or_missing_archive_fails_closed(self):
        with TemporaryDirectory() as tmp:
            temp = Path(tmp)
            for rel, chain in (
                ("source-sync/20261120/prop_firm/migrations", MOD.LEGACY),
                ("prop_firm/migrations", MOD.ISOLATED),
            ):
                for name in chain:
                    source = ROOT / rel / (name + ".py")
                    target = temp / rel / (name + ".py")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(source.read_bytes())
            self.assertTrue(MOD.check_sources(temp)["all_source_proven"])
            old = temp / "source-sync/20261120/prop_firm/migrations/0004_four_week_challenge.py"
            old.write_bytes(old.read_bytes() + b"# changed archived migration\n")
            self.assertFalse(MOD.check_sources(temp)["all_source_proven"])

    def test_04_current_migration_missing_fails_closed(self):
        with TemporaryDirectory() as tmp:
            self.assertFalse(MOD.check_sources(Path(tmp))["all_source_proven"])
            self.assertEqual(MOD.check_sources(Path(tmp))["matched"], 0)

    def test_05_backup_tables_and_digest_can_be_verified_without_import(self):
        tables = {"table_" + str(i) for i in range(30)}
        sql = b"".join(b"CREATE TABLE " + bytes([96]) + n.encode() +
                       bytes([96]) + b" (id integer);\n" for n in sorted(tables))
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "existing.sql.gz"
            with gzip.open(path, "wb") as stream:
                stream.write(sql)
            os.chmod(path, 0o600)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result = MOD.inspect_archive(path, digest, tables)
            self.assertTrue(result["digest_verified"])
            self.assertTrue(result["exact_30_table_schema"])
            self.assertEqual(result["tables_matched"], 30)
            self.assertTrue(result["no_database_switch"])
            self.assertTrue(result["no_destructive_ddl"])
            self.assertFalse(result["rehearsed_independent_restore"])

    def test_06_backup_digest_mismatch_and_unsafe_selector_are_detected(self):
        tables = {"alpha"}
        sql = (b"CREATE DATABASE oldprod;\nUSE oldprod;\n"
               b"DROP TABLE IF EXISTS " + bytes([96]) + b"alpha" + bytes([96]) + b";\n"
               b"CREATE TABLE " + bytes([96]) + b"alpha" + bytes([96]) + b" (id integer);\n")
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "backup.sql.gz"
            with gzip.open(path, "wb") as stream:
                stream.write(sql)
            os.chmod(path, 0o600)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertFalse(MOD.inspect_archive(path, "0" * 64, tables)["digest_verified"])
            result = MOD.inspect_archive(path, digest, tables)
            self.assertTrue(result["digest_verified"])
            self.assertFalse(result["no_database_switch"])
            self.assertFalse(result["no_destructive_ddl"])
            self.assertFalse(result["exact_30_table_schema"])

    def test_07_symlink_and_world_readable_archive_refused(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "normal.sql.gz"
            with gzip.open(path, "wb") as f:
                f.write(b"CREATE TABLE " + bytes([96]) + b"t" + bytes([96]) + b" (id int);\n")
            os.chmod(path, 0o600)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            link = Path(tmp) / "backup-symlink.sql.gz"
            link.symlink_to(path)
            self.assertFalse(MOD.inspect_archive(link, digest, {"t"})["digest_verified"])
            os.chmod(path, 0o644)
            self.assertFalse(MOD.inspect_archive(path, digest, {"t"})["digest_verified"])

    def test_08_cli_never_offers_migration_or_restore_mutation(self):
        out = io.StringIO()
        with contextlib.redirect_stderr(out):
            self.assertEqual(MOD.main(["--apply"]), 64)
            self.assertEqual(MOD.main(["--migrate"]), 64)
            self.assertEqual(MOD.main(["--restore"]), 64)
        self.assertIn("read-only", out.getvalue())

    def test_09_exact_parent_dependency_checks_reject_swapped_graph(self):
        valid = (b"from django.db import migrations\n"
                 b"class Migration(migrations.Migration):\n"
                 b"    dependencies = [('prop_firm','0001_initial')]\n"
                 b"    operations = []\n")
        self.assertEqual(MOD.parents_in_migration(valid), {"0001_initial"})
        self.assertEqual(MOD.parents_in_migration(valid.replace(
            b"0001_initial", b"0001_simulation_isolation")), {"0001_simulation_isolation"})

    def test_10_no_claim_of_live_restore_or_financial_readiness(self):
        source = SCRIPT.read_text(encoding="utf8")
        for marker in ("independent_restore_verified", "financial_release_proven",
                       "production_migration_approved", "written_changes",
                       "status"):
            self.assertIn(marker, source)
        self.assertIn('"status": "BLOCKED"', source)
        self.assertNotIn("schema_editor(", source)
        self.assertNotIn("subprocess.run(", source)


    def test_11_archive_lineage_reads_multiline_values_without_leaking_rows(self):
        names = list(MOD.LEGACY) + list(MOD.ISOLATED)[:5]
        header = b"CREATE TABLE " + bytes([96]) + b"django_migrations" + bytes([96]) + b" (id int);\n"
        payload = (b"INSERT INTO " + bytes([96]) + b"django_migrations" + bytes([96])
                   + b" VALUES\n" + b",\n".join(
                       ("('prop_firm','" + name + "')").encode() for name in names
                   ) + b";\n")
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "historical.sql.gz"
            with gzip.open(path, "wb") as f:
                f.write(header + payload)
            os.chmod(path, 0o600)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result = MOD.inspect_archive(path, digest, {"django_migrations"})
            self.assertTrue(result["archived_migration_names_15_of_15"])
            self.assertFalse(result["archived_unique_receiver_marked_applied"])
            self.assertFalse(result["rehearsed_independent_restore"])

    def test_12_backup_migration_records_must_not_claim_unique_was_applied(self):
        marker = b"INSERT INTO " + bytes([96]) + b"django_migrations" + bytes([96])
        sql = (b"CREATE TABLE " + bytes([96]) + b"django_migrations" + bytes([96])
               + b" (id int);\n" + marker +
               b" VALUES\n('prop_firm','0006_unique_invoice_receivers');\n")
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "unique-not-applied.sql.gz"
            with gzip.open(path, "wb") as f:
                f.write(sql)
            os.chmod(path, 0o600)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result = MOD.inspect_archive(path, digest, {"django_migrations"})
            self.assertFalse(result["archived_migration_names_15_of_15"])
            self.assertTrue(result["archived_unique_receiver_marked_applied"])


    def test_13_legacy_applied_markers_without_legacy_tables_are_flagged(self):
        self.assertEqual(MOD.LEGACY_ROOT_TABLES, frozenset({
            "prop_firm_proptrader", "prop_firm_propaccount",
            "prop_firm_propexecution", "prop_firm_propequityobservation",
            "prop_firm_propdecisionlog",
        }))
        applied = set(MOD.LEGACY) | set(MOD.ISOLATED)
        isolated_tables = {
            "prop_firm_propsimulationpayment",
            "prop_firm_propsimulationidentity",
        }
        self.assertTrue(MOD.legacy_markers_contradict_schema(applied, isolated_tables))

    def test_14_legacy_root_check_never_flags_isolated_only_or_complete_schema(self):
        self.assertFalse(MOD.legacy_markers_contradict_schema(
            set(MOD.ISOLATED), set()
        ))
        self.assertFalse(MOD.legacy_markers_contradict_schema(
            set(MOD.LEGACY), set(MOD.LEGACY_ROOT_TABLES)
        ))
        self.assertTrue(MOD.legacy_markers_contradict_schema(
            set(MOD.LEGACY), set(MOD.LEGACY_ROOT_TABLES) - {"prop_firm_propaccount"}
        ))


if __name__ == "__main__":
    import unittest
    unittest.main()
