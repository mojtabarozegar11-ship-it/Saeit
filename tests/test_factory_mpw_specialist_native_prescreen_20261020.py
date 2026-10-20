"""Specialist-native QA must inspect real bytes, preserve stock and never license goods."""
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
import wave
import zipfile
import zlib

from scripts import mpw_vps_warehouse_courier as courier
from scripts import factory_mpw_specialist_native_prescreen_20261020 as specialist

ENGINE=Path(__file__).resolve().parents[1]/"scripts/factory_continuous_production_orders.py"


def zipped(files):
    b=io.BytesIO()
    with zipfile.ZipFile(b,"w",compression=zipfile.ZIP_DEFLATED) as archive:
        for name,raw in sorted(files.items()):
            archive.writestr(name,raw)
    return b.getvalue()


def png_sample():
    def chunk(typ,payload):
        return struct.pack(">I",len(payload))+typ+payload+struct.pack(">I",zlib.crc32(typ+payload))
    hdr=struct.pack(">IIBBBBB",1,1,8,2,0,0,0)
    return (b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",hdr)+
            chunk(b"IDAT",zlib.compress(b"\x00\xff\x00\x00"))+chunk(b"IEND",b""))


def wav_sample():
    b=io.BytesIO()
    with wave.open(b,"wb") as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000)
        wav.writeframes(b"".join(struct.pack("<h",((i*73)%30000)-15000) for i in range(16000)))
    return b.getvalue()


class SourceQualityTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        (self.root/"production-warehouse/finished").mkdir(parents=True)
        (self.root/"production-instructions/orders").mkdir(parents=True)

    def add(self,product,version,family,files):
        source=zipped(files)
        folder=self.root/"production-warehouse/finished"/product/version
        folder.mkdir(parents=True)
        manifest={
            "schema":"saeit.factory.production-warehouse.v1",
            "product_id":product,"source_sha256":version,
            "artifact_sha256":courier.digest(source),"bytes":len(source),
            "manufacturing_qc":"passed","production_state":"finished_goods_in_factory",
            "commercial_release":False,"site_transfer_state":"not_transferred",
            "content_rights_market_review":"pending","receiving_site":None,
            "family_id":family
        }
        (folder/"product.zip").write_bytes(source)
        (folder/"warehouse_manifest.json").write_text(json.dumps(manifest))
        return manifest,source

    def test_png_full_crc_and_bounded_decode_rejects_tamper(self):
        good=png_sample()
        self.assertIn("crc",specialist.png_gate(good))
        broken=bytearray(good);broken[50]^=1
        with self.assertRaisesRegex(ValueError,"PNG_CHUNK_CRC"):
            specialist.png_gate(bytes(broken))

    def test_office_xml_real_sheets_and_wav_pcm(self):
        xlsx=zipped({
            "[Content_Types].xml":b'<Types><Override/></Types>',
            "xl/workbook.xml":b'<workbook><sheets><sheet/></sheets></workbook>',
            "xl/worksheets/sheet1.xml":b'<worksheet><sheetData><row/></sheetData></worksheet>'})
        self.assertIn("xml_parse",specialist.office_gate(xlsx,".xlsx"))
        with self.assertRaises(ValueError):
            specialist.office_gate(zipped({"doc.txt":b"text"}),".xlsx")
        self.assertIn("pcm_frames",specialist.wav_gate(wav_sample()))
        with self.assertRaises(ValueError):
            specialist.wav_gate(b"RIFFgarbageWAVE")

    def test_mp4_atoms_and_no_runtime_approval(self):
        def atom(t,p):return struct.pack(">I",len(p)+8)+t+p
        m=atom(b"ftyp",b"isom1234")+atom(b"moov",atom(b"trak",b"vide"))+atom(b"mdat",b"binaryframes")
        self.assertIn("video_track",specialist.mp4_gate(m))
        with self.assertRaises(ValueError):
            specialist.mp4_gate(atom(b"ftyp",b"isom1234"))
        source=zipped({
            "site/example.py":b"def sum_two(a,b): return a+b\n",
            "site/rules.json":b'{"kind":"educational"}',
            "site/README.md":b"Original software for private review."
        })
        manifest={"family_id":"F20","artifact_sha256":courier.digest(source),
                  "product_id":"valid_product","source_sha256":"a"*64,
                  "schema":"saeit.factory.production-warehouse.v1",
                  "bytes":len(source),"manufacturing_qc":"passed",
                  "production_state":"finished_goods_in_factory",
                  "commercial_release":False,"site_transfer_state":"not_transferred",
                  "content_rights_market_review":"pending","receiving_site":None}
        result=specialist.assess("valid_product","a"*64,manifest,source,courier)
        self.assertTrue(result["automated_format_prescreen_passed"])
        self.assertFalse(result["commercial_release"])
        self.assertFalse(result["functional_acceptance_for_native_product_verified"])
        self.assertFalse(result["python_or_javascript_executed"])

    def test_missing_provenance_is_not_accepted(self):
        manifest,blob=self.add("anonymous_original","a"*64,None,{
            "task/run.py":b"def f(): return 42",
            "task/config.json":b'{"ok":true}',
            "task/README.md":b"real usage instructions"})
        result=specialist.assess("anonymous_original","a"*64,manifest,blob,courier)
        self.assertFalse(result["automated_format_prescreen_passed"])
        self.assertIn("MISSING_OR_UNSUPPORTED_FAMILY_PROVENANCE",
                      result["automated_technical_blockers"])

    def test_missing_family_recovers_only_exact_original_qa_sha_without_stock_mutation(self):
        product="legacy_calc"
        version="a"*64
        manifest,blob=self.add(product,version,None,{
            "tool/main.py":b"def add(x,y): return x+y\n",
            "tool/data.json":b'{"value":3}',
            "tool/README.md":b"Original program."})
        source=self.root/"digital-products"/product
        source.mkdir(parents=True)
        (source/(product+"-internal-qa.zip")).write_bytes(blob)
        receipt={"recipe":product,"source_sha256":version,
                 "artifact_sha256":manifest["artifact_sha256"],
                 "family_id":"F20","qa_status":"passed"}
        (source/"manufacturing_manifest.json").write_text(json.dumps(receipt))
        repaired=specialist.assess(product,version,manifest,blob,courier,self.root)
        self.assertTrue(repaired["automated_format_prescreen_passed"])
        self.assertEqual(repaired["family_id"],"F20")
        self.assertEqual(repaired["family_provenance_source"],"sha256_matched_original_manufacturing_qa")
        self.assertFalse(repaired["commercial_release"])
        before=(self.root/"production-warehouse/finished"/product/version/"warehouse_manifest.json").read_bytes()
        run=specialist.run(self.root,courier,ENGINE)
        self.assertEqual(run["counts"]["source_sha_matched_family_recoveries"],1)
        self.assertEqual(specialist.run(self.root,courier,ENGINE)["counts"],run["counts"])
        self.assertEqual((self.root/"production-warehouse/finished"/product/version/"warehouse_manifest.json").read_bytes(),before)
        receipt["source_sha256"]="b"*64
        (source/"manufacturing_manifest.json").write_text(json.dumps(receipt))
        rejected=specialist.assess(product,version,manifest,blob,courier,self.root)
        self.assertIn("MISSING_OR_UNSUPPORTED_FAMILY_PROVENANCE",rejected["automated_technical_blockers"])
        receipt["source_sha256"]=version
        receipt["family_id"]="F99"
        (source/"manufacturing_manifest.json").write_text(json.dumps(receipt))
        rejected=specialist.assess(product,version,manifest,blob,courier,self.root)
        self.assertFalse(rejected["automated_format_prescreen_passed"])
        receipt["family_id"]="F20"
        (source/"manufacturing_manifest.json").write_text(json.dumps(receipt))
        (source/(product+"-internal-qa.zip")).write_bytes(blob+b"corruption")
        rejected=specialist.assess(product,version,manifest,blob,courier,self.root)
        self.assertFalse(rejected["automated_format_prescreen_passed"])

    def test_real_work_order_evidence_packet_is_replay_safe_and_not_closed(self):
        version="1"*64
        manifest,stock=self.add("original_python_tool",version,"F20",{
            "product/check.py":b"def run(a,b):\n    return a+b\n",
            "product/data.json":b'{"numbers":[2,3]}',
            "product/README.md":b"Usable source and examples."})
        order=self.root/"production-instructions/orders/WO-00000001.json"
        original={
            "schema":"saeit.factory.production-instructions.v1",
            "id":"WO-00000001","fingerprint":"f"*64,"status":"blocked_rework",
            "public_distribution_allowed":False,"requesting_site":"mojplaywin.com",
            "source_product_id":"original_python_tool","source_sha256":version,
            "source_artifact_sha256":manifest["artifact_sha256"],
            "manufacturing_qa_passed":False,"publication_approved":False}
        order.write_text(json.dumps(original))
        first=specialist.run(self.root,courier,ENGINE)
        self.assertEqual(first["counts"]["original_stock_checked"],1)
        self.assertEqual(first["counts"]["prescreen_format_passed"],1)
        self.assertEqual(first["counts"]["site_origin_work_orders_evidence_linked"],1)
        self.assertEqual(first["completed_manufacturing_work_orders_claimed"],0)
        files=list((self.root/"production-instructions/mojplaywin-specialist-order-reports").glob("*.json"))
        self.assertEqual(len(files),1)
        packet=json.loads(files[0].read_text())
        self.assertFalse(packet["engineering_work_order_completed"])
        self.assertTrue(packet["needs_licensing_and_rights_review"])
        self.assertEqual(packet["source_artifact_sha256"],manifest["artifact_sha256"])
        self.assertEqual(specialist.run(self.root,courier,ENGINE)["counts"],
                         first["counts"])
        self.assertEqual(len(list(
            (self.root/"production-instructions/mojplaywin-specialist-order-reports").glob("*.json"))),1)
        self.assertEqual((self.root/"production-warehouse/finished"/"original_python_tool"/version/"product.zip").read_bytes(),stock)

    def test_invalid_source_sha_stops_without_touching_original(self):
        manifest,_=self.add("original_valid_code","b"*64,"F20",{
            "product/test.py":b"def ok(): return True",
            "product/report.json":b'{"ok":true}',
            "product/README.md":b"Original"})
        where=self.root/"production-warehouse/finished/original_valid_code"/("b"*64)/"product.zip"
        where.write_bytes(where.read_bytes()+b"x")
        with self.assertRaisesRegex(RuntimeError,"WAREHOUSE_RECEIPT_NOT_VERIFIED"):
            specialist.run(self.root,courier,ENGINE)
        self.assertFalse((self.root/"design-state/mojplaywin-native-specialist-evidence/dashboard.json").exists())


if __name__=="__main__":
    unittest.main()
