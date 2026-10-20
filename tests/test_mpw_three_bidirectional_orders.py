"""Actual three sourced MojPlayWin site->VPS work orders; never fake purchases."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts import mpw_vps_warehouse_courier as courier

ENGINE=Path(__file__).resolve().parents[1]/"scripts/factory_continuous_production_orders.py"

def digest(s):
    return hashlib.sha256(s.encode()).hexdigest()

def goods_zip():
    z=io.BytesIO()
    with zipfile.ZipFile(z,"w",zipfile.ZIP_DEFLATED) as f:
        f.writestr("product/readme.txt","QA review candidate only")
    return z.getvalue()

class ThreeRealProductRequests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.root=self.base/"factory";self.root.mkdir(mode=0o700)
        (self.root/"design-intake").mkdir(mode=0o700)
        (self.root/"production-instructions/orders").mkdir(parents=True,mode=0o700)
        (self.root/"production-warehouse/finished").mkdir(parents=True,mode=0o700)
        self.site=self.base/"site";self.site.mkdir(mode=0o700)
        self.products=[]
        for i in range(5):
            product="farm_product_"+str(i)
            version=digest("valid unique source "+str(i))
            archive=goods_zip()
            base=self.root/"production-warehouse/finished"/product/version
            base.mkdir(parents=True,mode=0o700)
            manifest={"schema":"saeit.factory.production-warehouse.v1",
                "product_id":product,"source_sha256":version,
                "artifact_sha256":courier.digest(archive),"bytes":len(archive),
                "manufacturing_qc":"passed","production_state":"finished_goods_in_factory",
                "commercial_release":False,"site_transfer_state":"not_transferred",
                "content_rights_market_review":"pending","receiving_site":None}
            (base/"warehouse_manifest.json").write_text(json.dumps(manifest))
            (base/"product.zip").write_bytes(archive)
            self.products.append((product,version,manifest))
        stock=courier.export_factory(self.root)
        q=courier.import_site(stock,self.site)
        self.assertEqual(q["pending_stage1_return"],5)
        r=courier.receive_factory_returns(courier.feedback_site(self.site),self.root)
        self.assertEqual(r["accepted_stage1_qa_returns"],5)

    def test_three_real_site_product_orders_become_native_wo_only_once(self):
        raw=courier.three_site_product_requests(self.site,cycle="20261019")
        batch=json.loads(raw)
        self.assertEqual(len(batch["requests"]),3)
        self.assertEqual(batch["real_customer_purchases"],0)
        first=courier.receive_three_product_requests(raw,self.root,ENGINE)
        self.assertEqual(first["new_native_orders"],3)
        self.assertEqual(first["status"],"three_native_product_orders_created")
        self.assertEqual(len(first["native_product_orders"]),3)
        for name in first["native_product_orders"]:
            doc=json.loads((self.root/"production-instructions/orders"/(name+".json")).read_text())
            self.assertEqual(doc["requesting_site"],"mojplaywin.com")
            self.assertEqual(doc["phase"],"engineering_specification")
            self.assertEqual(doc["origin"],"mojplaywin-site-qa-return")
            self.assertFalse(doc["publication_approved"])
            self.assertFalse(doc["requires_customer_order"])
            self.assertFalse(doc["manufacturing_qa_passed"])
            self.assertEqual(doc["instruction_kind"],"site_product_rework_work_order")
        same=courier.receive_three_product_requests(raw,self.root,ENGINE)
        self.assertEqual(same["new_native_orders"],0)
        self.assertEqual(same["status"],"already_admitted")
        self.assertEqual(same["native_product_orders"],first["native_product_orders"])
        self.assertEqual(courier.three_site_product_requests(self.site,cycle="20261019"),raw)

    def test_same_day_batch_stays_stable_when_factory_stock_grows(self):
        first=courier.three_site_product_requests(self.site,cycle="20261019")
        name,version,_=self.products[0]
        original=self.root/"production-warehouse/finished"/name/version
        new_name="farm_product_5"
        new_version=digest("genuinely new source six")
        dest=self.root/"production-warehouse/finished"/new_name/new_version
        dest.mkdir(parents=True,mode=0o700)
        manifest=json.loads((original/"warehouse_manifest.json").read_text())
        manifest.update(product_id=new_name,source_sha256=new_version)
        (dest/"warehouse_manifest.json").write_text(json.dumps(manifest))
        (dest/"product.zip").write_bytes((original/"product.zip").read_bytes())
        courier.import_site(courier.export_factory(self.root),self.site)
        self.assertEqual(courier.three_site_product_requests(self.site,cycle="20261019"),first)

    def test_tampered_persisted_site_batch_still_fails_closed(self):
        courier.three_site_product_requests(self.site,cycle="20261019")
        receipt=self.site/"product-orders-outbound"/"20261019.json"
        original=json.loads(receipt.read_text())
        original["requests"][0]["artifact_sha256"]="f"*64
        receipt.write_text(json.dumps(original))
        with self.assertRaisesRegex(RuntimeError,"THREE_ORDERS_SITE_RECEIPT_CONFLICT"):
            courier.three_site_product_requests(self.site,cycle="20261019")

    def test_no_backlog_explosion_before_first_three_are_completed(self):
        first=courier.three_site_product_requests(self.site,cycle="20261019")
        courier.receive_three_product_requests(first,self.root,ENGINE)
        next_=courier.three_site_product_requests(self.site,cycle="20261020")
        blocked=courier.receive_three_product_requests(next_,self.root,ENGINE)
        self.assertEqual(blocked["received_verified_site_requests"],3)
        self.assertEqual(blocked["native_product_orders"],[])
        self.assertEqual(blocked["status"],"waiting_for_prior_three_to_complete")
        self.assertEqual(len(list((self.root/"production-instructions/orders").glob("WO-*.json"))),3)
        for file in (self.root/"production-instructions/orders").glob("WO-*.json"):
            row=json.loads(file.read_text());row["status"]="completed_verified"
            file.write_text(json.dumps(row))
        done=courier.receive_three_product_requests(next_,self.root,ENGINE)
        self.assertEqual(done["new_native_orders"],3)
        self.assertEqual(len(list((self.root/"production-instructions/orders").glob("WO-*.json"))),6)

    def test_site_order_shares_no_other_tenant_and_cannot_spoof_customer_sale(self):
        raw=json.loads(courier.three_site_product_requests(self.site,cycle="20261019"))
        raw["tenant"]="zomorodmelal-main"
        with self.assertRaisesRegex(RuntimeError,"THREE_ORDERS_BATCH_SCHEMA"):
            courier.receive_three_product_requests(json.dumps(raw).encode(),self.root,ENGINE)
        raw["tenant"]=courier.TENANT
        raw["requests"][0]["paid_customer_purchase"]=True
        with self.assertRaisesRegex(RuntimeError,"THREE_ORDERS_REQUEST_INVALID"):
            courier.receive_three_product_requests(json.dumps(raw).encode(),self.root,ENGINE)
        self.assertFalse(list((self.root/"production-instructions/orders").glob("WO-*.json")))

    def test_source_manufacture_sha_and_site_return_tampering_is_rejected(self):
        raw=courier.three_site_product_requests(self.site,cycle="20261019")
        task=json.loads(raw)["requests"][0]
        back=self.root/"design-intake/mojplaywin-stage1-quality-returns"/(
             task["product_id"]+"-"+task["source_sha256"]+".json")
        row=json.loads(back.read_text());row["artifact_sha256"]="f"*64
        back.write_text(json.dumps(row))
        with self.assertRaisesRegex(RuntimeError,"THREE_ORDERS_UNVERIFIED_SITE_FEEDBACK"):
            courier.receive_three_product_requests(raw,self.root,ENGINE)

    def test_three_new_companions_max_per_stock_transfer_tick(self):
        with patch.object(courier,"customer_companion") as source:
            source.return_value=({"package_sha256":"a"*64},b"fake temporary ZIP")
            archive=courier.export_factory(self.root)
        with tarfile.open(fileobj=io.BytesIO(archive),mode="r:gz") as t:
            index=json.loads(t.extractfile("index.json").read())
            self.assertEqual(index["inventory_count"],5)
            self.assertEqual(sum(item["consumer_package_sha256"] is not None
                                 for item in index["items"]),3)
            self.assertEqual(sum(name.endswith("/customer-package.zip")
                                 for name in t.getnames()),3)

if __name__=="__main__":unittest.main()
