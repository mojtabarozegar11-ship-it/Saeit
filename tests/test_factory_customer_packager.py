"""Integration checks for independent factory consumer package finishing."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/(name+".py"))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod
packager=module("factory_customer_packager")
intake=module("factory_design_intake")
designer=module("factory_recipe_designer")
maker=module("factory_product_maker")

class CustomerFinishingTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)

    def _product(self,key="inventory_coverage",family="F28"):
        spec=intake.expand({"schema":intake.SCHEMA,"family_id":family,"blueprint":key},"factory_invention")
        compiled=designer.compile_recipe(spec,self.root/"generated-product-recipes")
        recipe=compiled["recipe"]
        receipt=maker.manufacture(recipe,self.root/"generated-product-recipes",
                                  self.root/"digital-products")
        self.assertEqual(receipt["qa_status"],"passed")
        return recipe

    def test_real_customer_bundle_works_and_is_not_a_fake_commercial_product(self):
        name=self._product()
        result=packager.cycle(self.root)
        self.assertEqual(result["new_buyer_usable_packages_this_tick"],1)
        self.assertEqual(result["store_purchase_eligible_products"],0)
        receipt=packager.read(self.root/"digital-products"/name/"manufacturing_manifest.json")
        candidate=self.root/"customer-packs"/name/receipt["source_sha256"]
        manifest=packager.read(candidate/"candidate_manifest.json")
        archive=candidate/"customer-package.zip"
        self.assertEqual(packager.digest(archive),manifest["package_sha256"])
        self.assertTrue(manifest["technical_buyer_package_verified"])
        self.assertFalse(manifest["commercial_release"])
        self.assertIsNone(manifest["price"])
        self.assertFalse(manifest["public_download_allowed"])
        self.assertEqual(manifest["consumer_cli_smoke_examples_passed"],2)
        with zipfile.ZipFile(archive) as package:
            self.assertIsNone(package.testzip())
            files=set(package.namelist())
            for name in ("product/calculator.py","product/example_inputs.json",
                         "guide/START_HERE.md","qa/SHA256SUMS.txt",
                         "license/REVIEW_REQUIRED.txt","description/STORE_LISTING_DRAFT.md"):
                self.assertIn(name,files)
            self.assertIn(b"python calculator.py",package.read("guide/START_HERE.md"))
            self.assertIn(b"NOT LICENSED",package.read("license/REVIEW_REQUIRED.txt"))
            for row in package.read("qa/SHA256SUMS.txt").decode().splitlines():
                digest,filename=row.split("  ",1)
                self.assertEqual(hashlib.sha256(package.read(filename)).hexdigest(),digest)

    def test_multiple_distinct_products_and_idempotent_replay(self):
        self._product("inventory_coverage")
        self._product("water_volume")
        first=packager.cycle(self.root,limit=2)
        self.assertEqual(first["new_buyer_usable_packages_this_tick"],2)
        second=packager.cycle(self.root,limit=2)
        self.assertEqual(second["new_buyer_usable_packages_this_tick"],0)
        self.assertEqual(second["previous_versions_revalidated_this_tick"],2)
        self.assertEqual(len(list((self.root/"customer-packs").glob("*/**/customer-package.zip"))),2)

    def test_a_stale_or_unverified_manufactured_artifact_is_never_packaged(self):
        recipe=self._product()
        code=self.root/"generated-product-recipes"/recipe/"calculator.py"
        code.write_text(code.read_text()+"\n# changed after QA\n")
        out=packager.cycle(self.root)
        self.assertEqual(out["new_buyer_usable_packages_this_tick"],0)
        self.assertIn("CONSUMER_STALE_MANUFACTURED_SOURCE",out["blocked_for_rework"][0]["reason"])
        self.assertFalse(list((self.root/"customer-packs").rglob("customer-package.zip")))

    def test_quarantines_active_rework_and_cannot_label_sale_ready(self):
        recipe=self._product()
        p=self.root/"qa-rework"/recipe/"ledger.json"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({"schema":"saeit.factory.qa-rework.v1","current_status":"needs_rework"}))
        with self.assertRaisesRegex(ValueError,"CONSUMER_OPEN_QA_REWORK"):
            packager.pack(self.root,recipe)
        self.assertFalse(list((self.root/"customer-packs").rglob("customer-package.zip")))

    def test_f27_customer_pack_includes_real_workbook(self):
        recipe=self._product("inventory_coverage","F27")
        manifest=packager.pack(self.root,recipe)
        self.assertEqual(manifest["family_id"],"F27")
        with zipfile.ZipFile(self.root/"customer-packs"/recipe/manifest["factory_source_sha256"]/"customer-package.zip") as z:
            self.assertTrue(any(name.endswith(".xlsx") for name in z.namelist()))
        self.assertFalse(manifest["eligible_for_commercial_listing"])

if __name__=="__main__":unittest.main()
