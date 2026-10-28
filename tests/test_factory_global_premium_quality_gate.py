"""Global excellence QUALITY FAIL-CLOSED negative controls for all 40 families."""
import hashlib
import importlib.util
import json
from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/factory_global_premium_quality_gate.py"
spec=importlib.util.spec_from_file_location("global_qa_gate",SCRIPT)
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
REGISTRY=gate.load_registry(ROOT/"factory_config/forty_families.json")
def codes(doc):
    return {x["code"] for x in doc["blockers"]}

def proof(root,name):
    p=root/(name+".txt")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(("Independent integrity fixture "+name+"; "
                  "cryptographic identity does not prove expertise or benchmark legitimacy. ")*2)
    return {"path":p.relative_to(root).as_posix(),
            "sha256":hashlib.sha256(p.read_bytes()).hexdigest()}

class GlobalPremiumQualityGateTests(unittest.TestCase):
    def test_evidence_cannot_escape_root_through_symlinked_directory(self):
        with tempfile.TemporaryDirectory() as d:
            workspace=Path(d)
            private=workspace/"private"
            external=workspace/"external"
            private.mkdir()
            external.mkdir()
            valid=proof(private,"authentic")
            outside=proof(external,"borrowed")
            self.assertTrue(gate.evidence_file(private,valid))
            (private/"borrowed-folder").symlink_to(external,target_is_directory=True)
            rel={"path":"borrowed-folder/borrowed.txt","sha256":outside["sha256"]}
            self.assertFalse(gate.evidence_file(private,rel))
            inside=private/"inside"
            inside.mkdir()
            (private/"inside-link").symlink_to(inside,target_is_directory=True)
            nested=proof(inside,"nested")
            self.assertFalse(gate.evidence_file(private,{
                "path":"inside-link/nested.txt","sha256":nested["sha256"]}))
            self.assertFalse(gate.evidence_file(private,{
                "path":"nonexistent/valid.txt","sha256":valid["sha256"]}))

    def test_all_40_individual_domain_rubrics_have_stop_ship(self):
        self.assertEqual(len(REGISTRY),40)
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            for family in sorted(REGISTRY):
                q=gate.inspect({"family_id":family},base,REGISTRY)
                self.assertEqual(q["family_id"],family)
                self.assertEqual(q["quality_verdict"],"BLOCKED_REWORK_REQUIRED")
                self.assertFalse(q["quality_permit"])
                self.assertFalse(q["world_number_one_verified"])
                self.assertFalse(q["public_release_allowed"])
                for individual_test in REGISTRY[family]["specialist_tests"]:
                    self.assertIn("P0_DOMAIN_SPECIALIST_PROOF_MISSING:"+individual_test,codes(q))
                for universal in gate.DIMENSIONS:
                    self.assertIn("P0_PROOF_MISSING:"+universal,codes(q))
                self.assertIn("P0_GLOBAL_TOP_FIVE_CURRENT_BENCHMARKS_MISSING",codes(q))
                self.assertIn("P0_ORIGINAL_INNOVATIONS_UNPROVEN",codes(q))
                self.assertGreaterEqual(q["blocker_count"],len(gate.DIMENSIONS)+len(REGISTRY[family]["specialist_tests"])+4)

    def test_valid_artifact_and_unit_tests_do_not_mean_professional_quality(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            artifact=proof(root,"candidate-artifact")
            manufacture={"qa_status":"passed","artifact_sha256":artifact["sha256"],
                         "commercial_status":"private_internal_qa_pass_not_published"}
            q=gate.inspect({"family_id":"F01","artifact":artifact},root,REGISTRY,manufacture)
            self.assertTrue(q["technical_test_passed"])
            self.assertNotIn("P0_ARTIFACT_UNVERIFIED",codes(q))
            self.assertFalse(q["commercially_approved"])
            self.assertIn("P0_GLOBAL_TOP_FIVE_CURRENT_BENCHMARKS_MISSING",codes(q))
            self.assertIn("P0_DOMAIN_SPECIALIST_PROOF_MISSING:expert_peer_review",codes(q))

    def test_old_comparators_and_cloned_decorative_innovation_cannot_pass(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            rows=[{"name":"Old model "+str(i),"benchmark_date":"2012-01-01",
                   "benchmark_evidence":proof(root,"old-"+str(i))} for i in range(12)]
            q=gate.inspect({"family_id":"F14","comparators":rows,
                    "innovations":[{"id":"cosmetic_a"},{"id":"cosmetic_b"}],
                    "self_certified_number_one":True,
                    "positioning":"brand_new","new_product_announcement_date":"2012-08-01"},
                    root,REGISTRY)
            self.assertEqual(q["global_comparators_structurally_verified"],0)
            self.assertIn("P0_GLOBAL_TOP_FIVE_CURRENT_BENCHMARKS_MISSING",codes(q))
            self.assertIn("P0_SELF_CERTIFICATION_NOT_ACCEPTED",codes(q))
            self.assertIn("P0_NEW_PRODUCT_FRESHNESS_UNVERIFIED",codes(q))
            self.assertIn("P0_ORIGINAL_INNOVATIONS_UNPROVEN",codes(q))

    def test_hash_tampering_detected_in_real_product(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            artifact=proof(root,"real-product")
            q=gate.inspect({"family_id":"F28","artifact":artifact},root,REGISTRY)
            self.assertNotIn("P0_ARTIFACT_UNVERIFIED",codes(q))
            (root/artifact["path"]).write_text("Product file altered")
            q=gate.inspect({"family_id":"F28","artifact":artifact},root,REGISTRY)
            self.assertIn("P0_ARTIFACT_UNVERIFIED",codes(q))

    def test_current_comparators_and_2_working_innovations_still_need_external_truth(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            rows=[{"name":"Leading competitor "+str(i),
                   "benchmark_date":date.today().isoformat(),
                   "benchmark_evidence":proof(root,"leader-"+str(i))} for i in range(5)]
            innovations=[{"id":"original_"+str(i),
                         "working_prototype":proof(root,"proto-"+str(i)),
                         "novelty_comparison":proof(root,"novelty-"+str(i))} for i in range(2)]
            q=gate.inspect({"family_id":"F14","comparators":rows,
                            "innovations":innovations},root,REGISTRY)
            self.assertEqual(q["global_comparators_structurally_verified"],5)
            self.assertEqual(q["innovations_with_integrity_evidence"],2)
            self.assertNotIn("P0_GLOBAL_TOP_FIVE_CURRENT_BENCHMARKS_MISSING",codes(q))
            self.assertNotIn("P0_ORIGINAL_INNOVATIONS_UNPROVEN",codes(q))
            self.assertIn("P0_INDEPENDENT_ATTESTATION_NOT_AUTHENTICATED",codes(q))
            self.assertIn("P0_WORLD_NUMBER_ONE_CLAIM_UNVERIFIED",codes(q))
            self.assertFalse(q["public_release_allowed"])

    def test_attestation_files_are_necessary_but_not_sufficient(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            proofset={k:proof(root,"dim-"+k) for k in gate.DIMENSIONS}
            proofset.update({"specialist:"+k:proof(root,"specialist-"+k)
                             for k in REGISTRY["F03"]["specialist_tests"]})
            doc={"family_id":"F03","artifact":proof(root,"artifact"),
                 "evidence":proofset,"self_approved":True}
            q=gate.inspect(doc,root,REGISTRY)
            self.assertFalse(any(c.startswith("P0_PROOF_MISSING:") for c in codes(q)))
            self.assertFalse(any(c.startswith("P0_DOMAIN_SPECIALIST_PROOF_MISSING:") for c in codes(q)))
            self.assertIn("P0_SELF_CERTIFICATION_NOT_ACCEPTED",codes(q))
            self.assertFalse(q["commercially_approved"])

    def test_product_unmapped_and_unsafe_release_status_fail(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            q=gate.inspect({"family_id":"F99"},root,REGISTRY,
                           {"qa_status":"passed","artifact_sha256":"a"*64,
                            "commercial_status":"public_on"})
            self.assertIn("P0_UNMAPPED_PRODUCT_FAMILY",codes(q))
            self.assertIn("P0_UNSAFE_COMMERCIAL_STATE",codes(q))
            self.assertIn("P0_BUILD_HASH_NOT_MATCHING_MANIFEST",codes(q))
            self.assertFalse(q["quality_permit"])

if __name__=="__main__":
    unittest.main()
