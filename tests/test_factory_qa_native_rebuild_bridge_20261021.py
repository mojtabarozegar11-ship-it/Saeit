"""Regression: real QA workorders can dispatch isolated technical rebuilds, never sales."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
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
    def test_does_not_mutate_original_stock_on_failed_rebuild(self):
        _,original=self.seed()
        saved=(original/"manufacturing_manifest.json").read_bytes()
        with patch.object(m,"load_maker",side_effect=ValueError("not installed")):
            with self.assertRaises(ValueError):m.execute(self.root,self.source,FILE)
        self.assertEqual(saved,(original/"manufacturing_manifest.json").read_bytes())
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
