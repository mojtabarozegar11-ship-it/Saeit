"""Native private-format review candidates: actual source bytes, no fake buyer approval."""
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts import factory_native_customer_packager as native
from scripts import mpw_vps_warehouse_courier as courier
from scripts import mpw_factory_stage1_technical_repair as worker


def archive(files):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for name,content in sorted(files.items()):
            z.writestr(name,content)
    return stream.getvalue()


def svg_source():
    return archive({
        "native_art/README.md":"Original native vector assets, private format review.",
        "native_art/logo.svg":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4"/></svg>',
    })


class NativePreviewTest(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.product="genuine_native_art"
        self.version="a"*64
        self.original=svg_source()
        self.stock=self.root/"production-warehouse/finished"/self.product/self.version
        self.stock.mkdir(parents=True)
        self.manifest={
            "schema":"saeit.factory.production-warehouse.v1",
            "product_id":self.product,
            "source_sha256":self.version,
            "artifact_sha256":courier.digest(self.original),
            "bytes":len(self.original),"manufacturing_qc":"passed",
            "production_state":"finished_goods_in_factory",
            "commercial_release":False,"site_transfer_state":"not_transferred",
            "content_rights_market_review":"pending","receiving_site":None,
            "family_id":"F34",
        }
        (self.stock/"product.zip").write_bytes(self.original)
        (self.stock/"warehouse_manifest.json").write_text(json.dumps(self.manifest))

    def test_source_bound_static_preview_is_not_product_or_sales_approval(self):
        result=native.pack(self.root,self.product,self.version,self.manifest,self.original,courier)
        self.assertTrue(result["new"])
        self.assertTrue(result["native_structural_review_passed"])
        self.assertFalse(result["technical_buyer_package_verified"])
        self.assertFalse(result["commercial_release"])
        self.assertFalse(result["public_download_allowed"])
        candidate=courier.customer_companion(self.root,self.product,self.version,self.manifest["artifact_sha256"])
        self.assertEqual(candidate[0]["schema"],native.SCHEMA)
        self.assertEqual(candidate[0]["package_sha256"],courier.digest(candidate[1]))
        with zipfile.ZipFile(io.BytesIO(candidate[1])) as z:
            self.assertEqual(z.read("product/ORIGINAL_FACTORY_PRODUCT.zip"),self.original)
        self.assertFalse(native.pack(self.root,self.product,self.version,self.manifest,self.original,courier)["new"])
        self.assertEqual((self.stock/"product.zip").read_bytes(),self.original)

    def test_bad_format_and_unsafe_svg_block_native_pack(self):
        for corrupt in (
            {"native_art/misleading.png":b"not a png"},
            {"native_art/a.svg":b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'},
        ):
            value=archive(corrupt)
            receipt=dict(self.manifest,bytes=len(value),artifact_sha256=courier.digest(value))
            with self.assertRaisesRegex(RuntimeError,"NATIVE_"):
                native.pack(self.root,self.product,self.version,receipt,value,courier)
        self.assertFalse((self.root/"customer-packs"/self.product/self.version).exists())

    def test_forged_approval_and_tampered_customer_copy_rejected(self):
        receipt=native.pack(self.root,self.product,self.version,self.manifest,self.original,courier)
        path=self.root/"customer-packs"/self.product/self.version
        report=json.loads((path/"candidate_manifest.json").read_text())
        report["commercial_release"]=True
        with self.assertRaisesRegex(RuntimeError,"NATIVE_PREVIEW"):
            courier.verify_native_private_preview(report,(path/"customer-package.zip").read_bytes(),self.product,self.version,self.manifest["artifact_sha256"])
        raw=(path/"customer-package.zip").read_bytes()+b"x"
        with self.assertRaises(RuntimeError):
            courier.verify_native_private_preview(json.loads((path/"candidate_manifest.json").read_text()),raw,self.product,self.version,self.manifest["artifact_sha256"])
        self.assertFalse(receipt["eligible_for_commercial_listing"])

    def test_stage1_routes_native_source_and_preserves_human_blocker(self):
        inbox=self.root/"design-intake/mojplaywin-stage1-quality-returns"
        inbox.mkdir(parents=True)
        receipt={
            "schema":courier.RETURN_SCHEMA,"tenant":courier.TENANT,
            "product_id":self.product,"source_sha256":self.version,
            "artifact_sha256":self.manifest["artifact_sha256"],"stage":1,
            "status":"return_for_qa_completion","issues":list(courier.ISSUES),
            "published":False,"factory_original_must_be_preserved":True,
        }
        (inbox/(self.product+"-"+self.version+".json")).write_text(json.dumps(receipt))
        done=worker.run(self.root,max_new=43)
        self.assertEqual(done["returned_products_inspected"],1)
        self.assertEqual(done["new_native_private_previews_statically_validated"],1)
        self.assertEqual(done["new_customer_bundles_technically_repaired"],0)
        self.assertEqual(done["stage1_returns_remaining_open"],1)
        self.assertEqual(done["commercially_approved_returns"],0)
        after=worker.run(self.root,max_new=43)
        self.assertEqual(after["new_native_private_previews_statically_validated"],0)
        self.assertEqual(after["existing_native_private_previews_revalidated"],1)
        self.assertEqual(after["stage1_returns_remaining_open"],1)


if __name__=="__main__":
    unittest.main()
