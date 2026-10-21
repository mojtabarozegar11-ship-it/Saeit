"""Real ten-stage source+customer ZIP upgrades, immutable lineage and stop-on-tamper."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

def load(name):
    source=ROOT/"scripts"/(name+".py")
    spec=importlib.util.spec_from_file_location(name,source)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

designer=load("factory_recipe_designer")
maker=load("factory_product_maker")
engine=load("factory_ten_generation_builder_v1")

class RealTenGenerationTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.private=self.root/"private"
        self.private.mkdir()
        self.recipes=self.private/"generated-product-recipes"
        specs=json.loads((ROOT/"factory_config/design_opportunities.json").read_text())["requests"]
        original=next(x for x in specs if x["family_id"]=="F28")
        names=[]
        for family in ("F27","F28"):
            candidate=dict(original,family_id=family)
            created=designer.compile_recipe(candidate,self.recipes)
            names.append(created["recipe"])
        self.names=names
        self.sha={recipe:maker.source_digest(self.recipes/recipe,
                 maker.inspect_recipe(self.recipes/recipe)[1]) for recipe in names}

    def test_both_real_adapter_families_gain_ten_distinct_tested_private_products(self):
        state=engine.run(self.private,self.recipes,ROOT/"scripts/factory_product_maker.py",limit=2)
        self.assertEqual(state["new_real_generations"],20)
        self.assertEqual(state["ten_generation_lineages_verified"],2)
        self.assertFalse(state["professional_1000_approved"])
        self.assertEqual(state["public_uploads"],0)
        self.assertEqual({x["family_id"] for x in state["completed"]},{"F27","F28"})
        for recipe in self.names:
            output=self.private/"quality-excellence"/"ten-generations"/recipe
            hashes=[]
            for generation in range(1,11):
                folder=output/("g%02d"%generation)
                proof=json.loads((folder/"receipt.json").read_text())
                hashes.append(proof["source_sha256"])
                self.assertEqual(proof["generation"],generation)
                self.assertEqual(proof["feature"],engine.FEATURES[generation-1][0])
                self.assertGreaterEqual(proof["independently_executed_tests"],7+generation)
                self.assertFalse(proof["quality_1000_certified"])
                self.assertTrue((folder/"product"/recipe/(recipe+"-internal-qa.zip")).is_file())
            self.assertEqual(len(set(hashes)),10)
            self.assertEqual(maker.source_digest(self.recipes/recipe,
                        maker.inspect_recipe(self.recipes/recipe)[1]),self.sha[recipe])
        again=engine.run(self.private,self.recipes,ROOT/"scripts/factory_product_maker.py",limit=2)
        self.assertEqual(again["new_real_generations"],0)

    def test_unproven_compiler_provenance_can_never_get_ten_generations(self):
        source=self.recipes/self.names[0]/"design_receipt.json"
        data=json.loads(source.read_text())
        data["generator_capability_revision"]="unverified"
        source.write_text(json.dumps(data))
        result=engine.run(self.private,self.recipes,ROOT/"scripts/factory_product_maker.py",limit=2)
        self.assertEqual(result["selected"],1)
        self.assertEqual(result["new_real_generations"],10)
        self.assertTrue(any(x["recipe"]==self.names[0] for x in result["untrusted_sources"]))
        self.assertFalse((self.private/"quality-excellence"/"ten-generations"/self.names[0]/"g01").exists())

    def test_archive_tampering_blocks_reuse_and_does_not_touch_original(self):
        state=engine.run(self.private,self.recipes,ROOT/"scripts/factory_product_maker.py",limit=2)
        recipe=self.names[0]
        artifact=self.private/"quality-excellence"/"ten-generations"/recipe/"g03"/"product"/recipe/(recipe+"-internal-qa.zip")
        with artifact.open("ab") as out:out.write(b"TAMPER")
        with self.assertRaisesRegex(ValueError,"ARTIFACT_TAMPERED"):
            engine.run(self.private,self.recipes,ROOT/"scripts/factory_product_maker.py",limit=2)
        self.assertEqual(maker.source_digest(self.recipes/recipe,
                         maker.inspect_recipe(self.recipes/recipe)[1]),self.sha[recipe])

if __name__=="__main__":unittest.main()
