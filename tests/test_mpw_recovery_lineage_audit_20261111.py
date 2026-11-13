"""Offline audit-mode contracts: never reach cPanel, customers, or payments."""

import contextlib
import io
import json
import unittest
from unittest.mock import patch

from scripts import mpw_recovery_guarded_release_20261105 as release


def report(migrations):
    return {
        "vendor": "mysql", "m39": True, "m49": False,
        "unreviewed_core_migrations": migrations,
        "tables": [], "enabled": False, "mail": False,
    }


class ReadOnlyLineageAuditTests(unittest.TestCase):
    def test_known_factory_fork_is_not_mistaken_for_recovery_parent(self):
        known = report(list(release.EXPECTED_LIVE_CORE_MIGRATIONS))
        self.assertEqual(release.classify_migration_lineage(known),
                         "known_factory_branch_needs_reconciliation")

    def test_reviewed_parent_does_not_authorize_release(self):
        recorded = report(["0040_commercefunnelevent"])
        self.assertEqual(release.classify_migration_lineage(recorded),
                         "reviewed_recovery_parent_recorded_verify_other_gates")

    def test_parallel_0040_branches_are_reported_as_conflict(self):
        parallel = report(["0040_agenttask_bridge_idempotency",
                           "0040_commercefunnelevent"])
        self.assertEqual(release.classify_migration_lineage(parallel),
                         "competing_0040_branches")

    def test_unrecognized_lineage_is_not_upgraded_to_proven(self):
        self.assertEqual(release.classify_migration_lineage(report([
            "0040_unrecognized", "0041_unrecognized"])),
            "unrecognized_migration_lineage")

    def test_invalid_baseline_is_conservatively_classified(self):
        baseline = report(["0040_commercefunnelevent"])
        baseline["m39"] = False
        self.assertEqual(release.classify_migration_lineage(baseline),
                         "unexpected_database_baseline")
        baseline["m39"] = True
        baseline["vendor"] = "sqlite"
        self.assertEqual(release.classify_migration_lineage(baseline),
                         "unexpected_database_baseline")
        self.assertEqual(release.classify_migration_lineage({
            "vendor": "mysql", "m39": True,
            "unreviewed_core_migrations": "0040_commercefunnelevent",
        }), "unknown_metadata")
        self.assertEqual(release.classify_migration_lineage(None),
                         "unknown_metadata")

    def test_audit_emits_only_schema_metadata_without_mutations(self):
        live = report(list(release.EXPECTED_LIVE_CORE_MIGRATIONS))
        live["secret_canary"] = "never_echo_this_value"
        capture = io.StringIO()
        with patch.object(release, "guard_host") as host, \
             patch.object(release, "db_state", return_value=live) as read, \
             patch.object(release, "private_backup") as backup, \
             patch.object(release, "restart") as restart, \
             patch.object(release, "migrate_new_tables") as migrate, \
             contextlib.redirect_stdout(capture):
            status = release.audit_host_read_only()
        host.assert_called_once_with()
        read.assert_called_once_with()
        backup.assert_not_called()
        restart.assert_not_called()
        migrate.assert_not_called()
        self.assertEqual(status, "known_factory_branch_needs_reconciliation")
        output = capture.getvalue()
        self.assertNotIn("never_echo_this_value", output)
        self.assertTrue(output.startswith("MPW_RECOVERY01_READONLY_LINEAGE="))
        result = json.loads(output.split("=", 1)[1])
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["required_parent_applied"])
        self.assertEqual(result["migration_names_only"],
                         release.EXPECTED_LIVE_CORE_MIGRATIONS)

    def test_audit_command_does_not_enter_publish_paths(self):
        with patch.object(release, "audit_host_read_only", return_value="ok") as audit, \
             patch.object(release, "publish") as publish, \
             patch.object(release, "publish_additive") as additive, \
             patch.object(release, "activate") as activate:
            release.main(["release.py", "audit"])
        audit.assert_called_once_with()
        publish.assert_not_called()
        additive.assert_not_called()
        activate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
