"""Master allocator policy: 40 families, strict nonactivation, offline resources."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

REPO=Path(__file__).resolve().parents[1]
SCRIPT=REPO/"scripts/factory_40_family_master.py"
reg_path=REPO/"factory_config/forty_families.json"
spec=importlib.util.spec_from_file_location("factory_40_family_master",SCRIPT)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class FortyLineMasterTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name)
        self.source=self.root/"production-instructions"/"orders"
        self.source.mkdir(parents=True)
    def run_master(self):
        return mod.run(self.root,reg_path)
    def add_order(self,n=1,family_id=None,passport=None):
        id="WO-"+str(n).zfill(8)
        payload={"id":id,"status":"issued","fingerprint":("%064x"%n)}
        if family_id:payload["family_id"]=family_id
        (self.source/(id+".json")).write_text(json.dumps(payload))
        if passport:
            p=self.root/"product-lifecycle"/"passports"
            p.mkdir(parents=True,exist_ok=True)
            (p/(id+".json")).write_text(json.dumps(passport))
        return id
    def test_complete_registry_subtypes_exclusive_adapters_and_qa(self):
        registry=mod.read_obj(reg_path)
        profiles=mod.registry_valid(registry)
        self.assertEqual(len(profiles),40)
        self.assertEqual(len({p["slug"] for p in profiles}),40)
        self.assertEqual(len({p["producer_adapter"] for p in profiles}),40)
        self.assertTrue(all(p["specialist_tests"] and p["subcategories"] for p in profiles))
        self.assertTrue(all(len(p["specialist_tests"])>=4 for p in profiles))
        self.assertTrue(all(p["resource_policy"]["requires_real_benchmark"] for p in profiles))
        self.assertTrue(all(p["readiness"]=="awaiting_executor_validation" for p in profiles))
        self.assertFalse(any(p["production_activation_allowed"] for p in profiles))
    def test_master_reports_forty_unready_when_no_proof(self):
        self.add_order()
        doc=self.run_master()
        self.assertEqual(doc["registered_families"],40)
        self.assertEqual(len(doc["families"]),40)
        self.assertEqual(doc["fully_verified_active_producer_families"],0)
        self.assertEqual(doc["new_work_ready_to_dispatch"],0)
        self.assertEqual(doc["unassigned_work_orders"]["awaiting_family_profile_and_passport"],1)
        self.assertTrue(doc["final_stock_not_inferred_from_technical_qa"])
        self.assertEqual(doc["sites_contacted"],0)
        self.assertFalse(doc["distribution_enabled"])
        self.assertEqual(doc["measured_vps_capacity"]["production_job_slots_authorized"],0)
    def test_matching_work_orders_profile_specific_status(self):
        self.add_order(1,"F28",passport={
            "family_id":"F28","specialty":"greenhouse_water","target_audience":"production manager",
            "problem_solved":"irrigation budget", "level":"advanced","language":"en",
            "source_sha256":"a"*64})
        self.add_order(2,"F28",passport={
            "family_id":"F28","specialty":"greenhouse_water","target_audience":"production manager",
            "problem_solved":"irrigation budget", "level":"advanced","language":"en",
            "source_sha256":"a"*64})
        c=self.run_master()
        f=c["families"][27]
        self.assertEqual(f["family_id"],"F28")
        self.assertEqual(f["pending_review_or_spec"],2)
        self.assertEqual(f["duplicate_identity_warning_count"],1)
        self.assertEqual(f["source_duplicate_hash_count"],1)
        self.assertEqual(f["approved_final_stock"],0)
        self.assertEqual(f["planned_concurrent_jobs"],0)
    def test_no_expensive_40_processes_or_fake_approvals(self):
        c=self.run_master()
        self.assertEqual(c["master_mode"],"inventory_and_admission_planning_only")
        self.assertFalse(any(x["planned_concurrent_jobs"] for x in c["families"]))
        self.assertTrue(all(x["actual_cost_usd"] is None for x in c["families"]))
        self.assertTrue(all(x["last_real_verified_production_duration_seconds"] is None for x in c["families"]))
        self.assertEqual(len([x for x in self.root.rglob("product.zip")]),0)
    def test_registry_rejects_shortcuts(self):
        data=mod.read_obj(reg_path)
        data["profiles"][0]["production_activation_allowed"]=True
        with self.assertRaises(RuntimeError):mod.registry_valid(data)
        data=mod.read_obj(reg_path)
        data["profiles"][3]["specialist_tests"]=[]
        with self.assertRaises(RuntimeError):mod.registry_valid(data)
        data=mod.read_obj(reg_path)
        data["profiles"][8]["resource_policy"]["memory_mb_max"]=0
        with self.assertRaises(RuntimeError):mod.registry_valid(data)
    def test_actual_command_line_exit_and_status(self):
        self.add_order()
        command=subprocess.run([sys.executable,str(SCRIPT),"--factory-private",
                                str(self.root),"--registry",str(reg_path)],
                               capture_output=True,text=True,timeout=20)
        self.assertEqual(command.returncode,0,command.stdout+command.stderr)
        self.assertIn("FACTORY_40_MASTER_STATUS=inventory_and_admission_planning_only",command.stdout)
        self.assertIn("FACTORY_40_FAMILY_REGISTRY=40",command.stdout)
    def test_unique_product_concept_identity(self):
        signature=mod.product_signature("F28","greenhouse","manager","water use","advanced","en")
        same=mod.product_signature(" f28 ","GREENHOUSE","Manager","water  use","ADVANCED","en")
        different=mod.product_signature("F28","greenhouse","manager","water use","beginner","en")
        self.assertEqual(signature,same)
        self.assertNotEqual(signature,different)
        self.assertIsNone(mod.product_signature("F28","greenhouse","manager","","advanced","en"))
    def test_final_goods_counted_only_with_real_receipt_and_family(self):
        wid=self.add_order(1,"F27",passport={"family_id":"F27"})
        target=self.root/"product-lifecycle"/"approved-finished-goods"/wid
        target.mkdir(parents=True)
        artifact=target/"product.zip"
        artifact.write_bytes(b"real verified example")
        digest=hashlib.sha256(artifact.read_bytes()).hexdigest()
        record=self.root/"product-lifecycle"/"records"
        record.mkdir(parents=True)
        (record/(wid+".json")).write_text(json.dumps({
            "final_warehouse_id":wid,"stage_status":{"11":"passed"}}))
        (target/"receipt.json").write_text(json.dumps({
            "order":wid,"distributed":False,"bytes":artifact.stat().st_size,
            "stage_gates_passed":10,"artifact_sha256":digest}))
        c=self.run_master()
        self.assertEqual(c["families"][26]["approved_final_stock"],1)
        self.assertEqual(c["families"][0]["approved_final_stock"],0)
        artifact.write_bytes(b"tampered contents")
        check=self.run_master()
        self.assertEqual(check["families"][26]["approved_final_stock"],0)
        self.assertEqual(check["unassigned_work_orders"]["invalid_or_unverified_final_goods"],1)

if __name__=="__main__":
    unittest.main()
