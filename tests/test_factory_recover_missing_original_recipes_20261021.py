import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

FILE=Path(__file__).resolve().parents[1]/"scripts/factory_recover_missing_original_recipes_20261021.py"
spec=importlib.util.spec_from_file_location("source_recovery",str(FILE))
rec=importlib.util.module_from_spec(spec);spec.loader.exec_module(rec)

class OriginalSourceRecoveryTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)/"private";self.root.mkdir()
        self.recipe="verified_calculator"
        self.product=self.root/"digital-products"/self.recipe;self.product.mkdir(parents=True)
        self.workorder=self.root/"quality-excellence"/"production-workorders"/self.recipe
        self.workorder.mkdir(parents=True)
        self.assessment=self.root/"quality-excellence"/"rework"/self.recipe
        self.assessment.mkdir(parents=True)
        self.names={"README.md":b"# Verified output\n","test_real.py":b"import unittest\nclass TestA(unittest.TestCase):\n def test_one(self):self.assertTrue(True)\n","calculator.py":b"print(1)\n"}
        self.seed()
    def source_hash(self,files):
        h=hashlib.sha256()
        for filename in sorted(files):
            h.update(filename.encode()+b"\0");h.update(files[filename])
        return h.hexdigest()
    def seed(self,files=None):
        files=files or self.names
        archive=self.product/(self.recipe+"-internal-qa.zip")
        with zipfile.ZipFile(archive,"w") as z:
            for name,data in files.items():z.writestr(self.recipe+"/"+name,data)
        digest=hashlib.sha256(archive.read_bytes()).hexdigest()
        self.meta={"recipe":self.recipe,"artifact_sha256":digest,
            "source_sha256":self.source_hash(files),
            "files":list(files),
            "qa_status":"passed","commercial_status":"private_internal_qa_pass_not_published",
            "public_listing_enabled":False,"owner_publication_approval":False}
        (self.product/"manufacturing_manifest.json").write_text(json.dumps(self.meta))
        self.assessment.joinpath("current.json").write_text(json.dumps({"artifact_sha256":digest}))
        qhash=hashlib.sha256((self.assessment/"current.json").read_bytes()).hexdigest()
        self.workorder.joinpath("current.json").write_text(json.dumps({
            "schema":"saeit.factory.production-rework-order.v1",
            "recipe":self.recipe,"source_quality_receipt_sha256":qhash,
            "artifact_sha256":digest,"unresolved_technical_or_domain_defects":[]}))
    def run_recovery(self,**kw):
        return rec.recover(self.root,**kw)
    def test_exact_byte_recovery_writes_separate_source_without_changing_original(self):
        old=(self.product/"manufacturing_manifest.json").read_bytes()
        result=self.run_recovery()
        self.assertEqual(result["totals"]["restored"],1)
        self.assertFalse(result["commercial_release_authorized"])
        dst=self.root/"recovered-original-product-recipes"/self.recipe
        self.assertEqual({p.name:p.read_bytes() for p in dst.iterdir()},self.names)
        self.assertEqual((self.product/"manufacturing_manifest.json").read_bytes(),old)
        self.assertEqual(self.run_recovery()["totals"]["previously_recovered"],1)
        receipt=json.loads((self.root/"recovered-original-product-recipes"/(".recovery-"+self.recipe+".json")).read_text())
        self.assertTrue(receipt["source_hash_verified_against_original_manifest"])
        self.assertFalse(receipt["technical_qa_retested"])
        self.assertFalse(receipt["professional_quality_1000_approved"])
    def test_corrupt_original_zip_does_not_create_source(self):
        archive=self.product/(self.recipe+"-internal-qa.zip")
        archive.write_bytes(b"corrupted")
        result=self.run_recovery()
        self.assertEqual(result["totals"]["unrecoverable_with_current_provenance"],1)
        self.assertFalse((self.root/"recovered-original-product-recipes"/self.recipe).exists())
    def test_manifest_source_hash_mismatch_is_not_synthesized(self):
        meta=self.meta.copy();meta["source_sha256"]="0"*64
        (self.product/"manufacturing_manifest.json").write_text(json.dumps(meta))
        self.assertEqual(self.run_recovery()["totals"]["unrecoverable_with_current_provenance"],1)
    def test_qa_assessment_hash_mismatch_fails_closed(self):
        (self.assessment/"current.json").write_text(json.dumps({"artifact_sha256":"0"*64}))
        self.assertEqual(self.run_recovery()["totals"]["unrecoverable_with_current_provenance"],1)
    def test_source_conflict_preserves_existing_owner_edited_source(self):
        own=self.root/"existing_source";own.mkdir()
        (own/self.recipe).mkdir()
        (own/self.recipe/"README.md").write_bytes(b"owner edits")
        report=self.run_recovery(other_roots=[own])
        self.assertEqual(report["totals"]["existing_original_source"],1)
        self.assertFalse((self.root/"recovered-original-product-recipes"/self.recipe).exists())
        self.assertEqual((own/self.recipe/"README.md").read_bytes(),b"owner edits")
    def test_archive_member_traversal_is_rejected(self):
        files={"README.md":b"# X","test_real.py":b"assert True","../escape.txt":b"escape"}
        self.seed(files=files)
        report=self.run_recovery()
        self.assertEqual(report["totals"]["unrecoverable_with_current_provenance"],1)
        self.assertFalse((self.root/"escape.txt").exists())
    def test_missing_source_tests_is_not_a_valid_buildable_recipe(self):
        self.seed(files={"README.md":b"# X", "main.py":b"print(1)"})
        self.assertEqual(self.run_recovery()["totals"]["unrecoverable_with_current_provenance"],1)
    def test_previously_recovered_source_must_remain_byte_exact(self):
        self.assertEqual(self.run_recovery()["totals"]["restored"], 1)
        target=self.root/"recovered-original-product-recipes"/self.recipe
        (target/"README.md").write_bytes(b"tampered source, no longer verified")
        result=self.run_recovery()
        self.assertEqual(result["totals"]["unrecoverable_with_current_provenance"], 1)
        self.assertEqual(result["totals"]["remediation_RECOVERY_PREVIOUS_FILES_MISMATCH"], 1)
        self.assertNotIn("previously_recovered", result["totals"])
        self.assertEqual((target/"README.md").read_bytes(),
                         b"tampered source, no longer verified")

    def test_previous_recovery_missing_receipt_never_counts_as_success(self):
        self.assertEqual(self.run_recovery()["totals"]["restored"], 1)
        proof=self.root/"recovered-original-product-recipes"/(".recovery-"+self.recipe+".json")
        proof.unlink()
        result=self.run_recovery()
        self.assertEqual(result["totals"]["unrecoverable_with_current_provenance"], 1)
        self.assertNotIn("previously_recovered", result["totals"])
        self.assertFalse(proof.exists())

    def test_previous_recovery_with_changed_qa_workorder_is_invalid(self):
        self.assertEqual(self.run_recovery()["totals"]["restored"], 1)
        order=self.workorder/"current.json"
        work=json.loads(order.read_text())
        work["unresolved_technical_or_domain_defects"]=["P0_BUILD_HASH_MISMATCH"]
        order.write_text(json.dumps(work))
        result=self.run_recovery()
        self.assertEqual(result["totals"]["remediation_RECOVERY_PREVIOUS_PROOF_MISMATCH"], 1)
        self.assertNotIn("previously_recovered", result["totals"])

    def test_preexisting_symlink_target_is_not_overwritten(self):
        target=self.root/"recovered-original-product-recipes";target.mkdir()
        (target/self.recipe).symlink_to(self.product,target_is_directory=True)
        self.assertEqual(self.run_recovery()["totals"]["unrecoverable_with_current_provenance"],1)
        self.assertTrue((target/self.recipe).is_symlink())


class ActiveProductAllowlistTests(unittest.TestCase):
    def test_accepts_line_41_single_product_and_legacy_five(self):
        with tempfile.TemporaryDirectory() as directory:
            slots = Path(directory) / "slots.json"
            for capacity in (1, 5):
                recipes = ["product_%02d" % n for n in range(1, capacity + 1)]
                slots.write_text(json.dumps({
                    "schema": "saeit.factory.product-slots.v1",
                    "line_id": 41 if capacity == 1 else None,
                    "capacity": capacity,
                    "active": [{"recipe": recipe} for recipe in recipes],
                }))
                self.assertEqual(rec.active_product_allowlist(slots), set(recipes))

    def test_rejects_family_count_as_product_slot_capacity(self):
        with tempfile.TemporaryDirectory() as directory:
            slots = Path(directory) / "slots.json"
            slots.write_text(json.dumps({
                "schema": "saeit.factory.product-slots.v1",
                "capacity": 40,
                "active": [{"recipe": "product_%02d" % n} for n in range(1, 41)],
            }))
            with self.assertRaisesRegex(ValueError, "CAPACITY_MISMATCH"):
                rec.active_product_allowlist(slots)
if __name__=="__main__":unittest.main()
