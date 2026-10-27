"""Regression: real QA workorders can dispatch isolated technical rebuilds, never sales."""
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import tempfile
import unittest
import zipfile
import shutil
from unittest.mock import patch

FILE=Path(__file__).resolve().parents[1]/"scripts/factory_qa_native_rebuild_bridge_20261021.py"
spec=importlib.util.spec_from_file_location("factory_tested_rebuild",str(FILE))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class FakeMaker:
    calls=0
    @staticmethod
    def inspect_recipe(path):
        return "Verified synthetic",("README.md",)
    @staticmethod
    def source_digest(path,files):
        return hashlib.sha256((path/"README.md").read_bytes()).hexdigest()
    @staticmethod
    def sha256_file(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    @classmethod
    def manufacture(cls,recipe,source_root,output):
        cls.calls+=1
        folder=output/recipe;folder.mkdir(parents=True,exist_ok=True)
        artifact=folder/(recipe+"-internal-qa.zip")
        artifact.write_bytes(b"synthetic safe private builder fixture")
        manifest={"qa_status":"passed",
                  "source_sha256":cls.source_digest(source_root/recipe,("README.md",)),
                  "artifact_sha256":cls.sha256_file(artifact)}
        (folder/"manufacturing_manifest.json").write_text(json.dumps(manifest))
        return {"qa_status":"passed"}

class QARebuildTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.source=self.root/"generated-product-recipes"
        self.source.mkdir()
        self.quality=self.root/"quality-excellence/production-workorders"
        self.quality.mkdir(parents=True)
        FakeMaker.calls=0
    def seed(self,name="synth_abc123",*,defects=None,source_bytes=b"v2 changed"):
        item=self.source/name;item.mkdir()
        (item/"README.md").write_bytes(source_bytes)
        order=self.quality/name;order.mkdir()
        (order/"current.json").write_text(json.dumps({
            "schema":"saeit.factory.production-rework-order.v1",
            "recipe":name,
            "family_id":"F28",
            "source_quality_receipt_sha256":"a"*64,
            "unresolved_technical_or_domain_defects":defects or []}))
        original=self.root/"digital-products"/name;original.mkdir(parents=True)
        (original/"manufacturing_manifest.json").write_text(json.dumps({
            "source_sha256":"b"*64,"qa_status":"passed"}))
        return item,original
    def run_bridge(self):
        with patch.object(m,"load_maker",return_value=FakeMaker):
            return m.execute(self.root,self.source,FILE,limit=2)
    def seed_archived_only(self,name="synth_abc123",*,tamper=False,flat=False):
        item,original=self.seed(name=name,defects=["P0_BUILD_ARCHIVE_INVALID"])
        source_bytes=(item/"README.md").read_bytes()
        archive=original/(item.name+"-internal-qa.zip")
        with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(("README.md" if flat else item.name+"/README.md"),source_bytes)
        (original/"manufacturing_manifest.json").write_text(json.dumps({
            "schema_version":2,"recipe":item.name,"files":["README.md"],
            "source_sha256":FakeMaker.source_digest(item,("README.md",)),
            "artifact_sha256":FakeMaker.sha256_file(archive),
            "qa_status":"passed","commercial_status":"private_internal_qa_pass_not_published",
            "public_listing_enabled":False,"owner_publication_approval":False}))
        artifact=FakeMaker.sha256_file(archive)
        receipt=self.root/"quality-excellence"/"rework"/item.name/"current.json"
        receipt.parent.mkdir(parents=True,exist_ok=True)
        receipt.write_text(json.dumps({"artifact_sha256":artifact}))
        order=self.quality/item.name/"current.json"
        order_data=json.loads(order.read_text())
        order_data["artifact_sha256"]=artifact
        order_data["source_quality_receipt_sha256"]=hashlib.sha256(receipt.read_bytes()).hexdigest()
        order.write_text(json.dumps(order_data))
        if tamper:archive.write_bytes(archive.read_bytes()+b"tamper")
        shutil.rmtree(item)
        return item.name,archive
    def test_failed_first_recipes_cannot_starve_remaining_rebuild_orders(self):
        for recipe in ("synth_first", "synth_second", "synth_third"):
            self.seed(name=recipe)
        class BrokenMaker(FakeMaker):
            attempted = []
            @classmethod
            def manufacture(cls, recipe, source_root, output):
                cls.attempted.append(recipe)
                raise RuntimeError("fixture build failure")
        with patch.object(m, "load_maker", return_value=BrokenMaker):
            for _ in range(9):
                result = m.execute(self.root, self.source, FILE, limit=1)
                self.assertEqual(result["rebuild_attempted"], 1)
                self.assertEqual(result["failed"], 1)
            exhausted = m.execute(self.root, self.source, FILE, limit=1)
        self.assertEqual(BrokenMaker.attempted,
                         ["synth_first", "synth_second", "synth_third"] * 3)
        self.assertEqual(exhausted["rebuild_attempted"], 0)
        self.assertEqual(exhausted["root_cause_review_pending"], 3)
        self.assertEqual(exhausted["technical_candidates_verified"], 0)
        self.assertFalse(exhausted["commercial_release_authorized"])
        for recipe in ("synth_first", "synth_second", "synth_third"):
            logs = list((self.root / "quality-excellence" / "native-rebuild-receipts" /
                         recipe).glob("failures-*.json"))
            self.assertEqual(len(logs), 1)
            record = json.loads(logs[0].read_text())
            self.assertEqual(record["attempts"], 3)
            self.assertEqual(record["status"], "ROOT_CAUSE_REVIEW_REQUIRED")

    def test_symlink_rebuild_cursor_is_rejected_before_builder(self):
        self.seed()
        cursor = self.root / "quality-excellence" / "native-rebuild-cursor.json"
        cursor.symlink_to(self.root / "outside.json")
        with patch.object(m, "load_maker", return_value=FakeMaker):
            with self.assertRaisesRegex(ValueError, "UNSAFE_REBUILD_CURSOR"):
                m.execute(self.root, self.source, FILE, limit=1)
        self.assertEqual(FakeMaker.calls, 0)

    def test_one_product_per_family_is_rebuilt_in_a_sweep(self):
        self.seed(name="synth_aaa111")
        self.seed(name="synth_bbb222")
        with patch.object(m,"load_maker",return_value=FakeMaker):
            result=m.execute(self.root,self.source,FILE,limit=40)
        self.assertEqual(result["rebuild_attempted"],1)
        self.assertEqual(result["technical_candidates_verified"],1)
        self.assertEqual(FakeMaker.calls,1)

    def test_excluded_family_does_not_enter_rebuild_loop(self):
        self.seed()
        with patch.object(m,"load_maker",return_value=FakeMaker):
            result=m.execute(self.root,self.source,FILE,limit=40,
                             excluded_families={"F28"})
        self.assertEqual(result["rebuild_attempted"],0)
        self.assertEqual(FakeMaker.calls,0)

    def test_changed_native_source_makes_real_private_candidate_once(self):
        _,original=self.seed()
        previous=(original/"manufacturing_manifest.json").read_bytes()
        r=self.run_bridge()
        self.assertEqual(r["technical_candidates_verified"],1)
        self.assertEqual(r["rebuild_attempted"],1)
        self.assertEqual(FakeMaker.calls,1)
        self.assertFalse(r["commercial_release_authorized"])
        self.assertFalse(r["professional_quality_1000_verified"])
        self.assertEqual(previous,(original/"manufacturing_manifest.json").read_bytes())
        self.assertEqual(self.run_bridge()["rebuild_attempted"],0)
        self.assertEqual(FakeMaker.calls,1)
    def test_no_source_change_and_human_only_defect_does_not_rebuild(self):
        path,original=self.seed(source_bytes=b"unchanged")
        digest=FakeMaker.source_digest(path,("README.md",))
        (original/"manufacturing_manifest.json").write_text(json.dumps({"source_sha256":digest}))
        r=self.run_bridge()
        self.assertEqual(r["rebuild_attempted"],0)
        self.assertEqual(r["unchanged_or_human_only"],1)
    def test_same_source_with_mechanical_defect_rebuilds(self):
        path,original=self.seed(defects=["P0_BUILD_HASH_NOT_MATCHING_MANIFEST"])
        (original/"manufacturing_manifest.json").write_text(json.dumps({
            "source_sha256":FakeMaker.source_digest(path,("README.md",))}))
        r=self.run_bridge()
        self.assertEqual(r["technical_candidates_verified"],1)
    def test_verified_original_zip_recovers_missing_recipe_for_rework(self):
        name,archive=self.seed_archived_only()
        before=archive.read_bytes()
        result=self.run_bridge()
        self.assertEqual(result["archive_sources_recovered"],1)
        self.assertEqual(result["missing_source"],0)
        self.assertEqual(result["rebuild_attempted"],1)
        self.assertEqual(result["technical_candidates_verified"],1)
        self.assertEqual((self.root/"quality-excellence"/"recovered-verified-sources"/name/"README.md").read_bytes(),b"v2 changed")
        self.assertEqual(archive.read_bytes(),before)
    def test_original_sha_can_verify_exact_zip_inventory_when_index_omitted(self):
        name,original_zip=self.seed_archived_only()
        meta=self.root/"digital-products"/name/"manufacturing_manifest.json"
        document=json.loads(meta.read_text())
        original_sha=document.pop("source_sha256")
        self.assertRegex(original_sha,r"^[a-f0-9]{64}$")
        document["source_sha256"]=original_sha
        document.pop("files")
        meta.write_text(json.dumps(document))
        before=original_zip.read_bytes()
        outcome=self.run_bridge()
        self.assertEqual(outcome["archive_sources_recovered"],1)
        self.assertEqual(outcome["missing_source"],0)
        self.assertEqual(outcome["technical_candidates_verified"],1)
        self.assertEqual(before,original_zip.read_bytes())
        self.assertFalse(outcome["commercial_release_authorized"])
    def test_malformed_explicit_file_index_remains_blocked(self):
        name,_=self.seed_archived_only()
        meta=self.root/"digital-products"/name/"manufacturing_manifest.json"
        document=json.loads(meta.read_text())
        document["files"]=["README.md","README.md"]
        meta.write_text(json.dumps(document))
        result=self.run_bridge()
        self.assertEqual(result["archive_sources_recovered"],0)
        self.assertEqual(result["archive_recovery_rejection_reasons"]["source_file_inventory_not_verifiable"],1)
    def test_nonstr_file_index_returns_recoverable_error_not_crash(self):
        name,_=self.seed_archived_only()
        meta=self.root/"digital-products"/name/"manufacturing_manifest.json"
        document=json.loads(meta.read_text())
        document["files"]=["README.md",{"not":"a string"}]
        meta.write_text(json.dumps(document))
        result=self.run_bridge()
        self.assertEqual(result["archive_sources_recovered"],0)
        self.assertEqual(result["archive_recovery_rejection_reasons"]["source_file_inventory_not_verifiable"],1)
    def test_receipt_bound_archive_without_original_source_manifest_is_rejected(self):
        name,_=self.seed_archived_only()
        original=self.root/"digital-products"/name
        (original/"manufacturing_manifest.json").write_text(json.dumps({"legacy":True}))
        result=self.run_bridge()
        self.assertEqual(result["archive_sources_recovered"],0)
        self.assertEqual(result["missing_source"],1)
        self.assertEqual(result["rebuild_attempted"],0)
        self.assertEqual(result["archive_recovery_rejection_reasons"]["source_manifest_technical_quality_unverified"],1)
    def test_receipt_bound_archive_with_wrong_original_source_sha_is_rejected(self):
        name,_=self.seed_archived_only()
        original=self.root/"digital-products"/name
        meta=json.loads((original/"manufacturing_manifest.json").read_text())
        meta["source_sha256"]="0"*64
        (original/"manufacturing_manifest.json").write_text(json.dumps(meta))
        result=self.run_bridge()
        self.assertEqual(result["archive_sources_recovered"],0)
        self.assertEqual(result["missing_source"],1)
        self.assertEqual(result["archive_recovery_rejection_reasons"]["source_hash_mismatch"],1)
    def test_receipt_bound_flat_archive_recovers_only_testable_source(self):
        self.seed_archived_only(flat=True)
        result=self.run_bridge()
        self.assertEqual(result["archive_sources_recovered"],1)
        self.assertEqual(result["technical_candidates_verified"],1)
    def test_tampered_original_zip_never_becomes_rebuild_source(self):
        self.seed_archived_only(tamper=True)
        result=self.run_bridge()
        self.assertEqual(result["archive_sources_recovered"],0)
        self.assertEqual(result["archive_recovery_rejected"],1)
        self.assertEqual(result["missing_source"],1)
        self.assertEqual(result["rebuild_attempted"],0)
    def test_recovery_root_is_reused_across_recipes_without_ambiguity(self):
        self.seed_archived_only("synth_first")
        self.seed_archived_only("synth_other")
        result=self.run_bridge()
        self.assertEqual(result["technical_candidates_verified"],2)
        self.assertEqual(result["duplicate_recipe_roots_blocked"],0)
    def test_does_not_mutate_original_stock_on_failed_rebuild(self):
        _,original=self.seed()
        saved=(original/"manufacturing_manifest.json").read_bytes()
        with patch.object(m,"load_maker",side_effect=ValueError("not installed")):
            with self.assertRaises(ValueError):m.execute(self.root,self.source,FILE)
        self.assertEqual(saved,(original/"manufacturing_manifest.json").read_bytes())
    def test_static_installed_recipe_is_rebuilt_from_second_verified_root(self):
        static=self.root/"canonical-factory-runtime"/"product_recipes"
        static.mkdir(parents=True)
        source,original=self.seed(name="farm_enterprise_economics")
        (static/source.name).mkdir()
        (static/source.name/"README.md").write_bytes(source.joinpath("README.md").read_bytes())
        source.joinpath("README.md").unlink()
        source.rmdir()
        before=(original/"manufacturing_manifest.json").read_bytes()
        with patch.object(m,"load_maker",return_value=FakeMaker):
            first=m.execute(self.root,self.source,FILE,limit=2,
                            additional_source_roots=[static])
            again=m.execute(self.root,self.source,FILE,limit=2,
                            additional_source_roots=[static])
        self.assertEqual(first["sources_available"],1)
        self.assertEqual(first["missing_source"],0)
        self.assertEqual(first["source_root_hits"],[0,1])
        self.assertEqual(first["technical_candidates_verified"],1)
        self.assertEqual(FakeMaker.calls,1)
        self.assertEqual(again["rebuild_attempted"],0)
        self.assertEqual(before,(original/"manufacturing_manifest.json").read_bytes())
        proofs=list((self.root/"quality-excellence"/"native-rebuild-receipts"/source.name).glob("source-*.json"))
        self.assertEqual(len(proofs),1)
        self.assertEqual(json.loads(proofs[0].read_text())["source_root_slot"],1)

    def test_real_factory_layout_autodiscovers_installed_native_sources(self):
        # Mirror the VPS roots used by the cron manufacturer and QA bridge.
        factory_base=self.root/"factory-runtime"
        self.root=factory_base/"private"/"autonomous-product-cycle"
        self.source=self.root/"generated-product-recipes"
        self.source.mkdir(parents=True)
        self.quality=self.root/"quality-excellence/production-workorders"
        self.quality.mkdir(parents=True)
        item,original=self.seed(name="farm_enterprise_economics")
        native=factory_base/"operations/autonomous-product-runtime/product_recipes"
        native.mkdir(parents=True)
        target=native/item.name
        item.rename(target)
        with patch.object(m,"load_maker",return_value=FakeMaker):
            result=m.execute(self.root,self.source,FILE,limit=2)
        self.assertEqual(result["verified_source_roots"],2)
        self.assertEqual(result["source_root_hits"],[0,1])
        self.assertEqual(result["technical_candidates_verified"],1)
        self.assertEqual(result["missing_source"],0)

    def test_duplicate_recipe_sources_refuse_ambiguous_rebuilding(self):
        source,original=self.seed(name="synth_abc123")
        other=self.root/"canonical-factory-runtime"/"product_recipes"
        other.mkdir(parents=True)
        (other/source.name).mkdir()
        (other/source.name/"README.md").write_bytes(b"unrelated")
        with patch.object(m,"load_maker",return_value=FakeMaker):
            result=m.execute(self.root,self.source,FILE,
                             additional_source_roots=[other])
        self.assertEqual(result["duplicate_recipe_roots_blocked"],1)
        self.assertEqual(result["technical_candidates_verified"],0)
        self.assertEqual(FakeMaker.calls,0)

    def test_unsafe_or_duplicate_extra_roots_fail_before_rework(self):
        self.seed()
        bad=self.root/"foreign";bad.mkdir()
        alias=self.root/"unsafe-link"
        alias.symlink_to(bad,target_is_directory=True)
        with patch.object(m,"load_maker",return_value=FakeMaker):
            with self.assertRaisesRegex(ValueError,"UNSAFE_OR_MISSING"):
                m.execute(self.root,self.source,FILE,additional_source_roots=[alias])
            with self.assertRaisesRegex(ValueError,"DUPLICATE_SOURCE_ROOT"):
                m.execute(self.root,self.source,FILE,additional_source_roots=[self.source])
            with self.assertRaisesRegex(ValueError,"BOUNDED_SOURCE_ROOTS"):
                m.execute(self.root,self.source,FILE,
                          additional_source_roots=[bad,bad,bad])
        self.assertEqual(FakeMaker.calls,0)

    def test_missing_source_archive_classifies_customer_material_without_promotion(self):
        import zipfile
        item,original=self.seed("archived_legacy_product")
        (item/"README.md").unlink();item.rmdir()
        (original/"manufacturing_manifest.json").write_text(json.dumps({"qa_status":"passed","recipe":"archived_legacy_product"}))
        path=original/"archived_legacy_product-internal-qa.zip"
        with zipfile.ZipFile(path,"w") as zf:
            zf.writestr("download/report.pdf",b"%PDF-1.4 fake example")
            zf.writestr("download/readme.txt",b"not executable source")
        facts=m.classify_unrecoverable_artifact(self.root,"archived_legacy_product")
        self.assertEqual(facts["customer_delivery_layout_not_source_recipe"],1)
        self.assertEqual(facts["no_embedded_source_tests"],1)
        self.assertEqual(facts["contains_document"],1)
        self.assertEqual(facts["source_hash_absent"],1)
        self.assertEqual(facts["source_file_manifest_absent"],1)
        self.assertNotIn("download",repr(facts))
        result=self.run_bridge()
        self.assertEqual(result["missing_source"],1)
        self.assertEqual(result["legacy_source_gap_causes"]["contains_document"],1)
        self.assertEqual(result["technical_candidates_verified"],0)
        self.assertFalse(result["commercial_release_authorized"])

    def test_diagnostic_rejects_symlink_to_other_product_archive(self):
        item,old=self.seed("legacy_symlink")
        (item/"README.md").unlink();item.rmdir()
        (old/"legacy_symlink-internal-qa.zip").symlink_to(self.root/"not-a-zip")
        facts=m.classify_unrecoverable_artifact(self.root,"legacy_symlink")
        self.assertEqual(facts,{"unsafe_stock_path":1})

    def test_document_edition_returns_to_existing_rework_and_is_not_rebuilt_identically(self):
        edition="edition_"+"a"*24
        source=self.root/"quality-excellence"/"document-edition-sources"/edition
        source.mkdir(parents=True)
        (source/"README.md").write_text("# Safe generated edition")
        manuf=self.root/"quality-excellence"/"document-edition-private-stock"/edition
        manuf.mkdir(parents=True)
        source_hash=FakeMaker.source_digest(source,("README.md",))
        (manuf/"manufacturing_manifest.json").write_text(json.dumps({
            "recipe":edition,"source_sha256":source_hash,"qa_status":"passed"}))
        order=self.quality/edition
        order.mkdir()
        (order/"current.json").write_text(json.dumps({
            "schema":"saeit.factory.production-rework-order.v1",
            "recipe":edition,
            "source_quality_receipt_sha256":"a"*64,
            "unresolved_technical_or_domain_defects":[
                "P0_PROOF_MISSING:independent_expert_review"]}))
        with patch.object(m,"load_maker",return_value=FakeMaker):
            actual=m.execute(self.root,self.source,FILE,limit=2)
        self.assertEqual(actual["sources_available"],1)
        self.assertEqual(actual["missing_source"],0)
        self.assertEqual(actual["unchanged_or_human_only"],1)
        self.assertEqual(actual["rebuild_attempted"],0)
        self.assertEqual(actual["document_editions_queued_for_strict_review"],1)
        self.assertFalse(actual["commercial_release_authorized"])

    def test_untrusted_source_symlink_is_not_executed(self):
        original=self.root/"foreign";original.mkdir()
        (self.source/"synth_abc123").symlink_to(original,target_is_directory=True)
        order=self.quality/"synth_abc123";order.mkdir()
        (order/"current.json").write_text(json.dumps({
            "schema":"saeit.factory.production-rework-order.v1",
            "recipe":"synth_abc123",
            "source_quality_receipt_sha256":"a"*64,
            "unresolved_technical_or_domain_defects":[]}))
        r=self.run_bridge()
        self.assertEqual(r["missing_source"],1)
        self.assertEqual(r["rebuild_attempted"],0)


class RealPrivateDocumentEditionTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.recipe="legacy_customer_document"
        self.stock=self.root/"digital-products"/self.recipe
        self.stock.mkdir(parents=True)
        self.arch=self.stock/(self.recipe+"-internal-qa.zip")
        self.qa=self.root/"quality-excellence"/"rework"/self.recipe
        self.qa.mkdir(parents=True)
        self.maker=m.load_maker(FILE.parent/"factory_product_maker.py")

    def bind(self,source_files):
        with zipfile.ZipFile(self.arch,"w") as zf:
            for name,payload in source_files.items():
                zf.writestr(name,payload)
        self.artifact_hash=hashlib.sha256(self.arch.read_bytes()).hexdigest()
        (self.qa/"current.json").write_text(json.dumps({
            "schema":"saeit.factory.quality-rework.v2",
            "recipe":self.recipe,"artifact_sha256":self.artifact_hash}))
        self.order={"recipe":self.recipe,
                    "artifact_sha256":self.artifact_hash,
                    "source_quality_receipt_sha256":hashlib.sha256(
                        (self.qa/"current.json").read_bytes()).hexdigest(),
                    "unresolved_technical_or_domain_defects":
                        ["P0_GLOBAL_TOP_FIVE_CURRENT_BENCHMARKS_MISSING"]}

    def test_genuine_customer_documents_become_new_accessible_private_source_and_zip(self):
        attack=b"</pre><script>alert('bad')</script> Read this guide. Visit https://example.org safely."
        self.bind({
            "bundle/":b"",
            "bundle/book.txt":attack,
            "bundle/appendix.pdf":b"%PDF-1.4 sample bytes",
            "bundle/executable.js":b"alert('never run')"})
        status=m.reauthor_document_delivery(self.root,self.recipe,self.order,self.maker)
        self.assertEqual(status,"private_document_edition_built")
        new_id="edition_"+self.artifact_hash[:24]
        recipes=self.root/"quality-excellence"/"document-edition-sources"
        product=self.root/"quality-excellence"/"document-edition-private-stock"/new_id
        source=recipes/new_id
        self.assertTrue(source.is_dir())
        index=(source/"index.html").read_text()
        self.assertIn("&lt;script&gt;",index)
        self.assertNotIn("<script>",index)
        self.assertIn('aria-label="Document and asset links"',index)
        self.assertNotIn("executable.js",index)
        self.assertFalse(re.search(r'''(?:src|href)\s*=\s*["']https?://''',index,re.I))
        self.assertGreaterEqual(len(list((source/"assets").iterdir())),2)
        self.assertEqual(self.maker.verify_recipe(source),"unit_tests_passed")
        actual=json.loads((product/"manufacturing_manifest.json").read_text())
        self.assertEqual(actual["qa_status"],"passed")
        self.assertFalse(actual["professional_quality_approved"])
        self.assertNotEqual(actual["artifact_sha256"],self.artifact_hash)
        self.assertTrue((product/(new_id+"-internal-qa.zip")).is_file())
        receipt=json.loads((self.root/"quality-excellence/document-edition-receipts"/(new_id+".json")).read_text())
        self.assertTrue(receipt["technical_manufacturer_qa_passed"])
        self.assertFalse(receipt["commercial_release_authorized"])
        self.assertFalse(receipt["external_independent_review_verified"])
        self.assertEqual(m.reauthor_document_delivery(self.root,self.recipe,self.order,self.maker),
                         "already_issued_private_edition")
        product_archive=product/(new_id+"-internal-qa.zip")
        product_archive.write_bytes(b"tampered private product")
        self.assertEqual(m.reauthor_document_delivery(self.root,self.recipe,self.order,self.maker),
                         "private_document_edition_repaired")
        repaired_meta=json.loads((product/"manufacturing_manifest.json").read_text())
        repaired_receipt=json.loads((self.root/"quality-excellence/document-edition-receipts"
                                     /(new_id+".json")).read_text())
        self.assertEqual(self.maker.sha256_file(product_archive),
                         repaired_receipt["new_artifact_sha256"])
        self.assertEqual(repaired_meta["artifact_sha256"],
                         repaired_receipt["new_artifact_sha256"])
        self.assertEqual(self.arch.read_bytes(),(self.stock/(self.recipe+"-internal-qa.zip")).read_bytes())

    def test_orphaned_edition_receipt_classifies_without_destroying_private_stock(self):
        self.bind({"bundle/guide.txt":b"authentic legacy document"})
        self.assertEqual(m.reauthor_document_delivery(
            self.root,self.recipe,self.order,self.maker),"private_document_edition_built")
        code="edition_"+self.artifact_hash[:24]
        receipts=self.root/"quality-excellence"/"document-edition-receipts"
        receipt=receipts/(code+".json")
        stock=self.root/"quality-excellence"/"document-edition-private-stock"/code
        archive=stock/(code+"-internal-qa.zip")
        before=archive.read_bytes()
        proof=receipt.read_bytes()
        receipt.unlink()
        self.assertEqual(m.reauthor_document_delivery(
            self.root,self.recipe,self.order,self.maker),
            "existing_edition_receipt_missing_or_unsafe")
        self.assertEqual(archive.read_bytes(),before)
        receipt.write_bytes(b"not valid JSON")
        self.assertEqual(m.reauthor_document_delivery(
            self.root,self.recipe,self.order,self.maker),
            "existing_edition_receipt_invalid")
        self.assertEqual(archive.read_bytes(),before)
        receipt.write_bytes(proof)
        data=json.loads(proof)
        data["source_customer_archive_sha256"]="0"*64
        receipt.write_text(json.dumps(data))
        self.assertEqual(m.reauthor_document_delivery(
            self.root,self.recipe,self.order,self.maker),
            "existing_edition_receipt_provenance_mismatch")
        self.assertEqual(archive.read_bytes(),before)

    def test_failed_private_edition_repair_restores_old_stock_and_receipt(self):
        self.bind({"bundle/guide.txt":b"authenticated old customer document"})
        self.assertEqual(m.reauthor_document_delivery(
            self.root,self.recipe,self.order,self.maker),"private_document_edition_built")
        code="edition_"+self.artifact_hash[:24]
        stock=self.root/"quality-excellence"/"document-edition-private-stock"/code
        archive=stock/(code+"-internal-qa.zip")
        receipt=self.root/"quality-excellence"/"document-edition-receipts"/(code+".json")
        archive.write_bytes(b"previous private damaged package - retain for forensic review")
        before_stock=archive.read_bytes()
        before_receipt=receipt.read_bytes()
        with patch.object(self.maker,"manufacture",side_effect=RuntimeError("test forced failure")):
            self.assertEqual(m.reauthor_document_delivery(
                self.root,self.recipe,self.order,self.maker),
                "private_edition_rebuild_failed")
        self.assertEqual(archive.read_bytes(),before_stock)
        self.assertEqual(receipt.read_bytes(),before_receipt)
        self.assertFalse((receipt.parent/(code+".json.pending")).exists())

    def test_successful_private_edition_repair_retains_forensic_backup(self):
        self.bind({"bundle/guide.txt":b"authenticated old customer document"})
        self.assertEqual(m.reauthor_document_delivery(
            self.root,self.recipe,self.order,self.maker),"private_document_edition_built")
        code="edition_"+self.artifact_hash[:24]
        stock_parent=self.root/"quality-excellence"/"document-edition-private-stock"
        archive=stock_parent/code/(code+"-internal-qa.zip")
        archive.write_bytes(b"old corrupted private package")
        self.assertEqual(m.reauthor_document_delivery(
            self.root,self.recipe,self.order,self.maker),
            "private_document_edition_repaired")
        snapshots=list(stock_parent.glob(".edition-repair-"+code+"-*"))
        self.assertEqual(len(snapshots),1)
        self.assertEqual((snapshots[0]/"prior-stock"/(code+"-internal-qa.zip")).read_bytes(),
                         b"old corrupted private package")
        self.assertEqual(m.reauthor_document_delivery(
            self.root,self.recipe,self.order,self.maker),
            "already_issued_private_edition")

    def test_document_edition_120_original_assets_produces_full_new_private_zip(self):
        files={"bundle/guide.txt":b"Original legacy technical guide with a reversible offline procedure."}
        files.update({"bundle/support_%03d.png"%i:("original image bytes %03d"%i).encode()
                      for i in range(119)})
        self.bind(files)
        original=self.arch.read_bytes()
        result=m.reauthor_document_delivery(self.root,self.recipe,self.order,self.maker)
        self.assertEqual(result,"private_document_edition_built")
        new_id="edition_"+self.artifact_hash[:24]
        source=self.root/"quality-excellence"/"document-edition-sources"/new_id
        record=json.loads((source/"metadata.json").read_text())
        self.assertEqual(len(record["assets"]),120)
        self.assertFalse(record["commercial_release_authorized"])
        self.assertEqual(self.arch.read_bytes(),original)
        output=self.root/"quality-excellence"/"document-edition-private-stock"/new_id
        with zipfile.ZipFile(output/(new_id+"-internal-qa.zip")) as z:
            self.assertEqual(len(z.namelist()),124)
            self.assertIsNone(z.testzip())
    def test_more_than_200_assets_cannot_silently_drop_original(self):
        files={"bundle/guide.txt":b"Original technical guide"}
        files.update({"bundle/image_%03d.png"%i:b"x" for i in range(200)})
        self.bind(files)
        self.assertEqual(m.reauthor_document_delivery(self.root,self.recipe,self.order,self.maker),
                         "document_asset_count_over_limit")
        self.assertFalse((self.root/"quality-excellence/document-edition-sources"/(
            "edition_"+self.artifact_hash[:24])).exists())
    def test_transient_manufacturing_failure_is_retryable(self):
        self.bind({"bundle/guide.txt":b"legitimate document"})
        source=self.root/"quality-excellence/document-edition-sources"/(
            "edition_"+self.artifact_hash[:24])
        original=self.maker.manufacture
        calls=[0]
        def fail_once_then_build(*args,**kwargs):
            calls[0]+=1
            if calls[0]==1:raise RuntimeError("temporary build failure")
            return original(*args,**kwargs)
        with patch.object(self.maker,"manufacture",side_effect=fail_once_then_build) as build:
            self.assertEqual(m.reauthor_document_delivery(
                self.root,self.recipe,self.order,self.maker),
                "document_edition_failed_needs_engineering")
            self.assertFalse(source.exists())
            self.assertEqual(m.reauthor_document_delivery(
                self.root,self.recipe,self.order,self.maker),
                "private_document_edition_built")
            self.assertEqual(build.call_count,2)

    def test_all_assets_below_hard_zip_bound_survive_edition_build(self):
        self.bind({"bundle/file_%03d.txt"%i:("Document %d\n"%i).encode()
                   for i in range(81)})
        status=m.reauthor_document_delivery(self.root,self.recipe,self.order,self.maker)
        self.assertEqual(status,"private_document_edition_built")
        new_id="edition_"+self.artifact_hash[:24]
        edition=json.loads((self.root/"quality-excellence/document-edition-sources"
                            /new_id/"metadata.json").read_text())
        self.assertEqual(len(edition["assets"]),81)

    def test_unbound_and_tampered_archives_never_get_new_product(self):
        self.bind({"bundle/file.txt":b"legitimate doc"})
        self.order["source_quality_receipt_sha256"]="0"*64
        self.assertEqual(m.reauthor_document_delivery(self.root,self.recipe,self.order,self.maker),
                         "original_qa_receipt_not_bound")
        self.order["source_quality_receipt_sha256"]=hashlib.sha256(
            (self.qa/"current.json").read_bytes()).hexdigest()
        with self.arch.open("ab") as fh:fh.write(b"tamper")
        self.assertEqual(m.reauthor_document_delivery(self.root,self.recipe,self.order,self.maker),
                         "original_archive_sha_mismatch")
        self.assertFalse((self.root/"quality-excellence/document-edition-sources").exists())

    def test_archive_cannot_use_path_traversal_or_executable_source_as_document(self):
        self.bind({"../outside.txt":b"data"})
        self.assertEqual(m.reauthor_document_delivery(self.root,self.recipe,self.order,self.maker),
                         "unsafe_document_archive_member")
        self.assertFalse((self.root/"outside.txt").exists())
        self.bind({"private/evil.py":b"print('run')"})
        self.assertEqual(m.reauthor_document_delivery(self.root,self.recipe,self.order,self.maker),
                         "no_supported_document_content")
        self.assertFalse((self.root/"quality-excellence/document-edition-sources"/(
            "edition_"+self.artifact_hash[:24])).exists())


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
                self.assertEqual(m.active_product_allowlist(slots), set(recipes))

    def test_rejects_family_count_as_product_slot_capacity(self):
        with tempfile.TemporaryDirectory() as directory:
            slots = Path(directory) / "slots.json"
            slots.write_text(json.dumps({
                "schema": "saeit.factory.product-slots.v1",
                "capacity": 40,
                "active": [{"recipe": "product_%02d" % n} for n in range(1, 41)],
            }))
            with self.assertRaisesRegex(ValueError, "CAPACITY_MISMATCH"):
                m.active_product_allowlist(slots)


if __name__=="__main__":unittest.main()

