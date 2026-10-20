"""Deep source validation: real bytes and immutable return receipts, no fake approvals."""
import io,json,struct,tempfile,unittest,zipfile,zlib
from pathlib import Path
from scripts import mpw_factory_stage1_deep_evidence as deep
from scripts import mpw_factory_stage1_technical_repair as repair
from scripts import mpw_vps_warehouse_courier as courier

def zip_bytes(mapping):
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as z:
        for name,body in mapping.items():z.writestr(name,body)
    return buf.getvalue()
def png():
    def ch(kind,data):
        return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data)&0xffffffff)
    rgb=b"\x00\xff\x00\x00"
    return b"\x89PNG\r\n\x1a\n"+ch(b"IHDR",struct.pack(">IIBBBBB",1,1,8,2,0,0,0))+ch(b"IDAT",zlib.compress(rgb))+ch(b"IEND",b"")
class DeepNativeQATests(unittest.TestCase):
    def test_real_png_crc_and_mutation_detected(self):
        sample=png()
        self.assertIn("crc",deep.verify_png(sample))
        bad=bytearray(sample);bad[-6]^=1
        with self.assertRaisesRegex(ValueError,"PNG_CRC"):
            deep.verify_png(bytes(bad))
    def test_native_docx_and_epub_xml_containers(self):
        docx=zip_bytes({"[Content_Types].xml":"<Types/>","word/document.xml":"<document/>"})
        self.assertIn("xml",deep.verify_woffice(docx,"docx"))
        epub=zip_bytes({"mimetype":"application/epub+zip",
           "META-INF/container.xml":"<container/>"})
        self.assertIn("epub",deep.verify_woffice(epub,"epub"))
        wrong=zip_bytes({"mimetype":"not-an-epub","META-INF/container.xml":"<container/>"})
        with self.assertRaisesRegex(ValueError,"EPUB_MIMETYPE"):
            deep.verify_woffice(wrong,"epub")
    def test_pdf_and_wav_reject_misleading_header(self):
        with self.assertRaisesRegex(ValueError,"PDF_TRAILER"):deep.verify_pdf(b"%PDF-1.7\nnot complete")
        with self.assertRaisesRegex(ValueError,"WAV_HEADER"):deep.verify_wav(b"RIFF"+b"\0"*40)
    def test_stage1_one_genuine_receipt_deep_checked_not_closed(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);product="native_demo";version="a"*64
            blob=zip_bytes({"native_demo/README.md":"An original useful operating guide."})
            stock=root/"production-warehouse/finished"/product/version
            stock.mkdir(parents=True)
            manifest={"schema":"saeit.factory.production-warehouse.v1",
              "product_id":product,"source_sha256":version,"artifact_sha256":courier.digest(blob),
              "bytes":len(blob),"manufacturing_qc":"passed","production_state":"finished_goods_in_factory",
              "commercial_release":False,"site_transfer_state":"not_transferred",
              "content_rights_market_review":"pending","receiving_site":None}
            (stock/"product.zip").write_bytes(blob)
            (stock/"warehouse_manifest.json").write_text(json.dumps(manifest))
            row={"schema":courier.RETURN_SCHEMA,"tenant":courier.TENANT,"product_id":product,
             "source_sha256":version,"artifact_sha256":manifest["artifact_sha256"],
             "stage":1,"status":"return_for_qa_completion","issues":list(courier.ISSUES),
             "factory_original_must_be_preserved":True,"published":False}
            folder=root/"design-intake/mojplaywin-stage1-quality-returns"
            folder.mkdir(parents=True)
            (folder/(product+"-"+version+".json")).write_text(json.dumps(row))
            outcome=deep.run(root,courier,repair)
            self.assertEqual(outcome["returned_versions"],1)
            self.assertEqual(outcome["deep_passed_files"],1)
            self.assertEqual(outcome["technical_member_defects"],0)
            self.assertEqual(outcome["stage1_returns_still_open"],1)
            receipt=json.loads((root/"design-state/mojplaywin-source-specific-reviews"/(product+"-"+version+".json")).read_text())
            self.assertTrue(receipt["original_archive_valid"])
            self.assertIsNone(receipt["independent_reviewer_signature"])
            self.assertFalse(receipt["customer_payment_enabled"])
            self.assertEqual((stock/"product.zip").read_bytes(),blob)
if __name__=="__main__":unittest.main()
