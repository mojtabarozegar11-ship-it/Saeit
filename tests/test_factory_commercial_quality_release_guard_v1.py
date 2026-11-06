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


def buyer_value_fixture(root, recipe, digest, *, paid=False, real_buyer=False):
    folder=root/"quality-clearance"/recipe/digest
    proofs=folder/"buyer-proof"
    proofs.mkdir(parents=True,exist_ok=True)
    cases=[]
    for index in range(2):
        filename=f"observed-case-{index}.txt"
        content=(f"Observed result for real customer scenario {index}: "
                 "Inputs, actual outputs, limitations, and repeatable steps independently recorded. "*2).encode()
        (proofs/filename).write_bytes(content)
        cases.append({"buyer_task":f"Buyer investigates scenario {index} for actual business decisions",
                      "reproduction_steps":"Extract the package, input the provided data and compare every output to the recorded observations.",
                      "observed_outcome":"A verified, repeatable numerical result for the buyer's specified scenario.",
                      "decision_enabled":"Buyer can identify if the tested option fits their resource constraint.",
                      "proof_filename":filename,"proof_sha256":hashlib.sha256(content).hexdigest()})
    signals=[{"kind":"public_market_research", "source_url":"https://extension.psu.edu/budgeting-for-agricultural-decision-making",
              "finding":"Official agricultural extension documents the need for enterprise budget comparison.",
              "limitations":"This source does not establish willingness to pay or product-specific purchase intent."}]
    if real_buyer:
        feedback=b"Consent-cleared, independently verified buyer feedback record and detailed need. "*2
        (proofs/"buyer-feedback.txt").write_bytes(feedback)
        signals.append({"kind":"documented_customer_feedback",
                        "finding":"A buyer confirmed a specific workflow need after seeing the packaged deliverable.",
                        "limitations":"One buyer's response cannot predict broader sales or retention.",
                        "proof_filename":"buyer-feedback.txt", "proof_sha256":hashlib.sha256(feedback).hexdigest()})
    document={"schema":mod.VALUE_EVIDENCE_SCHEMA,"recipe":recipe,"artifact_sha256":digest,
              "target_buyer":"A manager responsible for comparing agricultural enterprises under constrained resources.",
              "customer_problem":"They need a fast, consistent way to compare profitability and downside cases.",
              "measurable_buyer_outcome":"Identify the break-even threshold and sensitivity to changes in sales and price.",
              "scope_limitations":"This model does not include all cash-flow, tax, depreciation or financing requirements.",
              "why_customer_would_choose_this":"Provides an offline reproducible analysis in two interfaces with consistent outputs.",
              "alternatives":[
                  {"name":f"Extension budgeting method {i}","source_url":([
                       "https://extension.psu.edu/budgeting-for-agricultural-decision-making",
                       "https://extension.umn.edu/agriculture/farm-operations-and-systems/agricultural-business-management/farm-finance"
                   ][i]),
                   "what_it_already_solves":"Documents comprehensive budgeting methods and helps buyers understand costs.",
                   "our_verified_advantage":"An offline calculator allows interactive case comparison and repeatable exports."}
                  for i in range(2)],
              "customer_workflows":cases,
              "commercial_offer":{"model":"paid" if paid else "free","currency":"USD",
                   "price_minor_units":990 if paid else 0,
                   "price_justification":"Price considers comparable available free resources and the validated buyer utility.",
                   "delivery_method":"A verified exact-release ZIP is delivered through the storefront download process.",
                   "license_terms":"Single buyer may use the copy within a documented commercial enterprise.",
                   "support_process":"Buyer can reach the publisher about setup or file corruption through contact support.",
                   "refund_or_remediation_policy":"Non-working downloads receive an accessible replacement and a refund review."},
              "demand_signals":signals}
    path=folder/"buyer-value-evidence.json"
    path.write_text(json.dumps(document),encoding="utf8")
    return path,document

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
            buyer_value_fixture(root,"test_product",digest)
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
            evidence_file,_=buyer_value_fixture(root,"test_product",digest)
            blob=b"Real usable instructions\n"
            manifest_sha=hashlib.sha256(json.dumps(manifest,ensure_ascii=False,sort_keys=True,
                                                    separators=(",",":")).encode()).hexdigest()
            review={"schema":mod.CHATGPT_REVIEW_SCHEMA,"reviewer":mod.CHATGPT_REVIEWER,
                    "reviewer_role":"owner-delegated final product quality reviewer",
                    "decision":"approved_for_store","recipe":"test_product",
                    "artifact_sha256":digest,"manifest_sha256":manifest_sha,
                    "reviewed_at_utc":datetime.now(timezone.utc).isoformat(),
                    "review_summary":"Verified scope, limitations, product behavior, ownership, privacy and delivery. "*5,
                    "buyer_value_evidence_sha256":hashlib.sha256(evidence_file.read_bytes()).hexdigest(),
                    "unresolved_findings":[],
                    "checklist":{key:True for key in mod.CHATGPT_REVIEW_CHECKS},
                    "reviewed_files":[{"path":"test_product/README.md",
                                       "sha256":hashlib.sha256(blob).hexdigest(),"size":len(blob)}]}
            dest=root/"quality-clearance"/"test_product"/digest
            dest.mkdir(parents=True,exist_ok=True)
            receipt=dest/"chatgpt-final-review.json"
            receipt.write_text(json.dumps(review))
            result=mod.require_quality_clearance(root,"test_product",digest,manifest,product)
            self.assertEqual(result["status"],"VERIFIED_OBJECTIVE_RELEASE_READINESS")
            review["checklist"].pop("extracted_customer_zip_checks")
            receipt.write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError,"CHATGPT_FINAL_REVIEW_CHECKLIST_INCOMPLETE"):
                mod.require_quality_clearance(root,"test_product",digest,manifest,product)

    def test_technical_success_does_not_imply_commercial_value(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            package=root/"sample.zip";package.write_bytes(b"test product with valid unit tests")
            digest=hashlib.sha256(package.read_bytes()).hexdigest()
            manifest={"recipe":"test_product","artifact_sha256":digest,"qa_status":"passed",
                      "qa_measurements":{"tests_run":3,"successful_tests":3},
                      "public_listing_enabled":False,"owner_publication_approval":False}
            with self.assertRaisesRegex(ValueError,"BUYER_VALUE_EVIDENCE_MISSING"):
                mod.require_quality_clearance(root,"test_product",digest,manifest,package)

    def test_paid_product_needs_documented_real_buyer_signal(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); digest="a"*64
            path,_=buyer_value_fixture(root,"test_product",digest,paid=True)
            with self.assertRaisesRegex(ValueError,"BUYER_VALUE_PAID_DEMAND_NOT_VALIDATED"):
                mod.require_buyer_value_evidence(root,"test_product",digest)
            path,_=buyer_value_fixture(root,"test_product",digest,paid=True,real_buyer=True)
            self.assertTrue(mod.require_buyer_value_evidence(root,"test_product",digest)
                            ["real_buyer_demand_documented"])

    def test_tampered_buyer_proof_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); digest="b"*64
            path,document=buyer_value_fixture(root,"test_product",digest)
            proof=path.parent/"buyer-proof"/document["customer_workflows"][0]["proof_filename"]
            proof.write_bytes(b"this no longer agrees with its declared SHA")
            with self.assertRaisesRegex(ValueError,"BUYER_VALUE_PROOF_NOT_VERIFIED"):
                mod.require_buyer_value_evidence(root,"test_product",digest)

    def test_forged_comparison_does_not_pass_value_gate(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); digest="c"*64
            path,document=buyer_value_fixture(root,"test_product",digest)
            document["alternatives"]=[]
            path.write_text(json.dumps(document),encoding="utf8")
            with self.assertRaisesRegex(ValueError,"BUYER_VALUE_ALTERNATIVES_MISSING"):
                mod.require_buyer_value_evidence(root,"test_product",digest)

    def test_same_comparison_url_and_same_proof_cannot_count_twice(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); digest="d"*64
            path,document=buyer_value_fixture(root,"test_product",digest)
            document["alternatives"][1]["source_url"]=document["alternatives"][0]["source_url"]
            path.write_text(json.dumps(document),encoding="utf8")
            with self.assertRaisesRegex(ValueError,"BUYER_VALUE_ALTERNATIVES_DUPLICATED"):
                mod.require_buyer_value_evidence(root,"test_product",digest)
            document["alternatives"][1]["source_url"]="https://extension.umn.edu/agriculture/farm-operations-and-systems/agricultural-business-management/farm-finance"
            document["customer_workflows"][1]["proof_sha256"]=document["customer_workflows"][0]["proof_sha256"]
            path.write_text(json.dumps(document),encoding="utf8")
            with self.assertRaisesRegex(ValueError,"BUYER_VALUE_WORKFLOW_DUPLICATED"):
                mod.require_buyer_value_evidence(root,"test_product",digest)
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
