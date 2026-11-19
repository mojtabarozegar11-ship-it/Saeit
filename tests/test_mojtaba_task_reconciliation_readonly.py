"""Read-only reconciliation contract regression tests; no live hosts."""
import json
from copy import deepcopy
from deploy.mojtaba_task_reconciliation_receipt import validate_reconciliation
import sqlite3
import unittest
from deploy.mojtaba_task_reconciliation_readonly import task_reconciliation, reason_tags, collect

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
    def test_absent_optional_run_table_preserves_task_evidence(self):
        self.insert(1,"queued","product_validation",3,"retry exhausted",100,1)
        self.db.execute("DROP TABLE core_factoryrun")
        report = json.loads(json.dumps(task_reconciliation(self.db.cursor())))
        self.assertEqual(report["run_links"], {"state":"run_schema_incomplete"})
        self.assertEqual(report["exhausted_cases_snapshot_local"][0]["run_link_state"],"not_evaluated")
        agents=[{"pending_groups":[{"action":"product_validation","status":"queued",
                                    "total":1,"attempt_limit_reached":1}]}]
        self.assertEqual(validate_reconciliation(report,agents,1),report)

    def test_full_census_receipt_reconciles_real_fixture_rows(self):
        self.db.execute("CREATE TABLE core_agent (id INTEGER,code TEXT,active INTEGER)")
        self.db.execute("INSERT INTO core_agent VALUES (1,'factory-market-research-agent',1)")
        self.db.execute("CREATE TABLE core_approvalrequest (target_id TEXT,status TEXT,target_type TEXT)")
        for name, declaration in (
            ("agent_id","INTEGER DEFAULT 1"), ("capability_code","TEXT DEFAULT 'product_research'"),
            ("risk_snapshot","TEXT DEFAULT 'low'"), ("execution_id","TEXT DEFAULT ''")
        ):
            self.db.execute("ALTER TABLE core_agenttask ADD COLUMN "+name+" "+declaration)
        self.db.execute("INSERT INTO core_agenttask (id,status,action_type,attempt_count,max_attempts,output_data,product_id,factory_run_id) VALUES (1,'queued','product_research',3,3,'{}',100,1)")
        self.db.execute("INSERT INTO core_agenttask (id,status,action_type,attempt_count,max_attempts,output_data,product_id,factory_run_id) VALUES (2,'blocked','product_research',1,3,'{}',100,1)")
        before = self.db.total_changes
        snapshot = json.loads(json.dumps(collect(self.db.cursor())))
        self.assertEqual(snapshot["nonterminal_tasks"],2)
        receipt = snapshot["task_reconciliation"]
        self.assertEqual(validate_reconciliation(receipt,snapshot["agents"],2),receipt)
        self.assertEqual(self.db.total_changes,before)
        for field,value in (("project_id","present"),("product_id","null")):
            bad = deepcopy(receipt)
            bad["exhausted_cases_snapshot_local"][0]["links"][field]=value
            with self.assertRaises(ValueError):
                validate_reconciliation(bad,snapshot["agents"],2)
        bad=deepcopy(receipt)
        bad["exhausted_cases_snapshot_local"][0]["run_link_state"]="not_evaluated"
        with self.assertRaises(ValueError):
            validate_reconciliation(bad,snapshot["agents"],2)

    def test_untrusted_reason_tags(self):
        self.assertEqual(reason_tags("not json"),("unstructured_reason",))
        self.assertEqual(reason_tags({"error": "arbitrary private content"}),("other_reason",))
        self.assertEqual(reason_tags({"error": "permission timeout"}),("approval_or_permission","retry_or_timeout"))


    def test_exhausted_case_and_receipt(self):
        self.insert(1,"blocked","product_research",1,"owner provenance",100,1)
        self.insert(2,"queued","product_validation",3,"retry exhausted",101,1)
        report=json.loads(json.dumps(task_reconciliation(self.db.cursor())))
        agents=[{"pending_groups":[
            {"action":"product_research","status":"blocked","total":1,"attempt_limit_reached":0},
            {"action":"product_validation","status":"queued","total":1,"attempt_limit_reached":1},
        ]}]
        self.assertEqual(validate_reconciliation(report,agents,2),report)
        case=report["exhausted_cases_snapshot_local"][0]
        self.assertEqual(case["case"],1)
        self.assertEqual(case["run_link_state"],"run_product_mismatch")
        self.assertNotIn("_product",case)
        self.assertNotIn("_run",case)
        for mutation in ("unknown_label","bad_total","extra_payload","authorization","missing_case","duplicate_group","wrong_exhausted_count"):
            bad=deepcopy(report)
            if mutation=="unknown_label":
                bad["blocked_reason_indicators_nonexclusive"][0]["reason_tag"]="raw secret"
            elif mutation=="bad_total":
                bad["links"][0]["total"]=2
            elif mutation=="extra_payload":
                bad["exhausted_cases_snapshot_local"][0]["raw_payload"]="secret"
            elif mutation=="authorization":
                bad["execution_authorized"]=True
            elif mutation=="missing_case":
                bad["exhausted_cases_snapshot_local"]=[]
            elif mutation=="duplicate_group":
                bad["groups"].append(bad["groups"][0])
            else:
                bad["exhausted_groups"][0]["total"]=2
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_reconciliation(bad,agents,2)

    def test_empty_snapshot_receipt(self):
        report=json.loads(json.dumps(task_reconciliation(self.db.cursor())))
        self.assertEqual(validate_reconciliation(report,[],0),report)

if __name__=="__main__":
    unittest.main()
