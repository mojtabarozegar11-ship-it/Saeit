"""Independent VPS finished-goods warehouse acceptance and safety tests."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[1]

def load(filename,name):
    spec=importlib.util.spec_from_file_location(name,REPO/"scripts"/filename)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

warehouse=load("factory_production_warehouse.py","saeit_warehouse")
maker=load("factory_product_maker.py","saeit_maker")

class FactoryWarehouseTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.private=self.root/"factory-private"
        self.private.mkdir()
        self.recipes=self.root/"recipes"
        for recipe in maker.RECIPES:
            shutil.copytree(REPO/"product_recipes"/recipe,self.recipes/recipe)
        self.finished=self.private/"production-warehouse"/"finished"
    def manufacture(self, recipe):
        return maker.manufacture(recipe,self.recipes,self.private/"digital-products")
    def register(self):
        return json.loads((self.private/"production-warehouse"/"stock-register.json").read_text("utf8"))
    def test_strict_build50_holds_technical_pass_and_keeps_original(self):
        self.manufacture('farm_enterprise_economics')
        result=warehouse.cycle(self.private,strict_build50=True)
        self.assertEqual(result['stocked'],0)
        self.assertEqual(result['held'],1)
        register=self.register()
        self.assertTrue(register['strict_build50_enabled'])
        self.assertEqual(register['build_quality']['verified_50_stage_builds'],0)
        self.assertEqual(register['build_quality']['requiring_replanning'],1)
        self.assertTrue((self.private/'digital-products/farm_enterprise_economics/farm_enterprise_economics-internal-qa.zip').exists())
    def test_all_registered_products_first_to_warehouse_zero_site_contact(self):
        expected_count = len(maker.RECIPES)
        for recipe in maker.RECIPES:self.manufacture(recipe)
        result=warehouse.cycle(self.private)
        self.assertEqual(result["status"],"ok")
        self.assertEqual(result["stocked"],expected_count)
        self.assertEqual(result["warehouse_count"],expected_count)
        reg=self.register()
        self.assertFalse(reg["factory_site_dependency"])
        self.assertFalse(reg["distribution_enabled"])
        self.assertEqual(reg["sites_contacted"],0)
        self.assertEqual(reg["finished_goods_product_count"],expected_count)
        self.assertEqual(reg["awaiting_commercial_review"],expected_count)
        for rec in reg["records"]:
            item=self.finished/rec["product_id"]/rec["version"]
            self.assertEqual((item/"product.zip").stat().st_mode & 0o777,0o400)
            self.assertFalse(json.loads((item/"warehouse_manifest.json").read_text())["commercial_release"])
            self.assertEqual(rec["site_transfer_state"],"not_transferred")
        self.assertFalse((self.root/"published").exists())
        self.assertEqual(len(list(self.private.rglob("*.zip"))),expected_count * 2)  # source and stocked archives
    def test_repeat_cycles_never_duplicate_or_overwrite(self):
        self.manufacture("farm_enterprise_economics")
        a=warehouse.cycle(self.private)
        self.assertEqual(a["stocked"],1)
        p=list(self.finished.rglob("product.zip"))[0]
        hash_before=warehouse.digest(p)
        b=warehouse.cycle(self.private)
        self.assertEqual(b["stocked"],0)
        self.assertEqual(b["warehouse_count"],1)
        self.assertEqual(warehouse.digest(p),hash_before)
    def test_source_change_creates_new_immutable_version(self):
        self.manufacture("farm_enterprise_economics")
        warehouse.cycle(self.private)
        src=self.recipes/"farm_enterprise_economics"/"README.md"
        src.write_text(src.read_text()+"\nRelease two additions.\n",encoding="utf8")
        self.manufacture("farm_enterprise_economics")
        r=warehouse.cycle(self.private)
        self.assertEqual(r["warehouse_count"],2)
        self.assertEqual(r["stocked"],1)
        self.assertEqual(len(list((self.finished/"farm_enterprise_economics").iterdir())),2)
    def test_open_rework_holds_new_product_without_deleting_it(self):
        self.manufacture("farm_enterprise_economics")
        ledger=self.private/"qa-rework"/"farm_enterprise_economics"/"ledger.json"
        ledger.parent.mkdir(parents=True)
        ledger.write_text(json.dumps({"schema":"saeit.factory.qa-rework.v1",
                                      "current_status":"needs_rework"}))
        result=warehouse.cycle(self.private)
        self.assertEqual(result["stocked"],0)
        self.assertEqual(result["held"],1)
        self.assertTrue((self.private/"digital-products"/"farm_enterprise_economics"/"farm_enterprise_economics-internal-qa.zip").exists())
        self.assertEqual(self.register()["finished_goods_versions"],0)
    def test_failed_qa_manifest_cannot_become_finished_good(self):
        self.manufacture("farm_enterprise_economics")
        f=self.private/"digital-products"/"farm_enterprise_economics"/"manufacturing_manifest.json"
        manifest=json.loads(f.read_text())
        manifest["qa_status"]="failed"
        f.write_text(json.dumps(manifest))
        result=warehouse.cycle(self.private)
        self.assertEqual(result["stocked"],0)
        self.assertEqual(result["held"],1)
        self.assertIn("WAREHOUSE_MANUFACTURING_QA_NOT_APPROVED",self.register()["needs_rework_or_review"][0]["reason"])
    def test_archive_corruption_is_detected_without_deleting_source(self):
        self.manufacture("farm_enterprise_economics")
        warehouse.cycle(self.private)
        archive=list(self.finished.rglob("product.zip"))[0]
        archive.chmod(0o600)
        with archive.open("ab") as file:file.write(b"corruption")
        with self.assertRaises(RuntimeError):
            warehouse.cycle(self.private)
        self.assertEqual(archive.read_bytes()[-10:],b"corruption")
        self.assertTrue((self.private/"digital-products"/"farm_enterprise_economics"/"farm_enterprise_economics-internal-qa.zip").is_file())
    def test_unrelated_site_and_order_objects_not_required(self):
        self.manufacture("water_budget_economics")
        result=warehouse.cycle(self.private)
        self.assertEqual(result["warehouse_count"],1)
        self.assertFalse((self.private/"sites").exists())
        self.assertFalse((self.private/"orders").exists())

if __name__=="__main__":unittest.main()
