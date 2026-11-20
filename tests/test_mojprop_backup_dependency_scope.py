"""Read-only metadata graph tests; no database or quota commands."""
import unittest
from scripts.mpw_db_backup_scope_readonly_20261119 import dependency_scope

class MojPropBackupScopeTests(unittest.TestCase):
    def test_parent_closure_excludes_unrelated_auth_children(self):
        invoice = "prop_firm_propplan1invoice"
        account = "prop_firm_propsimulationaccount"
        rows = [(invoice,"InnoDB",10), (account,"InnoDB",20),
                ("auth_user","InnoDB",30), ("other_child","InnoDB",1000)]
        edges = {(account, invoice, 1), (account, "auth_user", 1),
                 ("other_child", "auth_user", 1)}
        report = dependency_scope(rows, edges, {"auth_user"}, "auth_user")
        self.assertEqual(report["present_prop_tables"], 2)
        self.assertEqual(report["parent_closure_tables"], 3)
        self.assertEqual(report["parent_closure_bytes_estimated"], 60)
        self.assertEqual(report["incoming_dependencies_from_other_tables"], 1)
        self.assertEqual(report["shared_store_tables_in_closure"], 1)
        self.assertTrue(report["shared_auth_table_in_closure"])
        self.assertFalse(report["backup_scope_approved"])
        self.assertFalse(report["independent_restore_proven"])

    def test_cross_schema_or_missing_parent_never_silently_accepted(self):
        table = "prop_firm_propplan1invoice"
        report = dependency_scope([(table,"InnoDB",10)],
            {(table,"outside",0),(table,"missing",1)}, set(), "auth_user")
        self.assertEqual(report["external_or_missing_parent_edges"], 2)
        self.assertEqual(report["missing_prop_tables"], 9)
        self.assertFalse(report["backup_scope_approved"])

    def test_absent_prop_tables_are_not_an_independent_backup(self):
        report = dependency_scope([("auth_user","InnoDB",100)], set(), set(), "auth_user")
        self.assertEqual(report["present_prop_tables"], 0)
        self.assertEqual(report["missing_prop_tables"], 10)
        self.assertFalse(report["independent_restore_proven"])
