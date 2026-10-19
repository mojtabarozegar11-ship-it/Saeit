"""Factory 12-stage lifecycle: never conflate draft/technical QA with final sale goods."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

MODULE=Path(__file__).resolve().parents[1]/"scripts"/"factory_12_stage_governance.py"
spec=importlib.util.spec_from_file_location("lifecycle",MODULE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Factory12StageTests(unittest.TestCase):
    def setUp(self):
        td=tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root=Path(td.name)
        self.ins=self.root/"production-instructions"/"orders"
        self.ins.mkdir(parents=True)
        self.instruction={"id":"WO-00000001","status":"issued","fingerprint":"a"*64,
                          "subject":"Real software utility","phase":"engineering_specification"}
        (self.ins/"WO-00000001.json").write_text(json.dumps(self.instruction))
        self.technical=self.root/"production-warehouse"
        self.technical.mkdir()
        (self.technical/"stock-register.json").write_text(json.dumps({"finished_goods_versions":2}))
        self.base=self.root/"product-lifecycle"
        self.wid="WO-00000001"
    def passport(self):
        return {"schema":m.SPEC_SCHEMA,"work_order":self.wid,"title":"Real software utility",
                "product_type":"software","version":"1.0.0","origin":"factory_invention",
                "target_audience":"Software engineers","problem_solved":"Validate local data safely",
                "deliverables":["working calculator","test harness"],"file_formats":[".zip"],
                "language":"English","scope":"Local offline execution","prerequisites":["Python 3"],
                "acceptance_criteria":["Pass independent functional and security checks"],
                "sources":["Verified local software tests"],"asset_licenses":["Original work"],
                "technical_dependencies":["Python stdlib"],
                "stages_and_owners":["Engineer:build","QA specialist:review"],
                "resource_budget":"2 worker hours","sensitivity":"Low",
                "producer_id":"engineer-01","independent_reviewer_id":"reviewer-02",
                "human_review_required":True}
    def register(self):
        m.tick(self.root)
        p=self.root/"passport-to-import.json"
        p.write_text(json.dumps(self.passport()))
        m.import_passport(self.root,self.wid,p)
    def review_file(self,stage,decision="pass",reviewer="engineer-01",defect=None):
        proof=self.root/("evidence-stage-"+str(stage)+".txt")
        proof.write_text("Real test execution log for stage "+str(stage))
        checks=[{"id":"stage_"+str(stage)+"_evidence","status":"passed"}]
        if stage in (6,7,9,10):
            checks=[{"id":c,"status":"passed"} for c in m.TYPES["software"]]
        if decision=="fail":
            checks=[{"id":"stage_failure","status":"failed"}]
        record={"schema":m.REVIEW_SCHEMA,"order":self.wid,"stage":stage,
                "passport_sha256":m.sha(m.spec_path(self.root,self.wid)),
                "reviewer_id":reviewer,"producer_id":"engineer-01","reviewer_role":
                "qualified_specialist" if stage in (6,10) else "engineer",
                "decision":decision,"human_attestation":stage in (6,10),
                "checks":checks,
                "evidence_files":[{"path":proof.name,"sha256":m.sha(proof)}]}
        if defect:record["defect"]=defect
        ref=self.root/("stage-"+str(stage)+"-"+decision+".json")
        ref.write_text(json.dumps(record))
        return ref
    def test_no_unsourced_product_can_enter_final_stock(self):
        summary=m.tick(self.root)
        self.assertEqual(summary["newly_tracked"],1)
        self.assertEqual(summary["old_technical_QA_stock_pending_final_review"],2)
        self.assertEqual(summary["final_commercially_verified_stock"],0)
        self.assertEqual(summary["blocked_reasons"]["missing_product_passport"],1)
        with self.assertRaises(RuntimeError):
            m.final_admit(self.root,self.wid,"something.zip")
    def test_two_existing_technical_products_never_autopromoted(self):
        m.tick(self.root)
        m.tick(self.root)
        self.assertEqual(len(list((self.base/"records").glob("*.json"))),1)
        self.assertEqual(len(list((self.base/"approved-finished-goods").iterdir())),0)
        self.assertTrue((self.technical/"stock-register.json").is_file())
    def test_complete_passport_required_and_immutable(self):
        m.tick(self.root)
        incomplete=self.passport();incomplete["target_audience"]=""
        path=self.root/"passport.json";path.write_text(json.dumps(incomplete))
        with self.assertRaises(RuntimeError):m.import_passport(self.root,self.wid,path)
        path.write_text(json.dumps(self.passport()))
        m.import_passport(self.root,self.wid,path)
        with self.assertRaises(RuntimeError):m.import_passport(self.root,self.wid,path)
    def test_review_must_be_sequential_and_evidenced(self):
        self.register()
        with self.assertRaises(RuntimeError):m.review(self.root,self.wid,self.review_file(2))
        state=m.review(self.root,self.wid,self.review_file(1))
        self.assertEqual(state["current_stage"],2)
        self.assertEqual(state["stage_status"]["1"],"passed")
        with self.assertRaises(RuntimeError):m.review(self.root,self.wid,self.review_file(1))
        self.assertFalse(state["commercial_release"])
    def test_independent_reviewer_and_family_checks_required(self):
        self.register()
        for i in range(1,6):m.review(self.root,self.wid,self.review_file(i))
        with self.assertRaises(RuntimeError):
            m.review(self.root,self.wid,self.review_file(6,reviewer="engineer-01"))
        with self.assertRaises(RuntimeError):
            m.review(self.root,self.wid,self.review_file(6,reviewer="reviewer-03"))
        ref=self.review_file(6,reviewer="reviewer-02")
        doc=json.loads(ref.read_text());doc["checks"]=[{"id":"real_execution","status":"passed"}]
        ref.write_text(json.dumps(doc))
        with self.assertRaises(RuntimeError):m.review(self.root,self.wid,ref)
        m.review(self.root,self.wid,self.review_file(6,reviewer="reviewer-02"))
    def test_rework_preserved_and_retested_without_fake_pass(self):
        self.register()
        defect={"description":"Invalid computation result","severity":"critical",
                "likely_cause":"Incorrect arithmetic operator",
                "corrective_action":"Repair operator and rerun suite",
                "retest_criteria":"All affected calculations match known reference"}
        state=m.review(self.root,self.wid,self.review_file(1,"fail",defect=defect))
        self.assertEqual(state["status"],"rework_required")
        self.assertEqual(state["stage_status"]["1"],"failed")
        with self.assertRaises(RuntimeError):m.review(self.root,self.wid,self.review_file(1))
        proof=self.root/"correction.txt";proof.write_text("Verified fix and regression tests")
        doc={"schema":m.REVIEW_SCHEMA,"order":self.wid,"stage":1,
             "corrective_action_completed":True,"affected_area_regression_passed":True,
             "evidence_files":[{"path":proof.name,"sha256":m.sha(proof)}]}
        evidence=self.root/"resolved.json";evidence.write_text(json.dumps(doc))
        state=m.resolve_defect(self.root,self.wid,evidence)
        self.assertEqual(state["defects"][0]["status"],"resolved")
        state=m.review(self.root,self.wid,self.review_file(1))
        self.assertEqual(state["current_stage"],2)
    def test_admit_after_all_real_qa_reviews_and_actual_bundle(self):
        self.register()
        for i in range(1,11):
            reviewer="reviewer-02" if i in (6,10) else "engineer-01"
            state=m.review(self.root,self.wid,self.review_file(i,reviewer=reviewer))
        self.assertEqual(state["status"],"awaiting_final_warehouse_admission")
        with self.assertRaises(RuntimeError):
            m.final_admit(self.root,self.wid,"missing.zip")
        bundle=self.root/"product-bundle.zip"
        with zipfile.ZipFile(bundle,"w") as f:
            for folder in m.REQUIRED_PACKAGE:
                f.writestr(folder+"example.txt","Actual content for "+folder)
        final=m.final_admit(self.root,self.wid,bundle.name)
        receipt=json.loads((final/"receipt.json").read_text())
        self.assertEqual(receipt["stage_gates_passed"],10)
        self.assertFalse(receipt["distributed"])
        self.assertEqual(m.load_order(self.root,self.wid)["stage_status"]["11"],"passed")
        self.assertEqual(m.tick(self.root)["final_commercially_verified_stock"],1)
        self.assertEqual(m.tick(self.root)["old_technical_QA_stock_pending_final_review"],2)
        with self.assertRaises(RuntimeError):m.final_admit(self.root,self.wid,bundle.name)
    def test_unknown_family_cannot_pass(self):
        self.register()
        self.assertEqual(len(m.STAGES),12)
        self.assertEqual(len(m.TYPES),11)
        self.assertNotIn("generic",m.TYPES)
        d=self.passport();d["product_type"]="experimental_unknown_family"
        with self.assertRaises(RuntimeError):m.passport_validate(d,self.wid)

if __name__=="__main__":unittest.main()
