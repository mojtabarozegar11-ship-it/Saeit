"""Both EXISTING site couriers: real version-bound customer ZIP, no fake sale."""
import importlib.util
import io
import json
import pathlib
import shutil
import tempfile
import unittest
import zipfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/(name+".py"))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value

mpw=load("mpw_vps_warehouse_courier")
receiver=load("store_receiver")
sender=load("factory_store_sender")
bridge=load("zomorod_vps_warehouse_3order_bridge")
intake=load("factory_design_intake")
designer=load("factory_recipe_designer")
maker=load("factory_product_maker")
packager=load("factory_customer_packager")

class BothExistingCouriers(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=pathlib.Path(t.name)/"factory"
        self.root.mkdir(mode=0o700)
        (self.root/"design-intake").mkdir(mode=0o700)
        self.site=pathlib.Path(t.name)/"private_site";self.site.mkdir(mode=0o700)
        spec=intake.expand({"schema":intake.SCHEMA,"family_id":"F28",
                            "blueprint":"inventory_coverage"},"factory_invention")
        compiled=designer.compile_recipe(spec,self.root/"generated-product-recipes")
        self.product=compiled["recipe"]
        maker.manufacture(self.product,self.root/"generated-product-recipes",self.root/"digital-products")
        self.report=packager.pack(self.root,self.product)
        self.version=self.report["factory_source_sha256"]
        self.manufacturing=json.loads((self.root/"digital-products"/self.product/"manufacturing_manifest.json").read_text())
        stock=self.root/"production-warehouse/finished"/self.product/self.version
        stock.mkdir(parents=True,mode=0o700)
        shutil.copyfile(self.root/"digital-products"/self.product/(self.product+"-internal-qa.zip"),stock/"product.zip")
        self.stock_meta={"schema":"saeit.factory.production-warehouse.v1",
                         "product_id":self.product,"source_sha256":self.version,
                         "artifact_sha256":self.manufacturing["artifact_sha256"],
                         "manufacturing_qc":"passed","production_state":"finished_goods_in_factory",
                         "commercial_release":False,"site_transfer_state":"not_transferred",
                         "content_rights_market_review":"pending","receiving_site":None,
                         "bytes":(stock/"product.zip").stat().st_size}
        (stock/"warehouse_manifest.json").write_text(json.dumps(self.stock_meta))

    def test_mpw_site_receives_buyer_zip_and_qa_return_without_public_sale(self):
        payload=mpw.export_factory(self.root)
        self.assertEqual(len(mpw.unpack(payload)),1)
        result=mpw.import_site(payload,self.site)
        self.assertEqual(result["new_customer_packages_received"],1)
        private=self.site/"received"/self.product/self.version
        self.assertEqual(mpw.digest((private/"customer-package.zip").read_bytes()),
                         self.report["package_sha256"])
        state=json.loads((private/"site_qa.json").read_text())
        self.assertTrue(state["customer_bundle_verified"])
        self.assertFalse(state["commercial_approved"])
        self.assertFalse(state["payment_enabled"])
        again=mpw.import_site(payload,self.site)
        self.assertEqual(again["new_customer_packages_received"],0)
        self.assertEqual(again["existing_customer_packages_verified"],1)
        self.assertEqual(mpw.receive_factory_returns(mpw.feedback_site(self.site),self.root)["accepted_stage1_qa_returns"],1)

    def test_mpw_tamper_companion_refused_before_site_ingest(self):
        path=self.root/"customer-packs"/self.product/self.version/"customer-package.zip"
        path.chmod(0o600)
        path.write_bytes(path.read_bytes()+b"tampered")
        with self.assertRaisesRegex(RuntimeError,"CUSTOMER_PACKAGE_SHA_OR_RELEASE_GATE_INVALID"):
            mpw.export_factory(self.root)
        self.assertFalse((self.site/"received").exists())

    def test_zomorod_receiver_private_customer_receipt_checks_original(self):
        box=self.site
        recipe=self.product;v=self.version;hash=self.manufacturing["artifact_sha256"]
        private=box/"packages"/recipe;private.mkdir(parents=True,mode=0o700)
        shutil.copyfile(self.root/"digital-products"/recipe/(recipe+"-internal-qa.zip"),private/(hash+".zip"))
        (private/(hash+".json")).write_text(json.dumps(self.manufacturing))
        receipt=box/"receipts"/recipe;receipt.mkdir(parents=True,mode=0o700)
        (receipt/(hash+".json")).write_text(json.dumps(
            {"status":"received_private","recipe":recipe,"sha256":hash}))
        self.assertTrue(receiver.status(box,recipe,hash))
        self.assertFalse(receiver.consumer_status(box,recipe,v))
        sender.verify_consumer_source(self.root,recipe,v)
        dest=box/"incoming/consumer"/recipe/v
        dest.mkdir(parents=True,mode=0o700)
        orig=self.root/"customer-packs"/recipe/v
        shutil.copyfile(orig/"customer-package.zip",dest/"customer-package.zip.partial")
        shutil.copyfile(orig/"candidate_manifest.json",dest/"candidate_manifest.json.partial")
        receiver.consumer_finalize(box,recipe,v)
        self.assertTrue(receiver.consumer_status(box,recipe,v))
        self.assertFalse((box/"public_html").exists())
        final=box/"customer-packages"/recipe/v/"customer-package.zip"
        self.assertEqual(receiver.sha256(final),self.report["package_sha256"])
        # Tampering with an archived file must invalidate the receipt.
        final.write_bytes(final.read_bytes()+b"bad")
        self.assertFalse(receiver.consumer_status(box,recipe,v))

    def test_zomorod_existing_sender_rejects_stale_buyer_version(self):
        changed=self.root/"generated-product-recipes"/self.product/"calculator.py"
        changed.write_text(changed.read_text()+"\n# changed after original QA\n")
        # Existing sender checks source-manufacture match; a new recipe revision
        # must not silently change a formerly immutable customer package.
        # Genuine packager must explicitly detect stale revision.
        with self.assertRaisesRegex(ValueError,"CONSUMER_STALE_MANUFACTURED_SOURCE"):
            packager.pack(self.root,self.product)

if __name__=="__main__":unittest.main()
