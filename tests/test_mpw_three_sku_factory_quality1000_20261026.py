"""No-fake-QC1000/owner-preservation regression on exact retail version evidence."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

spec=importlib.util.spec_from_file_location("mpw_q1000",Path(__file__).resolve().parents[1]/
    "scripts/mpw_three_sku_factory_quality1000_20261026.py")
qc=importlib.util.module_from_spec(spec)
spec.loader.exec_module(qc)

def make_zip():
    with io.BytesIO() as buffer:
        with zipfile.ZipFile(buffer,"w") as bundle:
            bundle.writestr("index.html","<html><body>Good package</body></html>")
            bundle.writestr("README.md","original source records not included")
        return buffer.getvalue()

def make_pdf():
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Resources << >> /Contents 4 0 R >>",
        b"<< /Length 0 >>\nstream\n\nendstream"
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode())
        output.extend(body + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)

def install_fixture(root):
    hashes={}
    for ident in qc.IDS:
        data=(make_pdf() if ident !=879 else make_zip())
        h=hashlib.sha256(data).hexdigest()
        hashes[ident]=h
        folder=root/"copies"/str(ident)
        folder.mkdir(parents=True)
        (folder/(h+".bin")).write_bytes(data)
        request=root/"review-requests"/str(ident)
        request.mkdir(parents=True)
        (request/(h+".json")).write_text(json.dumps({
            "schema":qc.COPY_SCHEMA, "product_id":ident,"product_title":str(ident),
            "original_sha256":h,"copy_sha256":h,"bytes":len(data),
            "storefront_unchanged":True,"live_replacement_authorized":False
        }),encoding="utf8")
    return hashes

class Qc1000Tests(unittest.TestCase):
    def test_three_artifacts_generate_immutable_no_release_work_orders(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            identities=install_fixture(root)
            with contextlib.redirect_stdout(io.StringIO()):
                response=qc.run(root)
                repeated=qc.run(root)
            self.assertEqual(response,repeated)
            self.assertEqual([x["sku"] for x in response],list(qc.IDS))
            for ident in qc.IDS:
                directory=root/"quality1000-rework"/str(ident)/identities[ident]
                reports=list(directory.glob("*.json"))
                self.assertEqual(len(reports),1)
                ticket=json.loads(reports[0].read_text())
                self.assertEqual(len(ticket["quality_criteria"]),100)
                self.assertIsNone(ticket["professional_quality_score"])
                self.assertFalse(ticket["quality_1000_verified"])
                self.assertFalse(ticket["can_replace_live_store_file"])
                self.assertTrue(ticket["current_product_stays_published"])
                self.assertEqual(ticket["legal_dossier_status"], "owner_confirmed_complete")
                self.assertEqual(ticket["legal_execution_status"], "active")
                self.assertFalse(ticket["legal_dossier_reopened"])
                self.assertEqual(ticket["sku_version_mapping_status"], "execution_in_progress")
                legal_stage=next(stage for stage in ticket["rework_stages"]
                                 if stage["task"].startswith("reconcile the existing registered legal dossier"))
                self.assertEqual(legal_stage["state"], "owner_confirmed_dossier_complete_execution_active")
                self.assertEqual(ticket["source_file_sha256"],identities[ident])
                self.assertEqual(ticket["factory_copy_sha256"],identities[ident])
                self.assertEqual([t["approval"] for t in ticket["quality_criteria"]],
                                 ["PENDING_REAL_EVIDENCE"]*100)

    def test_tampered_copy_rejected_without_qa_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            hashes=install_fixture(root)
            (root/"copies"/"72"/(hashes[72]+".bin")).write_bytes(b"bad")
            with self.assertRaisesRegex(RuntimeError,"SOURCE_COPY_CHANGED"):
                qc.run(root)
            self.assertFalse((root/"quality1000-rework").exists())

    def test_zip_traversal_fails_without_extracting(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"attack.zip"
            with zipfile.ZipFile(source,"w") as z:
                z.writestr("../escape.txt","attack")
            with self.assertRaisesRegex(RuntimeError,"ZIP_UNSAFE_MEMBER"):
                qc.inspect_zip(source)
            self.assertFalse((Path(directory)/"escape.txt").exists())

    def test_pdf_and_zip_checks_never_claim_human_certification(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            hashes=install_fixture(root)
            with contextlib.redirect_stdout(io.StringIO()):
                result=qc.run(root)
            pdf=result[0]["versions"][0]
            web=result[2]["versions"][0]
            self.assertEqual(pdf["format"],"pdf")
            self.assertTrue(pdf["pdf_parser_available"])
            self.assertTrue(pdf["pdf_parser_passed"])
            self.assertEqual(pdf["pdf_pages"], 1)
            self.assertEqual(web["format"],"zip")
            self.assertTrue(web["zip_crc_passed"])
            self.assertFalse(pdf["quality1000_verified"])
            self.assertFalse(web["quality1000_verified"])

if __name__=="__main__":
    unittest.main()
