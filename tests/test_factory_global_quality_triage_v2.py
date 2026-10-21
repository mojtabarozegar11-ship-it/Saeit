"""Behavioral regression for actual manufacturer inventory -> immutable rework queue."""
import hashlib,importlib.util,json
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
S=ROOT/"scripts/factory_global_quality_triage_v2.py"
P=ROOT/"scripts/factory_global_premium_quality_gate.py"
R=ROOT/"factory_config/forty_families.json"
spec=importlib.util.spec_from_file_location("quality_rework",S)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class GlobalTriageTests(unittest.TestCase):
    def make(self,d,name,family="F14",broken=False):
        root=Path(d)
        folder=root/"digital-products"/name;folder.mkdir(parents=True)
        zipfile=folder/(name+"-internal-qa.zip")
        zipfile.write_bytes(b"tactical-game-tests-pass-but-no-expert-reviews"*10)
        good=hashlib.sha256(zipfile.read_bytes()).hexdigest()
        record={"recipe":name,"qa_status":"passed","source_sha256":"f"*64,"artifact_sha256":
                ("0"*64 if broken else good),
                "commercial_status":"private_internal_qa_pass_not_published"}
        if family:record["family_id"]=family
        (folder/"manufacturing_manifest.json").write_text(json.dumps(record))
        return root,folder

    def test_real_technical_green_goes_to_quality_rework_not_approved(self):
        with tempfile.TemporaryDirectory() as d:
            root,folder=self.make(d,"rootline_test")
            result=m.triage_inventory(root,P,R,"cycle-123")
            self.assertEqual(result["total_products"],1)
            self.assertEqual(result["technical_passed"],1)
            self.assertEqual(result["quality_certified"],0)
            receipt=json.loads((root/"quality-excellence/rework/rootline_test/current.json").read_text())
            self.assertEqual(receipt["quality_status"],"RETURN_TO_PRODUCTION_QUALITY")
            self.assertFalse(receipt["commercial_release_allowed"])
            self.assertIn("P0_ORIGINAL_INNOVATIONS_UNPROVEN",receipt["defects"])
            self.assertIn("REWORK_NOVELTY",receipt["rework_actions"])

    def test_modified_product_is_quarantined_instead_of_false_approval(self):
        with tempfile.TemporaryDirectory() as d:
            root,folder=self.make(d,"altered_game",broken=True)
            m.triage_inventory(root,P,R,"quarantine-1")
            q=json.loads((root/"quality-excellence/rework/altered_game/current.json").read_text())
            self.assertEqual(q["quality_status"],"QUARANTINE_TECHNICAL_OR_INTEGRITY")
            self.assertIn("P0_BUILD_HASH_NOT_MATCHING_MANIFEST",q["defects"])

    def test_missing_source_digest_is_quarantined_not_counted_as_technical_pass(self):
        with tempfile.TemporaryDirectory() as d:
            root,folder=self.make(d,"legacy_source")
            mpath=folder/"manufacturing_manifest.json"
            doc=json.loads(mpath.read_text())
            doc.pop("source_sha256")
            mpath.write_text(json.dumps(doc))
            report=m.triage_inventory(root,P,R,"missing-provenance")
            self.assertEqual(report["total_products"],1)
            self.assertEqual(report["source_provenance_missing_or_invalid"],1)
            self.assertEqual(report["technical_passed"],0)
            self.assertTrue(report["all_eligible_inventory_scanned"])
            ticket=json.loads((root/"quality-excellence/rework/legacy_source/current.json").read_text())
            self.assertEqual(ticket["quality_status"],"QUARANTINE_TECHNICAL_OR_INTEGRITY")
            self.assertFalse(ticket["source_provenance_hash_present"])
            self.assertIn("P0_SOURCE_PROVENANCE_HASH_MISSING_OR_INVALID",ticket["defects"])
            self.assertIn("RECONSTRUCT_OR_AUTHENTICATE_ORIGINAL_SOURCE_PROVENANCE",
                          ticket["rework_actions"])
            self.assertFalse(ticket["commercial_release_allowed"])

    def test_inventory_over_budget_must_fail_before_writing_partial_report(self):
        with tempfile.TemporaryDirectory() as d:
            root,_=self.make(d,"first_recipe")
            root,_=self.make(d,"second_recipe")
            with self.assertRaisesRegex(ValueError,"QUALITY_INVENTORY_LIMIT_EXCEEDED:2"):
                m.triage_inventory(root,P,R,"incomplete-scan",limit=1)
            self.assertFalse((root/"quality-excellence/rework/first_recipe/current.json").exists())
            self.assertFalse((root/"quality-excellence/audit-receipts").exists())

    def test_missing_family_gets_specific_fix_not_generic_vague_quality(self):
        with tempfile.TemporaryDirectory() as d:
            root,folder=self.make(d,"unmapped_recipe",family=None)
            m.triage_inventory(root,P,R,"missing-family")
            q=json.loads((root/"quality-excellence/rework/unmapped_recipe/current.json").read_text())
            self.assertEqual(q["quality_status"],"RETURN_TO_PRODUCTION_CLASSIFICATION")
            self.assertIn("P0_UNMAPPED_PRODUCT_FAMILY",q["defects"])

    def test_repeated_audit_preserves_versioned_receipt_idempotently(self):
        with tempfile.TemporaryDirectory() as d:
            root,folder=self.make(d,"steady_recipe")
            m.triage_inventory(root,P,R,"auditA")
            first=sorted((root/"quality-excellence/rework/steady_recipe").glob("rework-*"))
            self.assertEqual(len(first),1)
            digest=hashlib.sha256(first[0].read_bytes()).hexdigest()
            m.triage_inventory(root,P,R,"auditB")
            second=sorted((root/"quality-excellence/rework/steady_recipe").glob("rework-*"))
            self.assertEqual(len(second),1)
            self.assertEqual(hashlib.sha256(second[0].read_bytes()).hexdigest(),digest)
            self.assertTrue((root/"quality-excellence/audit-receipts/audit-auditB.json").exists())

    def test_human_evaluation_pending_not_rework_when_evidence_complete(self):
        result={"blockers":[{"code":"P0_INDEPENDENT_ATTESTATION_NOT_AUTHENTICATED"},
                            {"code":"P0_WORLD_NUMBER_ONE_CLAIM_UNVERIFIED"}],
                "public_release_allowed":False}
        status,defects,pending=m.classify(result)
        self.assertEqual(status,"AWAITING_AUTHENTICATED_INDEPENDENT_REVIEW")
        self.assertEqual(defects,[])
        self.assertEqual(len(pending),2)

    def test_no_opinion_of_world_number_one_can_auto_publish(self):
        result={"blockers":[{"code":"P0_WORLD_NUMBER_ONE_CLAIM_UNVERIFIED"}],
                "public_release_allowed":False}
        status,defects,pending=m.classify(result)
        self.assertNotEqual(status,"APPROVED")
        self.assertNotIn("P0_WORLD_NUMBER_ONE_CLAIM_UNVERIFIED",defects)

    def test_fault_isolation_records_corrupt_manifest_as_quarantine(self):
        with tempfile.TemporaryDirectory() as d:
            root,folder=self.make(d,"bad_receipt")
            (folder/"manufacturing_manifest.json").write_text("{not valid json")
            m.triage_inventory(root,P,R,"corrupt")
            q=json.loads((root/"quality-excellence/rework/bad_receipt/current.json").read_text())
            self.assertEqual(q["quality_status"],"QUARANTINE_AUDIT_ERROR")
            self.assertFalse(q["commercial_release_allowed"])
            self.assertEqual(q["defects"],["P0_AUDIT_ERROR_JSONDecodeError"])

if __name__=="__main__":unittest.main()
