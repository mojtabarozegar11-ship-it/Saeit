"""Read-only reconciliation contract regression tests; no live hosts."""
import json
import sqlite3
import unittest
from deploy.mojtaba_task_reconciliation_readonly import task_reconciliation, reason_tags

class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.execute("CREATE TABLE core_agenttask (id INTEGER, status TEXT, action_type TEXT, attempt_count INTEGER, max_attempts INTEGER, output_data TEXT, project_id INTEGER, product_id INTEGER, factory_run_id INTEGER)")
        self.db.execute("CREATE TABLE core_factoryrun (id INTEGER,status TEXT,product_id INTEGER)")
        self.db.execute("INSERT INTO core_factoryrun VALUES (1,'active',100),(2,'blocked',100)")
    def insert(self, pk, status, action, attempt, message, product, run):
        self.db.execute("INSERT INTO core_agenttask VALUES (?,?,?,?,?,?,?,?,?)",
                        (pk,status,action,attempt,3,json.dumps({"error":message}),None,product,run))
    def test_classification_and_no_payload_leak(self):
        self.insert(1,"blocked","product_research",1,"owner provenance; SECRET-TEST",100,1)
        self.insert(2,"queued","product_validation",3,"retry exhausted",101,1)
        self.insert(3,"queued","product_validation",0,"",100,2)
        self.insert(4,"completed","product_research",1,"SECRET-TEST",100,1)
        before=self.db.total_changes
        report=task_reconciliation(self.db.cursor())
        self.assertEqual(report["pending"],3)
        self.assertEqual(report["blocked_reason_indicators_nonexclusive"],[{"action":"product_research","reason_tag":"owner_provenance","total":1}])
        self.assertEqual(report["exhausted_groups"][0]["total"],1)
        self.assertEqual({x["link_state"] for x in report["run_links"]["groups"]},{"run_active_product_match","run_product_mismatch","run_not_active"})
        self.assertNotIn("SECRET-TEST",json.dumps(report))
        self.assertEqual(self.db.total_changes,before)
        self.assertFalse(report["execution_authorized"])
    def test_same_link_is_not_proven_duplicate(self):
        self.insert(1,"blocked","product_research",1,"",100,1)
        self.insert(2,"queued","product_research",1,"",100,1)
        report=task_reconciliation(self.db.cursor())
        self.assertEqual(report["same_action_product_run_candidate_tasks"],2)
        self.assertFalse(report["duplicates_proven"])
    def test_missing_links_not_confused_with_null(self):
        self.db.execute("DROP TABLE core_agenttask")
        self.db.execute("CREATE TABLE core_agenttask (id INTEGER,status TEXT,action_type TEXT,attempt_count INTEGER,max_attempts INTEGER,output_data TEXT)")
        self.db.execute("INSERT INTO core_agenttask VALUES (1,'queued','product_research',0,3,'{}')")
        report=task_reconciliation(self.db.cursor())
        self.assertEqual({r["state"] for r in report["links"]},{"field_absent"})
    def test_untrusted_reason_tags(self):
        self.assertEqual(reason_tags("not json"),("unstructured_reason",))
        self.assertEqual(reason_tags({"error": "arbitrary private content"}),("other_reason",))
        self.assertEqual(reason_tags({"error": "permission timeout"}),("approval_or_permission","retry_or_timeout"))

if __name__=="__main__":
    unittest.main()
