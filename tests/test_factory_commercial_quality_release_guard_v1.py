"""Objective release guard: real QA, rights and full-artifact review are separate."""
import hashlib,importlib.util,json,zipfile
from datetime import datetime,timezone
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"scripts/factory_commercial_quality_release_guard_v1.py"
spec=importlib.util.spec_from_file_location("factory_release_guard_1000",SRC)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class PublicReleaseSafety(unittest.TestCase):
    def test_new_factory_build_cannot_be_published_without_functional_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            package=root/"example.zip";package.write_bytes(b"real_new_factory_package")
            sha=hashlib.sha256(package.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,"OBJECTIVE_GATE_FUNCTIONAL_EVIDENCE_MISSING"):
                mod.require_quality_clearance(root,"test_product",sha,
                    {"professional_quality_standard":"objective_acceptance_v1"},package)
    def test_old_free_release_is_not_automatically_authorized(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            package=root/"legacy.zip";package.write_bytes(b"old free published product")
            digest=hashlib.sha256(package.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,"OBJECTIVE_GATE_FUNCTIONAL_EVIDENCE_MISSING"):
                mod.require_quality_clearance(root,"farm_enterprise_economics",digest,
                                              {"qa_status":"passed"},package)
    def test_real_qa_and_exact_artifact_review_allow_objective_readiness(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            package=root/"sample.zip";package.write_bytes(b"versioned functional product")
            digest=hashlib.sha256(package.read_bytes()).hexdigest()
            manifest={"recipe":"test_product","artifact_sha256":digest,"qa_status":"passed",
                      "qa_measurements":{"tests_run":20,"successful_tests":20},
                      "public_listing_enabled":False,"owner_publication_approval":False,
                      "professional_quality_standard":"objective_acceptance_v1"}
            original=mod.require_chatgpt_final_review
            mod.require_chatgpt_final_review=lambda *args: {"status":"CHATGPT_FINAL_REVIEW_VERIFIED"}
            try:
                result=mod.require_quality_clearance(root,"test_product",digest,manifest,package)
            finally:
                mod.require_chatgpt_final_review=original
            self.assertEqual(result["status"],"VERIFIED_OBJECTIVE_RELEASE_READINESS")
            self.assertEqual(result["functional_tests_verified"],20)
    def test_objective_final_review_is_bound_to_every_zip_byte(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            product=root/"product.zip"
            with zipfile.ZipFile(product,"w") as zipped:
                zipped.writestr("test_product/README.md",b"Real usable instructions\n")
            digest=hashlib.sha256(product.read_bytes()).hexdigest()
            manifest={"recipe":"test_product","artifact_sha256":digest,"qa_status":"passed",
                      "qa_measurements":{"tests_run":5,"successful_tests":5},
                      "public_listing_enabled":False,"owner_publication_approval":False}
            blob=b"Real usable instructions\n"
            manifest_sha=hashlib.sha256(json.dumps(manifest,ensure_ascii=False,sort_keys=True,
                                                    separators=(",",":")).encode()).hexdigest()
            review={"schema":mod.CHATGPT_REVIEW_SCHEMA,"reviewer":mod.CHATGPT_REVIEWER,
                    "reviewer_role":"owner-delegated final product quality reviewer",
                    "decision":"approved_for_store","recipe":"test_product",
                    "artifact_sha256":digest,"manifest_sha256":manifest_sha,
                    "reviewed_at_utc":datetime.now(timezone.utc).isoformat(),
                    "review_summary":"Verified scope, limitations, product behavior, ownership, privacy and delivery. "*5,
                    "unresolved_findings":[],
                    "checklist":{key:True for key in mod.CHATGPT_REVIEW_CHECKS},
                    "reviewed_files":[{"path":"test_product/README.md",
                                       "sha256":hashlib.sha256(blob).hexdigest(),"size":len(blob)}]}
            dest=root/"quality-clearance"/"test_product"/digest
            dest.mkdir(parents=True)
            receipt=dest/"chatgpt-final-review.json"
            receipt.write_text(json.dumps(review))
            result=mod.require_quality_clearance(root,"test_product",digest,manifest,product)
            self.assertEqual(result["status"],"VERIFIED_OBJECTIVE_RELEASE_READINESS")
            review["checklist"].pop("extracted_customer_zip_checks")
            receipt.write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError,"CHATGPT_FINAL_REVIEW_CHECKLIST_INCOMPLETE"):
                mod.require_quality_clearance(root,"test_product",digest,manifest,product)
    def test_public_release_rights_gate_still_blocks_without_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            package=root/"legacy.zip";package.write_bytes(b"public package")
            digest=hashlib.sha256(package.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,"RIGHTS_CLEARANCE_EVIDENCE_MISSING"):
                mod.require_rights_clearance(root,"farm_enterprise_economics",digest,package)

    def test_new_factory_cannot_smuggle_relative_path_to_quality_files(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            file=root/"factory.zip";file.write_bytes(b"data")
            with self.assertRaises(ValueError):
                mod.require_quality_clearance(root,"../../private","0"*64,
                    {"professional_quality_standard":"objective_acceptance_v1"},file)
if __name__=="__main__":unittest.main()
