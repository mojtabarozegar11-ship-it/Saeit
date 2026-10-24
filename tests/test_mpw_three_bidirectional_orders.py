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
from scripts import factory_native_customer_packager as native

ENGINE=Path(__file__).resolve().parents[1]/"scripts/factory_continuous_production_orders.py"

def digest(s):
    return hashlib.sha256(s.encode()).hexdigest()

def goods_zip():
    z=io.BytesIO()
    with zipfile.ZipFile(z,"w",zipfile.ZIP_DEFLATED) as f:
        f.writestr("product/readme.txt","QA review candidate only")
        f.writestr("product/check.py","def validate():\n    return True\n")
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

    def test_next_site_orders_continue_without_waiting_for_prior_completion(self):
        self._extend_real_stock_to_twelve()
        first=courier.three_site_product_requests(self.site,cycle="20261019")
        courier.receive_three_product_requests(first,self.root,ENGINE)
        second=courier.three_site_product_requests(self.site,cycle="20261020")
        second_result=courier.receive_three_product_requests(second,self.root,ENGINE,max_active=0)
        third=courier.three_site_product_requests(self.site,cycle="20261021")
        third_result=courier.receive_three_product_requests(third,self.root,ENGINE,max_active=0)
        self.assertEqual(second_result["new_native_orders"],3)
        self.assertEqual(third_result["new_native_orders"],3)
        self.assertEqual(len(list((self.root/"production-instructions/orders").glob("WO-*.json"))),9)
        fourth=courier.three_site_product_requests(self.site,cycle="20261022")
        fourth_result=courier.receive_three_product_requests(fourth,self.root,ENGINE,max_active=0)
        self.assertEqual(fourth_result["new_native_orders"],3)
        self.assertEqual(len(list((self.root/"production-instructions/orders").glob("WO-*.json"))),12)

    def test_verified_daily_source_rotation_avoids_old_unresolved_product_versions(self):
        self._extend_real_stock_to_twelve()
        first=courier.three_site_product_requests(self.site,cycle="20261019")
        second=courier.three_site_product_requests(self.site,cycle="20261020")
        third=courier.three_site_product_requests(self.site,cycle="20261021")
        def versions(batch):
            return {(x["product_id"],x["source_sha256"]) for x in json.loads(batch)["requests"]}
        self.assertEqual(len(versions(first)),3)
        self.assertEqual(len(versions(second)),3)
        self.assertEqual(len(versions(third)),3)
        self.assertFalse(versions(first)&versions(second))
        self.assertFalse(versions(first)&versions(third))
        self.assertFalse(versions(second)&versions(third))
        self.assertEqual(courier.three_site_product_requests(self.site,cycle="20261019"),first)
        self.assertEqual(courier.three_site_product_requests(self.site,cycle="20261020"),second)
        self.assertEqual(courier.three_site_product_requests(self.site,cycle="20261021"),third)
        self.assertFalse(any(row.get("paid_customer_purchase") for batch in (first,second,third)
                             for row in json.loads(batch)["requests"]))

    def test_tampered_earlier_batch_cannot_redirect_next_day_rotation(self):
        self._extend_real_stock_to_twelve()
        courier.three_site_product_requests(self.site,cycle="20261019")
        previous=self.site/"product-orders-outbound"/"20261019.json"
        record=json.loads(previous.read_text())
        record["tenant"]="forged"
        previous.write_text(json.dumps(record))
        with self.assertRaisesRegex(RuntimeError,"THREE_ORDERS_HISTORY_UNTRUSTED"):
            courier.three_site_product_requests(self.site,cycle="20261020")

    def test_new_site_work_orders_carry_only_a_verified_warehouse_family(self):
        batch=courier.three_site_product_requests(self.site,cycle="20261019")
        for row in json.loads(batch)["requests"]:
            target=self.root/"production-warehouse"/"finished"/row["product_id"]/row["source_sha256"]/"warehouse_manifest.json"
            manifest=json.loads(target.read_text())
            manifest["family_id"]="F28"
            target.write_text(json.dumps(manifest))
        admission=courier.receive_three_product_requests(batch,self.root,ENGINE)
        self.assertEqual(admission["new_native_orders"],3)
        for order in admission["native_product_orders"]:
            p=self.root/"production-instructions"/"orders"/(order+".json")
            ticket=json.loads(p.read_text())
            self.assertEqual(ticket["family_id"],"F28")
            self.assertFalse(ticket["publication_approved"])
            self.assertFalse(ticket["manufacturing_qa_passed"])

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

    def test_same_day_rescue_adds_three_real_new_sources_without_rewriting_first_batch(self):
        self._extend_real_stock_to_twelve()
        original=courier.three_site_product_requests(self.site,cycle="20261021")
        oldpath=self.site/"product-orders-outbound"/"20261021.json"
        oldbytes=oldpath.read_bytes()
        prior=courier.receive_three_product_requests(original,self.root,ENGINE)
        self.assertEqual(prior["new_native_orders"],3)
        self._private_preview_for_batch(original)
        courier.triage_site_work_orders(self.root,ENGINE)
        rescue=courier.three_site_product_requests(
            self.site,cycle="20261021-r1",require_fresh=True)
        x=json.loads(original)["requests"]
        y=json.loads(rescue)["requests"]
        self.assertEqual(json.loads(rescue)["cycle"],"20261021-r1")
        self.assertFalse({(r["product_id"],r["source_sha256"]) for r in x}
                         & {(r["product_id"],r["source_sha256"]) for r in y})
        new=courier.receive_three_product_requests(rescue,self.root,ENGINE)
        self.assertEqual(new["new_native_orders"],3)
        self.assertEqual(new["status"],"three_native_product_orders_created")
        self.assertEqual(oldpath.read_bytes(),oldbytes)
        self.assertEqual(courier.three_site_product_requests(
            self.site,cycle="20261021-r1",require_fresh=True),rescue)
        replay=courier.receive_three_product_requests(rescue,self.root,ENGINE)
        self.assertEqual(replay["status"],"already_admitted")
        self.assertEqual(replay["new_native_orders"],0)
        self.assertEqual(len(list((self.root/"production-instructions/orders").glob("WO-*.json"))),6)
        self.assertFalse(new["sales_or_publication_enabled"])

    def test_rescue_fails_closed_without_three_distinct_unused_sources(self):
        old=courier.three_site_product_requests(self.site,cycle="20261021")
        oldpath=self.site/"product-orders-outbound"/"20261021.json"
        oldbytes=oldpath.read_bytes()
        with self.assertRaisesRegex(RuntimeError,"THREE_ORDERS_RESCUE_NO_NEW_SOURCE"):
            courier.three_site_product_requests(self.site,cycle="20261021-r1",
                                                require_fresh=True)
        self.assertEqual(oldpath.read_bytes(),oldbytes)
        self.assertFalse((self.site/"product-orders-outbound"/"20261021-r1.json").exists())
        with self.assertRaisesRegex(RuntimeError,"THREE_ORDERS_CYCLE_INVALID"):
            courier.three_site_product_requests(self.site,cycle="20261021-r2")

    def test_source_manufacture_sha_and_site_return_tampering_is_rejected(self):
        raw=courier.three_site_product_requests(self.site,cycle="20261019")
        task=json.loads(raw)["requests"][0]
        back=self.root/"design-intake/mojplaywin-stage1-quality-returns"/(
             task["product_id"]+"-"+task["source_sha256"]+".json")
        row=json.loads(back.read_text());row["artifact_sha256"]="f"*64
        back.write_text(json.dumps(row))
        with self.assertRaisesRegex(RuntimeError,"THREE_ORDERS_UNVERIFIED_SITE_FEEDBACK"):
            courier.receive_three_product_requests(raw,self.root,ENGINE)

    def _extend_real_stock_to_twelve(self):
        # Distinct three-source daily requests are possible, not overlapping
        # when old work is held for legitimate specialist review.
        exemplar,ver,base_manifest=self.products[0]
        raw=(self.root/"production-warehouse/finished"/exemplar/ver/"product.zip").read_bytes()
        for i in range(5,12):
            product="farm_product_"+str(i)
            version=digest("real source "+str(i))
            dest=self.root/"production-warehouse/finished"/product/version
            dest.mkdir(parents=True,mode=0o700)
            manifest=dict(base_manifest,product_id=product,source_sha256=version)
            (dest/"warehouse_manifest.json").write_text(json.dumps(manifest))
            (dest/"product.zip").write_bytes(raw)
            self.products.append((product,version,manifest))
        courier.import_site(courier.export_factory(self.root),self.site)
        courier.receive_factory_returns(courier.feedback_site(self.site),self.root)

    def _private_preview_for_batch(self, batch):
        for row in json.loads(batch)["requests"]:
            item=row["product_id"];version=row["source_sha256"]
            stock=self.root/"production-warehouse/finished"/item/version
            manifest=json.loads((stock/"warehouse_manifest.json").read_text())
            native.pack(self.root,item,version,manifest,(stock/"product.zip").read_bytes(),courier)

    def test_real_provenance_triage_does_not_stop_other_orders(self):
        self._extend_real_stock_to_twelve()
        first=courier.three_site_product_requests(self.site,cycle="20261019")
        old=courier.receive_three_product_requests(first,self.root,ENGINE)
        self._private_preview_for_batch(first)
        triaged=courier.triage_site_work_orders(self.root,ENGINE)
        self.assertEqual(triaged["new_source_triages"],3)
        self.assertEqual(triaged["work_orders_completed_verified"],0)
        self.assertTrue(all(courier._prior_site_order_has_real_triage(self.root,json.loads((self.root/"production-instructions/orders"/(name+".json")).read_text())) for name in old["native_product_orders"]))
        for cycle in ("20261020","20261021","20261022"):
            batch=courier.three_site_product_requests(self.site,cycle=cycle)
            result=courier.receive_three_product_requests(batch,self.root,ENGINE)
            self.assertEqual(result["new_native_orders"],3)
        self.assertEqual(len(list((self.root/"production-instructions/orders").glob("WO-*.json"))),12)

    def test_missing_proof_does_not_freeze_new_independent_orders(self):
        self._extend_real_stock_to_twelve()
        first=courier.three_site_product_requests(self.site,cycle="20261019")
        prior=courier.receive_three_product_requests(first,self.root,ENGINE)
        next_=courier.three_site_product_requests(self.site,cycle="20261020")
        empty=courier.triage_site_work_orders(self.root,ENGINE)
        self.assertEqual(empty["new_source_triages"],0)
        self.assertEqual(empty["triage_blocked_missing_technical_evidence"],3)
        following=courier.receive_three_product_requests(next_,self.root,ENGINE)
        self.assertEqual(following["new_native_orders"],3)
        self.assertEqual(len(list((self.root/"production-instructions/orders").glob("WO-*.json"))),6)
        self.assertTrue(all(json.loads((self.root/"production-instructions/orders"/(name+".json")).read_text())["manufacturing_qa_passed"] is False for name in prior["native_product_orders"]))

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
