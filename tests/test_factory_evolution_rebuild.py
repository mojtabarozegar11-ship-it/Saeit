"""Prove an evolved factory source becomes a truly revised private ZIP.

The tests build real old and revised products, inspect immutable prior bytes,
and deliberately inject a *post-write* failure to verify complete rollback.
"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from tests.test_factory_source_evolution import make_legacy_source

ROOT=Path(__file__).resolve().parents[1]

def load(name):
    path=ROOT/"scripts"/(name+".py")
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

rebuilder=load("factory_evolution_rebuild")
designer=load("factory_recipe_designer")
maker=load("factory_product_maker")

class EvolvedArtifactRebuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=self.root/"generated-product-recipes"
        request=json.loads((ROOT/"factory_config/design_opportunities.json").read_text())["requests"]
        spec=next(x for x in request if x["family_id"]=="F28")
        created=designer.compile_recipe(spec,self.source)
        self.recipe=created["recipe"]
        folder=self.source/self.recipe
        make_legacy_source(folder)
        self.product=self.root/"digital-products"/self.recipe
        maker.manufacture(self.recipe,self.source,self.root/"digital-products")
        self.zip_path=self.product/(self.recipe+"-internal-qa.zip")
        self.previous_zip=self.zip_path.read_bytes()
        self.previous_manifest=(self.product/"manufacturing_manifest.json").read_bytes()
        self.assertTrue(designer.evolve_recipe(self.recipe,self.source)["changed"])

    def test_real_rebuild_changed_zip_and_saved_old_product(self):
        result=rebuilder.run(self.root,ROOT/"scripts",limit=1)
        self.assertEqual(result["actually_rebuilt"],1)
        self.assertEqual(result["stale_products_examined"],1)
        self.assertEqual(result["failures"],[])
        self.assertNotEqual(self.zip_path.read_bytes(),self.previous_zip)
        receipt=result["products"][0]
        self.assertEqual(receipt["recipe"],self.recipe)
        self.assertGreaterEqual(receipt["technical_tests_passed"],5)
        self.assertFalse(receipt["commercially_approved"])
        self.assertFalse(receipt["publicly_published"])
        saved=list((self.root/"evolution-package-backups").glob(self.recipe+"-*"))
        self.assertEqual(len(saved),1)
        self.assertEqual((saved[0]/self.zip_path.name).read_bytes(),self.previous_zip)
        self.assertEqual((saved[0]/"manufacturing_manifest.json").read_bytes(),self.previous_manifest)
        sha=rebuilder.digest_file(self.zip_path)
        self.assertEqual(sha,receipt["new_artifact_sha256"])
        self.assertTrue(list((self.root/"evolution-rebuild-receipts").glob("*.json")))
        second=rebuilder.run(self.root,ROOT/"scripts")
        self.assertEqual(second["actually_rebuilt"],0)
        self.assertEqual(second["stale_products_examined"],0)

    def test_rollback_after_new_zip_written_preserves_old_zip_and_manifest(self):
        real=maker.manufacture
        def fail_after_writing(*args,**kwargs):
            real(*args,**kwargs)
            raise RuntimeError("injected_post_write_receipt_failure")
        with mock.patch.object(maker,"manufacture",side_effect=fail_after_writing):
            result=rebuilder.run(self.root,ROOT/"scripts",maker=maker)
        self.assertEqual(result["actually_rebuilt"],0)
        self.assertEqual(len(result["failures"]),1)
        self.assertEqual(self.zip_path.read_bytes(),self.previous_zip)
        self.assertEqual((self.product/"manufacturing_manifest.json").read_bytes(),self.previous_manifest)
        self.assertFalse(list((self.root/"evolution-rebuild-receipts").glob("*.json")))

    def test_source_provenance_tamper_never_rebuilds(self):
        f=self.source/self.recipe/"design_request.json"
        obj=json.loads(f.read_text())
        obj["title"]="Unauthorized new claim"
        f.write_text(json.dumps(obj))
        result=rebuilder.run(self.root,ROOT/"scripts")
        self.assertEqual(result["actually_rebuilt"],0)
        self.assertEqual(len(result["failures"]),1)
        self.assertEqual(self.zip_path.read_bytes(),self.previous_zip)

    def test_zero_and_excessive_limit_rejected(self):
        for limit in (0,11,True,2.2):
            with self.assertRaises(ValueError):
                rebuilder.run(self.root,ROOT/"scripts",limit)

if __name__=="__main__":
    unittest.main()
