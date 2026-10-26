"""Real ten-stage source+customer ZIP upgrades, immutable lineage and stop-on-tamper."""
import importlib.util
import json
import re
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
            output=engine.generation_root(self.private,self.recipes/recipe)
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
        self.assertFalse((self.private/"quality-excellence"/"ten-generations"/self.names[0]/"verified-distribution-v4"/"g01").exists())

    def test_archive_tampering_blocks_reuse_and_does_not_touch_original(self):
        state=engine.run(self.private,self.recipes,ROOT/"scripts/factory_product_maker.py",limit=2)
        recipe=self.names[0]
        artifact=engine.generation_root(self.private,self.recipes/recipe)/"g03"/"product"/recipe/(recipe+"-internal-qa.zip")
        with artifact.open("ab") as out:out.write(b"TAMPER")
        with self.assertRaisesRegex(ValueError,"ARTIFACT_TAMPERED"):
            engine.run(self.private,self.recipes,ROOT/"scripts/factory_product_maker.py",limit=2)
        self.assertEqual(maker.source_digest(self.recipes/recipe,
                         maker.inspect_recipe(self.recipes/recipe)[1]),self.sha[recipe])


    def test_v3_generations_survive_a_verified_v4_source_upgrade(self):
        recipe=self.names[0]
        source=self.recipes/recipe
        calculator=source/"calculator.py"
        code=calculator.read_text(encoding="utf8")
        code=re.sub(r"(?s)# DISTRIBUTION_API_V4_START.*?# DISTRIBUTION_API_V4_END", "", code)
        calculator.write_text(code,encoding="utf8")
        cases=source/"test_calculator.py"
        tests=cases.read_text(encoding="utf8")
        tests=re.sub(r"(?ms)^# DISTRIBUTION_TESTS_V4_START.*?^# DISTRIBUTION_TESTS_V4_END\\n", "", tests)
        tests=re.sub(r"(?ms)^    # DISTRIBUTION_TESTS_V4_START.*?^    # DISTRIBUTION_TESTS_V4_END\\n", "", tests)
        cases.write_text(tests,encoding="utf8")
        receipt=source/"design_receipt.json"
        data=json.loads(receipt.read_text(encoding="utf8"))
        data["generator_capability_revision"]="verified-summary-v3"
        receipt.write_text(json.dumps(data),encoding="utf8")
        maker.verify_recipe(source,minimum_tests=7)

        old=engine.run(self.private,self.recipes,ROOT/"scripts/factory_product_maker.py",limit=2)
        self.assertEqual(old["new_real_generations"],20)
        legacy=engine.generation_root(self.private,source)
        self.assertTrue((legacy/"g10"/"receipt.json").is_file())
        historical=(legacy/"g01"/"receipt.json").read_bytes()

        upgrade=designer.evolve_recipe(recipe,self.recipes)
        self.assertTrue(upgrade["changed"])
        revised=engine.generation_root(self.private,self.recipes/recipe)
        self.assertNotEqual(legacy,revised)
        self.assertFalse((revised/"g01").exists())
        outcome=engine.run(self.private,self.recipes,ROOT/"scripts/factory_product_maker.py",limit=2)
        self.assertEqual(outcome["new_real_generations"],10)
        self.assertTrue((revised/"g10"/"receipt.json").is_file())
        self.assertEqual((legacy/"g01"/"receipt.json").read_bytes(),historical)
        self.assertEqual(engine.run(self.private,self.recipes,
                         ROOT/"scripts/factory_product_maker.py",limit=2)["new_real_generations"],0)

    def test_v4_source_cannot_claim_to_be_a_v3_compiler_revision(self):
        recipe=self.names[0]
        receipt=self.recipes/recipe/"design_receipt.json"
        document=json.loads(receipt.read_text(encoding="utf8"))
        document["generator_capability_revision"]="verified-summary-v3"
        receipt.write_text(json.dumps(document),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"TEN_VERIFIED_COMPILER_SOURCE_REQUIRED"):
            engine.original_identity(self.recipes/recipe,maker)

if __name__=="__main__":unittest.main()
