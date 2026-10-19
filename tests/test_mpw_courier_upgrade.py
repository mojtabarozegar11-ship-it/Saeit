"""Regression tests: signed per-version QA, pagination, scoped 3-order receipts."""
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile
from scripts import mpw_vps_warehouse_courier as c
from scripts import mpw_three_factory_orders as orders
from scripts import mpw_courier_catalog_drafts as catalog
from scripts import factory_continuous_production_orders as native

def sample_zip():
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w") as z:
        z.writestr("readme.txt","private product")
    return out.getvalue()

class CourierUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name)/"factory"
        (self.root/"production-warehouse/finished").mkdir(parents=True)
        (self.root/"design-intake").mkdir()
        (self.root/"production-instructions/orders").mkdir(parents=True)
        self.site=Path(self.t.name)/"site"
        self.site.mkdir(mode=0o700)
        self.blob=sample_zip()

    def add_product(self, num):
        product="game"
        version=format(num,"064x")
        path=self.root/"production-warehouse/finished"/product/version
        path.mkdir(parents=True)
        manifest={
            "schema":"saeit.factory.production-warehouse.v1","product_id":product,
            "source_sha256":version,"artifact_sha256":c.digest(self.blob),
            "manufacturing_qc":"passed","production_state":"finished_goods_in_factory",
            "commercial_release":False,"site_transfer_state":"not_transferred",
            "content_rights_market_review":"pending","receiving_site":None,"bytes":len(self.blob)
        }
        (path/"warehouse_manifest.json").write_text(json.dumps(manifest))
        (path/"product.zip").write_bytes(self.blob)
        return product,version,manifest

    def test_cursor_pages_past_fifty_unique_versions(self):
        for i in range(1,54):
            self.add_product(i)
        seen=set()
        cursor=""
        for _ in range(20):
            archive=c.export_factory(self.root,after=cursor)
            with tarfile.open(fileobj=io.BytesIO(archive),mode="r:gz") as z:
                index=json.load(z.extractfile("index.json"))
            rows=c.unpack(archive)
            self.assertTrue(0<len(rows)<=3)
            for name,version,_,_ in rows:
                self.assertNotIn((name,version),seen)
                seen.add((name,version))
            if not index["has_more"]:
                break
            self.assertNotEqual(cursor,index["next_cursor"])
            cursor=index["next_cursor"]
        self.assertEqual(len(seen),53)

    def test_review_is_pending_until_authenticated_per_artifact(self):
        name,version,manifest=self.add_product(1)
        archive=c.export_factory(self.root)
        result=c.import_site(archive,self.site)
        self.assertEqual(result["quality_approved"],0)
        rec=json.loads((self.site/"received"/name/version/"site_qa.json").read_text())
        self.assertEqual(rec["qa_state"],"awaiting_independent_product_review")
        self.assertFalse(rec["commercial_approved"])

    def test_independent_signed_review_is_not_a_commercial_sale(self):
        name,version,manifest=self.add_product(2)
        qa=self.site/"independent_qa"
        qa.mkdir(mode=0o700)
        key=b"independent reviewer test private key 0123456789"
        secret=qa/"reviewer_hmac.key"
        secret.write_bytes(key);os.chmod(secret,0o600)
        docs=qa/name
        docs.mkdir(mode=0o700)
        report={"schema":"mpw.factory.independent-qa.v1",
                "tenant":c.TENANT,"product_id":name,"source_sha256":version,
                "artifact_sha256":manifest["artifact_sha256"],
                "reviewer":"External named reviewer",
                "checks":{type_:{"passed":True,"evidence":"Reviewer-backed actual evidence reference for "+type_}
                          for type_ in ("content","rights","commercial_release")}}
        unsigned=json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
        report["signature"]=hmac.new(key,unsigned,hashlib.sha256).hexdigest()
        (docs/(version+".json")).write_text(json.dumps(report))
        result=c.import_site(c.export_factory(self.root),self.site)
        self.assertEqual(result["quality_approved"],1)
        self.assertEqual(result["pending_stage1_return"],0)
        self.assertFalse((self.site/"returns"/name/(version+".json")).exists())
        rec=json.loads((self.site/"received"/name/version/"site_qa.json").read_text())
        self.assertFalse(rec["commercial_approved"])
        self.assertFalse(rec["payment_enabled"])
        self.assertFalse(rec["public_listing"])

    def test_feedback_cursor_does_not_repeat_entries(self):
        for i in range(1,54):
            self.add_product(i)
        cursor=""
        imported=0
        while True:
            archive=c.export_factory(self.root,after=cursor)
            with tarfile.open(fileobj=io.BytesIO(archive),mode="r:gz") as z:
                idx=json.load(z.extractfile("index.json"))
            c.import_site(archive,self.site)
            imported+=idx["inventory_count"]
            if not idx["has_more"]:break
            cursor=idx["next_cursor"]
        self.assertEqual(imported,53)
        cursor=""
        got=0
        for _ in range(10):
            b=json.loads(c.feedback_site(self.site,after=cursor))
            got+=len(b["returns"])
            if not b["has_more"]:break
            cursor=b["next_cursor"]
        self.assertEqual(got,53)

    def test_unapproved_product_scans_only_as_private_draft(self):
        self.add_product(1)
        c.import_site(c.export_factory(self.root),self.site)
        rows=catalog.scan(self.site)
        self.assertEqual(len(rows),1)
        self.assertFalse(rows[0]["qa_passed"])
        self.assertEqual(rows[0]["product_id"],"game")

    def test_three_requests_wait_durably_if_native_factory_at_capacity(self):
        cycle="20261019-39287192970"
        first=orders.issue_three(self.root,native,cycle,max_active=0)
        self.assertEqual(first["status"],"waiting_for_native_capacity")
        self.assertEqual(first["requested"],3)
        self.assertEqual(first["native_accepted"],0)
        self.assertEqual(len(first["requests"]),3)
        retry=orders.issue_three(self.root,native,cycle,max_active=0)
        self.assertEqual(retry["new"],0)
        self.assertEqual(retry["requests"],first["requests"])
        self.assertFalse(list((self.root/"production-instructions/orders").glob("*.json")))

    def test_three_orders_per_run_native_queue_retry_safe(self):
        cycle="20261019-39287192970"
        one=orders.issue_three(self.root,native,cycle)
        self.assertEqual(one["new"],3)
        self.assertEqual(len(set(one["orders"])),3)
        again=orders.issue_three(self.root,native,cycle)
        self.assertEqual(again["new"],0)
        two=orders.issue_three(self.root,native,"20261019-39287192971")
        self.assertEqual(two["new"],3)
        self.assertEqual(len(list((self.root/"production-instructions/orders").glob("*.json"))),6)
        self.assertEqual({json.loads(p.read_text())["requesting_site"]
                          for p in (self.root/"production-instructions/orders").glob("*.json")},
                         {"mojplaywin.com"})

if __name__=="__main__":
    unittest.main()
