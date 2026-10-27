"""One MojPlayWin private courier: end-to-end, deterministic, no other sites."""
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.mpw_vps_warehouse_courier import (
    SCHEMA, TENANT, ISSUES, digest, export_factory, import_site,
    feedback_site, receive_factory_returns, triage_factory_stage1, unpack, safe_zip,
)


def build_zip():
    memory=io.BytesIO()
    with zipfile.ZipFile(memory,"w",compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("product/readme.txt","Private factory QA test — not approved for sale")
        archive.writestr("license/notice.txt","Commercial license review is required")
    return memory.getvalue()


class VPSWarehouseCourierTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name)
        self.factory=base/"factory"
        self.factory.mkdir(mode=0o700)
        (self.factory/"design-intake").mkdir(mode=0o700)
        (self.factory/"production-warehouse/finished").mkdir(parents=True,mode=0o700)
        self.site=base/"cpanel"
        self.site.mkdir(mode=0o700)
        self.product="farm_economics"
        self.version="a"*64
        self.zip=build_zip()
        folder=self.factory/"production-warehouse/finished"/self.product/self.version
        folder.mkdir(parents=True,mode=0o700)
        self.stock=folder
        self.manifest={
            "schema":"saeit.factory.production-warehouse.v1",
            "product_id":self.product,"source_sha256":self.version,
            "artifact_sha256":digest(self.zip),"manufacturing_qc":"passed",
            "production_state":"finished_goods_in_factory",
            "commercial_release":False,"site_transfer_state":"not_transferred",
            "content_rights_market_review":"pending","receiving_site":None,
            "bytes":len(self.zip),
        }
        (folder/"warehouse_manifest.json").write_text(json.dumps(self.manifest))
        (folder/"product.zip").write_bytes(self.zip)

    def test_real_end_to_end_quality_return_to_first_factory_stage(self):
        archive=export_factory(self.factory)
        self.assertEqual(len(unpack(archive)),1)
        result=import_site(archive,self.site)
        self.assertEqual(result["factory_versions_observed"],1)
        self.assertEqual(result["new_private_imports"],1)
        self.assertEqual(result["pending_stage1_return"],1)
        self.assertEqual(result["store_product_created"],0)
        self.assertEqual(result["publicly_published"],0)
        record=self.site/"received"/self.product/self.version/"site_qa.json"
        self.assertTrue(record.is_file())
        self.assertEqual(json.loads(record.read_text())["qa_state"],"requires_factory_stage1_rework")
        out=receive_factory_returns(feedback_site(self.site),self.factory)
        self.assertEqual(out["accepted_stage1_qa_returns"],1)
        self.assertFalse(out["factory_repair_executed"])
        ret=self.factory/"design-intake/mojplaywin-stage1-quality-returns"/(
             self.product+"-"+self.version+".json")
        self.assertTrue(ret.is_file())
        doc=json.loads(ret.read_text())
        self.assertEqual(doc["stage"],1)
        self.assertEqual(doc["issues"],list(ISSUES))
        self.assertFalse(doc["published"])
        self.assertTrue((self.stock/"product.zip").is_file())

    def test_return_queue_is_actually_consumed_at_first_factory_stage(self):
        raw=export_factory(self.factory)
        import_site(raw,self.site)
        receive_factory_returns(feedback_site(self.site),self.factory)
        first=triage_factory_stage1(self.factory)
        self.assertEqual(first["factory_stage1_work_items"],1)
        self.assertEqual(first["unresolved_independent_review_items"],1)
        self.assertFalse(first["commercial_approval_claimed"])
        state=(self.factory/"design-state/mojplaywin-stage1-qa-work"/
               (self.product+"-"+self.version+".json"))
        before=state.read_bytes()
        self.assertTrue(state.is_file())
        entry=json.loads(before)
        self.assertEqual(entry["factory_entry_stage"],1)
        self.assertEqual(len(entry["actual_tasks"]),4)
        self.assertFalse(entry["production_rebuild_executed"])
        self.assertTrue((self.stock/"product.zip").is_file())
        again=triage_factory_stage1(self.factory)
        self.assertEqual(again["factory_stage1_work_items"],1)
        self.assertEqual(state.read_bytes(),before)

    def test_stage_one_work_never_claims_factory_quality_approval(self):
        raw=export_factory(self.factory)
        import_site(raw,self.site)
        receive_factory_returns(feedback_site(self.site),self.factory)
        triage_factory_stage1(self.factory)
        status=self.factory/"design-state/mojplaywin-stage1-qa-work/stage1-status.json"
        self.assertFalse(json.loads(status.read_text())["commercial_approval_claimed"])
        self.assertFalse(json.loads(status.read_text())["physical_rebuild_claimed"])

    def test_retry_is_idempotent_no_duplicate_and_version_preserved(self):
        first=export_factory(self.factory)
        import_site(first,self.site)
        second=import_site(first,self.site)
        self.assertEqual(second["new_private_imports"],0)
        self.assertEqual(second["duplicate_versions_skipped"],1)
        self.assertEqual(receive_factory_returns(feedback_site(self.site),self.factory)["accepted_stage1_qa_returns"],1)
        self.assertEqual(receive_factory_returns(feedback_site(self.site),self.factory)["previously_queued"],1)
        entries=list((self.factory/"design-intake/mojplaywin-stage1-quality-returns").iterdir())
        self.assertEqual(len(entries),1)

    def test_52_receipts_are_delivered_in_bounded_pages_with_idempotent_retry(self):
        archive=export_factory(self.factory)
        import_site(archive,self.site)
        folder=self.site/"returns"/self.product
        template=json.loads((folder/(self.version+".json")).read_text())
        for index in range(1,52):
            version=f"{index:064x}"
            row=dict(template,source_sha256=version)
            (folder/(version+".json")).write_text(json.dumps(row))
            stock=self.factory/"production-warehouse/finished"/self.product/version
            stock.mkdir(parents=True,mode=0o700)
            manifest=dict(self.manifest,source_sha256=version)
            (stock/"warehouse_manifest.json").write_text(json.dumps(manifest))
            (stock/"product.zip").write_bytes(self.zip)
        pages=[feedback_site(self.site,page=p) for p in range(2)]
        identities=[(r["product_id"],r["source_sha256"])
                    for payload in pages for r in json.loads(payload)["returns"]]
        self.assertEqual(len(identities),52)
        self.assertEqual(len(set(identities)),52)
        self.assertEqual([len(json.loads(p)["returns"]) for p in pages],[50,2])
        self.assertEqual(json.loads(feedback_site(self.site,page=2))["returns"],[])
        self.assertEqual(sum(receive_factory_returns(p,self.factory)["accepted_stage1_qa_returns"]
                             for p in pages),52)
        self.assertEqual(sum(receive_factory_returns(p,self.factory)["previously_queued"]
                             for p in pages),52)
        state=triage_factory_stage1(self.factory)
        self.assertEqual(state["factory_stage1_work_items"],52)
        self.assertFalse(state["commercial_approval_claimed"])
        with self.assertRaisesRegex(RuntimeError,"RETURN_PAGE_INVALID"):
            feedback_site(self.site,page=32)

    def test_page_snapshot_fingerprint_detects_new_receipts_and_content_changes(self):
        archive=export_factory(self.factory)
        import_site(archive,self.site)
        first=json.loads(feedback_site(self.site,page=0))
        second=json.loads(feedback_site(self.site,page=1))
        self.assertRegex(first["snapshot_sha256"],r"^[a-f0-9]{64}$")
        self.assertEqual(first["snapshot_sha256"],second["snapshot_sha256"])
        self.assertEqual(second["returns"],[])
        folder=self.site/"returns"/self.product
        original=folder/(self.version+".json")
        row=json.loads(original.read_text())
        row["issues"]=list(row["issues"])+["ADDITIONAL_REVIEW_REQUIRED"]
        original.write_text(json.dumps(row))
        changed=json.loads(feedback_site(self.site,page=0))
        self.assertNotEqual(first["snapshot_sha256"],changed["snapshot_sha256"])
        another="b"*64
        row=dict(row,source_sha256=another)
        (folder/(another+".json")).write_text(json.dumps(row))
        extended=json.loads(feedback_site(self.site,page=0))
        self.assertNotEqual(changed["snapshot_sha256"],extended["snapshot_sha256"])
        self.assertEqual(len(extended["returns"]),2)

    def test_exact_1600_receipts_fills_last_page_and_1601_fails_closed(self):
        archive=export_factory(self.factory)
        import_site(archive,self.site)
        folder=self.site/"returns"/self.product
        template=json.loads((folder/(self.version+".json")).read_text())
        for index in range(1,1600):
            version=f"{index:064x}"
            row=dict(template,source_sha256=version)
            (folder/(version+".json")).write_text(json.dumps(row))
        last=json.loads(feedback_site(self.site,page=31))
        self.assertEqual(len(last["returns"]),50)
        self.assertEqual(len(json.loads(feedback_site(self.site,page=0))["returns"]),50)
        extra=dict(template,source_sha256="f"*64)
        (folder/("f"*64+".json")).write_text(json.dumps(extra))
        with self.assertRaisesRegex(RuntimeError,"RETURN_BACKLOG_REQUIRES_REVIEW"):
            feedback_site(self.site,page=31)

    def test_factory_authorization_never_inferred_from_technical_qa(self):
        self.manifest["commercial_release"]=True
        (self.stock/"warehouse_manifest.json").write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(RuntimeError,"WAREHOUSE_RECEIPT_NOT_VERIFIED"):
            export_factory(self.factory)

    def test_source_zip_tampering_fails_before_transfer(self):
        (self.stock/"product.zip").write_bytes(self.zip+b"tampered")
        with self.assertRaisesRegex(RuntimeError,"WAREHOUSE_RECEIPT_NOT_VERIFIED"):
            export_factory(self.factory)

    def test_site_feedback_wrong_tenant_cannot_write_factory(self):
        raw=json.dumps({"schema":"mpw.factory.return-to-stage1.v1",
                        "tenant":"zomorodmelal-main","returns":[]}).encode()
        with self.assertRaisesRegex(RuntimeError,"INVALID_MOJPLAYWIN_FEEDBACK"):
            receive_factory_returns(raw,self.factory)
        self.assertFalse((self.factory/"design-intake/mojplaywin-stage1-quality-returns").exists())

    def test_unsafe_product_name_is_rejected(self):
        wrong=self.factory/"production-warehouse/finished"/"../escape"
        # Even if a foreign directory is inserted, path inventory validates recipe.
        p=self.factory/"production-warehouse/finished"/"bad-product"
        p.mkdir(mode=0o700)
        with self.assertRaisesRegex(RuntimeError,"WAREHOUSE_PRODUCT_PATH_INVALID"):
            export_factory(self.factory)

    def test_private_import_does_not_create_shop_records(self):
        batch=export_factory(self.factory)
        import_site(batch,self.site)
        for candidate in ("public_html","products","store","checkout"):
            self.assertFalse((self.site/candidate).exists())

    def test_zip_bomb_or_path_traversal_rejected(self):
        x=io.BytesIO()
        with zipfile.ZipFile(x,"w") as z:
            z.writestr("../../outside.txt","no")
        with self.assertRaisesRegex(RuntimeError,"ZIP_TRAVERSAL_OR_DUPLICATE"):
            safe_zip(x.getvalue())


if __name__=="__main__":
    unittest.main()
