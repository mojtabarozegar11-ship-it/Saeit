"""Source-bound F34 pilot: accepted private binary formats never imply rights/sale."""
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile
import zlib
from scripts import factory_f34_commercial_pilot_20261020 as gate

def png(index=0):
    """Synthetic real decodable RGBA artwork, one distinct geometry per ID."""
    def chunk(typ,data):
        return struct.pack(">I",len(data))+typ+data+struct.pack(">I",zlib.crc32(typ+data))
    hdr=struct.pack(">IIBBBBB",256,256,8,6,0,0,0)
    rgb=bytes([30+(index*13)%180,40+(index*7)%170,50+(index*11)%160,255])
    transparent=b"\x00\x00\x00\x00"
    rows=[]
    for y in range(256):
        row=bytearray(b"\x00")
        for x in range(256):
            row.extend(rgb if 30<x<170+(index%37) and 35<y<188+(index%23)
                       else transparent)
        rows.append(bytes(row))
    return (b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",hdr)+
            chunk(b"IDAT",zlib.compress(b"".join(rows)))+chunk(b"IEND",b""))

class CommercialPilotAcceptance(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.product=gate.PRODUCT
        self.folder=self.root/"digital-products"/self.product
        self.folder.mkdir(parents=True)
        self.zipfile=self.folder/(self.product+"-internal-qa.zip")
        self.manifest=self.folder/"manufacturing_manifest.json"
        self.build()

    def build(self,broken=None):
        files={}
        icons=[]
        from scripts import factory_f34_ultra_quality_20261020 as ultra
        for i,(concept,variant) in enumerate(
                (a,b) for a in ultra.CONCEPTS for b in ultra.VARIANTS):
            key=concept+"_"+variant
            color="#%06x"%(0x220000+i*3491)
            svg=('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
                 'role="img" aria-labelledby="icon-title">'
                 '<title id="icon-title">'+concept+' '+variant+' icon</title>'
                 '<circle cx="32" cy="32" r="20" fill="none" stroke="'+color+'" stroke-width="3"/>'
                 '<polyline points="10,20 30,35 55,12" fill="none" stroke="'+color+'" stroke-width="2"/>'
                 '</svg>').encode()
            files[key+".svg"]=svg
            files[key+".png"]=png(i)
            icons.append({"id":key,"concept":concept,"treatment":variant,
                          "vector":key+".svg","raster":key+".png"})
        files.update({
            "README.md":b"Original F34 QA example with forty-eight original icon variants. "*10,
            "LICENSE.txt":b"PRIVATE internal QA artifact. No commercial sale or redistribution granted.",
            "catalog.json":json.dumps({"icons":icons}).encode(),
            "preview.html":("<html><body><main>"+ "".join(
                '<img src="'+x["raster"]+'"><a href="'+x["vector"]+'">SVG</a>' for x in icons)
                +"</main></body></html>").encode()
        })
        if broken:
            files.update(broken)
        with zipfile.ZipFile(self.zipfile,"w",compression=zipfile.ZIP_DEFLATED) as archive:
            for name,contents in sorted(files.items()):
                archive.writestr(self.product+"/"+name,contents)
        original=self.zipfile.read_bytes()
        self.manifest.write_text(json.dumps({
          "recipe":self.product,"family_id":"F34","source_sha256":"a"*64,
          "artifact_sha256":hashlib.sha256(original).hexdigest(),
          "qa_status":"passed","owner_publication_approval":False,
          "public_listing_enabled":False,
          "qa_measurements":{
            "review_kind":"separate_automated_technical_verification",
            "validated_archive_members":100,
            "archive_sha256":hashlib.sha256(original).hexdigest(),
            "critical_defects":[],
            "gates":{"gate_"+str(i):True for i in range(10)}}}))
        return original

    def test_private_pilot_materially_checks_all_pairs_without_sale(self):
        original=self.zipfile.read_bytes()
        response=gate.run(self.root)
        self.assertEqual(response["pairs_verified"],48)
        self.assertEqual(response["commercial_blockers"],4)
        self.assertGreaterEqual(response["measured_automated_assertions"],1500)
        self.assertTrue(response["automated_quality_passed"])
        self.assertFalse(response["sale_enabled"])
        self.assertFalse(response["owner_direction_present"])
        self.assertEqual(self.zipfile.read_bytes(),original)
        self.assertEqual(gate.run(self.root)["status"],"existing_receipt_verified")
        paths=list((self.root/"product-lifecycle/commercial-pilot-readiness").glob("*.json"))
        self.assertEqual(len(paths),1)
        receipt=json.loads(paths[0].read_text())
        self.assertTrue(receipt["automated_asset_integrity_verified"])
        self.assertFalse(receipt["commercial_publication_allowed"])
        self.assertFalse(receipt["independent_license_and_asset_rights_signed"])
        self.assertFalse(receipt["human_quality_signoff_required"])

    def test_owner_direction_is_not_per_sku_rights_and_sale(self):
        folder=self.root/"product-lifecycle/owner-commercial-instructions"
        folder.mkdir(parents=True)
        (folder/"20261020-commercial-direction.json").write_text(json.dumps({
            "schema":"saeit.factory.owner-commercial-direction.v1",
            "in_principle_commercial_publication_authorized":True,
            "unreviewed_private_stock_publication_allowed":False}))
        observed=gate.verify(self.root)
        self.assertTrue(observed["owner_in_principle_direction_present"])
        self.assertFalse(observed["buyer_access_enabled"])
        self.assertFalse(observed["commercial_publication_allowed"])

    def test_tampered_png_and_external_preview_fail_closed(self):
        bad=bytearray(png())
        bad[30]^=0x40
        self.build({"icon_00.png":bytes(bad)})
        with self.assertRaisesRegex(ValueError,"PILOT_PNG_CRC"):
            gate.verify(self.root)
        self.build({"preview.html":b'<html><body><img src="https://evil.example/x.png"></body></html>'})
        with self.assertRaisesRegex(ValueError,"PILOT_PREVIEW_EXTERNAL_OR_BROKEN_LINK"):
            gate.verify(self.root)

    def test_unchanged_sha_required_and_tech_flags_do_not_grant_rights(self):
        doc=json.loads(self.manifest.read_text())
        doc["artifact_sha256"]="b"*64
        self.manifest.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError,"PILOT_MANUFACTURING_SOURCE_CONTRACT_INVALID"):
            gate.verify(self.root)
        self.build({"LICENSE.txt":b"All rights automatically granted by AI"})
        with self.assertRaisesRegex(ValueError,"PILOT_PROVENANCE_OR_TERMS_REVIEW_MISSING"):
            gate.verify(self.root)

if __name__=="__main__":
    unittest.main()
