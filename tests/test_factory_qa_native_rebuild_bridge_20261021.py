"""Regression: real QA workorders can dispatch isolated technical rebuilds, never sales."""
import hashlib
import importlib.util
import json
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
            "source_quality_receipt_sha256":"a"*64,
            "unresolved_technical_or_domain_defects":defects or []}))
        original=self.root/"digital-products"/name;original.mkdir(parents=True)
        (original/"manufacturing_manifest.json").write_text(json.dumps({
            "source_sha256":"b"*64,"qa_status":"passed"}))
        return item,original
    def run_bridge(self):
        with patch.object(m,"load_maker",return_value=FakeMaker):
            return m.execute(self.root,self.source,FILE,limit=2)
    def seed_archived_only(self,name="synth_abc123",*,tamper=False):
        item,original=self.seed(name=name,defects=["P0_BUILD_ARCHIVE_INVALID"])
        source_bytes=(item/"README.md").read_bytes()
        archive=original/(item.name+"-internal-qa.zip")
        with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(item.name+"/README.md",source_bytes)
        (original/"manufacturing_manifest.json").write_text(json.dumps({
            "schema_version":2,"recipe":item.name,"files":["README.md"],
            "source_sha256":hashlib.sha256(source_bytes).hexdigest(),
            "artifact_sha256":FakeMaker.sha256_file(archive)}))
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
    def test_receipt_bound_archive_recovers_source_without_manifest_fields(self):
        name,_=self.seed_archived_only()
        original=self.root/"digital-products"/name
        (original/"manufacturing_manifest.json").write_text(json.dumps({"legacy":True}))
        result=self.run_bridge()
        self.assertEqual(result["archive_sources_recovered"],1)
        self.assertEqual(result["missing_source"],0)
        self.assertEqual(result["rebuild_attempted"],1)
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

if __name__=="__main__":unittest.main()

