import json,tempfile,unittest
from pathlib import Path
from scripts.f01_quality_1000_machine_gate import evaluate
class F01QualityGateTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.root=Path(self.t.name); self.package=self.root/"f01.zip"; self.package.write_bytes(b"verified-f01-1.5"); self.catalog=Path("factory_config/f01_quality_100_criteria.json"); self.evidence=self.root/"evidence"; self.evidence.mkdir(); self.sha=__import__("hashlib").sha256(self.package.read_bytes()).hexdigest()
 def tearDown(self): self.t.cleanup()
 def write_evidence(self,ids):
  data=json.loads(self.catalog.read_text())
  for c in data["criteria"]:
   if c["id"] in ids:
    p=self.evidence/c["required_evidence"]; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps({"schema":"saeit.factory.f01-quality-evidence.v1","product_id":"farm_enterprise_economics","criterion_id":c["id"],"artifact_sha256":self.sha,"status":"PASS"}))
 def test_partial_score_is_exact_and_locked(self):
  self.write_evidence(["F01-01-1","F01-20-5"]); r=evaluate(self.package,self.catalog,self.evidence); self.assertEqual(r["machine_documentary_points"],20); self.assertEqual(r["machine_documentary_gap"],980); self.assertIsNone(r["professional_quality_points"]); self.assertFalse(r["professional_qc1000_certified"]); self.assertFalse(r["commercial_release_allowed"])
 def test_all_machine_evidence_reaches_documentary_1000_only(self):
  self.write_evidence([c["id"] for c in json.loads(self.catalog.read_text())["criteria"]]); r=evaluate(self.package,self.catalog,self.evidence); self.assertEqual(r["machine_documentary_points"],1000); self.assertEqual(r["machine_documentary_gap"],0); self.assertFalse(r["professional_qc1000_certified"]); self.assertFalse(r["commercial_release_allowed"])
 def test_non_object_json_is_missing_not_crash(self):
  p=self.evidence/"evidence/F01-01-1.json"; p.parent.mkdir(parents=True,exist_ok=True); p.write_text("[]"); r=evaluate(self.package,self.catalog,self.evidence); self.assertEqual(r["machine_documentary_points"],0); self.assertIn("F01-01-1",r["missing_criteria"])
 def test_missing_evidence_root_is_zero_not_crash(self):
  r=evaluate(self.package,self.catalog,self.root/"not-created"); self.assertEqual(r["machine_documentary_points"],0); self.assertEqual(len(r["missing_criteria"]),100)
 def test_cyclic_evidence_symlink_is_missing_not_crash(self):
  self.write_evidence(["F01-20-5"])
  p=self.evidence/"evidence/F01-01-1.json"; p.parent.mkdir(parents=True,exist_ok=True); p.symlink_to(p.name)
  r=evaluate(self.package,self.catalog,self.evidence)
  self.assertEqual(r["machine_documentary_points"],10)
  self.assertIn("F01-01-1",r["missing_criteria"])
  self.assertFalse(r["commercial_release_allowed"])
 def test_cyclic_parent_symlink_is_missing_not_crash(self):
  (self.evidence/"evidence").symlink_to("evidence",target_is_directory=True)
  r=evaluate(self.package,self.catalog,self.evidence)
  self.assertEqual(r["machine_documentary_points"],0)
  self.assertEqual(len(r["missing_criteria"]),100)
  self.assertFalse(r["professional_qc1000_certified"])
if __name__=="__main__": unittest.main()
