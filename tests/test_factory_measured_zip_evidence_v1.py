"""Positive and adversarial real-file Q068, one ten-point group only."""
import hashlib,importlib.util,json,zipfile
from pathlib import Path
import tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
script=ROOT/"scripts/factory_measured_zip_evidence_v1.py"
sp=importlib.util.spec_from_file_location("zip_evidence",script)
mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
class ActualZipEvidence(unittest.TestCase):
    def make(self,folder,unsafe=False):
        root=Path(folder)
        p=root/"good_recipe-internal-qa.zip"
        with zipfile.ZipFile(p,"w",zipfile.ZIP_DEFLATED) as z:
            z.writestr("../outside" if unsafe else "good_recipe/README.md",
                       "Authentic archive data must be inspected not declared.")
        return p,{"artifact_sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
    def test_measurement_of_real_zip_validates_and_creates_versioned_proof(self):
        with tempfile.TemporaryDirectory() as d:
            p,m=self.make(d)
            a=mod.measured_zip_evidence(d,"good_recipe",p,m)
            self.assertIsNotNone(a)
            self.assertTrue((Path(d)/a["path"]).is_file())
            self.assertEqual(a,mod.measured_zip_evidence(d,"good_recipe",p,m))
            detail=json.loads((Path(d)/a["path"]).read_text())
            self.assertTrue(detail["all_crc_and_path_safety_tests_passed"])
            self.assertFalse(detail["professional_quality_1000_approved"])
            self.assertEqual(detail["criterion"],"Q068")
    def test_forged_manifest_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p,m=self.make(d)
            m["artifact_sha256"]="a"*64
            self.assertIsNone(mod.measured_zip_evidence(d,"good_recipe",p,m))
    def test_corrupt_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p,m=self.make(d)
            p.write_bytes(p.read_bytes()[:10])
            m["artifact_sha256"]=hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertIsNone(mod.measured_zip_evidence(d,"good_recipe",p,m))
    def test_unsafe_zip_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p,m=self.make(d,unsafe=True)
            self.assertIsNone(mod.measured_zip_evidence(d,"good_recipe",p,m))
    def test_zip_sha_is_not_world_class_certificate(self):
        with tempfile.TemporaryDirectory() as d:
            p,m=self.make(d)
            a=mod.measured_zip_evidence(d,"good_recipe",p,m)
            assert a
            sc=ROOT/"scripts/factory_quality_1000_v2.py"
            spec=importlib.util.spec_from_file_location("score_100",sc)
            score=importlib.util.module_from_spec(spec);spec.loader.exec_module(score)
            verdict={"family_id":"F14","blockers":[{"code":"P0_PROOF_MISSING:independent_adversarial_testing"}]}
            grade=score.grade(verdict,criteria_evidence={"Q068":a},evidence_root=d)
            self.assertEqual(grade["documentary_evidence_points"],10)
            self.assertEqual(grade["criteria"]["Q068"]["documentary_points"],10)
            self.assertIsNone(grade["product_quality_points"])
            self.assertFalse(grade["professional_quality_1000_passed"])
            self.assertFalse(grade["release_allowed"])
if __name__=="__main__":unittest.main()
