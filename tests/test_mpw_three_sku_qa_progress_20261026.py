import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import hashlib
import zipfile

spec=importlib.util.spec_from_file_location(
    "mpw_private_progress",
    Path(__file__).resolve().parents[1]/"scripts/mpw_three_sku_qa_progress_20261026.py",
)
progress=importlib.util.module_from_spec(spec)
spec.loader.exec_module(progress)

class PrivateProgressTests(unittest.TestCase):
    def write_json(self,path,value):
        path.parent.mkdir(parents=True,exist_ok=True)
        raw=(json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode()
        path.write_bytes(raw)
        return raw

    def seed(self,root,sku=72,failed=False):
        source=b"private-source-bytes"
        digest=hashlib.sha256(source).hexdigest()
        self.write_json(root/"review-requests"/str(sku)/(digest+".json"),{
            "schema":"saeit.mpw.live-three-private-qa-copy.v1","product_id":sku,
            "original_sha256":digest,"copy_sha256":digest,"storefront_unchanged":True,
            "live_replacement_authorized":False})
        copied=root/"copies"/str(sku)/(digest+".bin")
        copied.parent.mkdir(parents=True,exist_ok=True)
        copied.write_bytes(source)
        self.write_json(root/"quality1000-rework"/str(sku)/digest/"base.json",{
            "schema":"saeit.mpw.three-retail-artifact-qa1000-rework.v1","product_id":sku,
            "source_file_sha256":digest,"legal_dossier_status":"owner_confirmed_complete",
            "legal_execution_status":"active","legal_dossier_reopened":False})
        self.write_json(root/"quality1000-rework"/str(sku)/digest/"prior-base.json",{
            "schema":"saeit.mpw.three-retail-artifact-qa1000-rework.v1","product_id":sku,
            "source_file_sha256":digest,"legal_dossier_status":"owner_confirmed_complete",
            "legal_execution_status":"active","legal_dossier_reopened":False})
        self.write_json(root/"quality1000-rework"/str(sku)/digest/"historical-legal-state.json",{
            "schema":"saeit.mpw.three-retail-artifact-qa1000-rework.v1","product_id":sku,
            "source_file_sha256":digest,"legal_dossier_status":"pending",
            "legal_execution_status":"pending","legal_dossier_reopened":False})
        measured={"checks":{"reader_opened":True,"all_pdf_pages_rendered":not failed},
            "visual_render":{"rendered_page_count":415,"page_count_matches":True,
                "render_failure":None,"near_blank_page_numbers":[],"pages_with_color_signal":403}}
        report={"schema":"saeit.mpw.private-content-audit.v1","sku":sku,"source_sha256":digest,
            "professional_quality_score":None,"quality1000_verified":False,"measured_artifact":{**measured,"sha256":digest}}
        self.write_json(root/"quality1000-rework"/str(sku)/digest/"content-audits"/"audit.json",report)
        second_report=json.loads(json.dumps(report))
        second_report["measured_artifact"]["visual_render"]["pages_with_color_signal"]=402
        self.write_json(root/"quality1000-rework"/str(sku)/digest/"content-audits"/"prior-audit.json",second_report)
        return digest

    def test_advances_only_source_bound_mechanical_stage_and_keeps_quality_uncertified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            digest=self.seed(root)
            result=progress.verified_progress(root,72)
            self.assertEqual(result["source_sha256"],digest)
            self.assertEqual(result["mechanical_stage"],"FULL_PDF_RENDER_AND_MECHANICAL_CHECKS_PASSED")
            self.assertFalse(result["quality1000_verified"])
            folder=root/"quality1000-rework"/"72"/digest/"progress"
            saved=json.loads(next(folder.glob("*.json")).read_text())
            self.assertEqual(saved["legal_dossier_status"],"owner_confirmed_complete")
            self.assertFalse(saved["legal_dossier_reopened"])
            self.assertFalse(saved["commercial_release_allowed"])
            self.assertEqual(len(saved["base_rework_ticket_sha256s"]),2)
            self.assertEqual(len(saved["technical_audit_sha256s"]),2)

    def test_website_kit_progress_requires_browser_review_not_gameplay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.seed(root,sku=879)
            result=progress.verified_progress(root,879)
            self.assertEqual(result["mechanical_stage"],"ZIP_INTEGRITY_AND_STATIC_ACCESSIBILITY_CHECKS_PASSED")
            folder=root/"quality1000-rework"/"879"/result["source_sha256"]/"progress"
            saved=json.loads(next(folder.glob("*.json")).read_text())
            self.assertIn("website-kit",saved["next_private_operation"])
            self.assertNotIn("gameplay",saved["next_private_operation"])
            self.assertFalse(saved["commercial_release_allowed"])

    def test_rejects_failed_mechanical_gate_without_advancing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            digest=self.seed(root,failed=True)
            with self.assertRaisesRegex(RuntimeError,"PRIVATE_QA_NO_PASSING_AUDIT_FOR_SOURCE_HASH"):
                progress.verified_progress(root,72)
            progress_dir=root/"quality1000-rework"/"72"/digest/"progress"
            self.assertFalse(progress_dir.exists())

    def test_v2_candidate_requires_exact_zip_and_independent_twelve_view_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_sha = hashlib.sha256(b"original-private").hexdigest()
            blob = root / "private.zip"
            with zipfile.ZipFile(blob, "w") as archive:
                archive.writestr("index.html", "<html><title>Responsive</title></html>")
            candidate_bytes = blob.read_bytes()
            candidate_sha = hashlib.sha256(candidate_bytes).hexdigest()
            folder = root / "quality1000-rework" / "879" / source_sha / "mobile-candidates"
            folder.mkdir(parents=True)
            (folder / (candidate_sha + ".zip")).write_bytes(candidate_bytes)
            self.assertIsNone(progress.candidate_browser_evidence(root, source_sha, candidate_sha))
            payload = {
                "schema": progress.CANDIDATE_12VIEW_SCHEMA,
                "source_sha256": source_sha,
                "candidate_sha256": candidate_sha,
                "quality1000_verified": False,
                "commercial_release_allowed": False,
                "live_product_modified": False,
                "browser_and_accessibility_smoke_passed": True,
                "checks": {"gate_%02d" % i: True for i in range(13)},
                "viewports": [{"size":[320+i*10,720]} for i in range(12)],
            }
            raw = (json.dumps(payload,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode()
            name = hashlib.sha256(raw).hexdigest() + ".json"
            target = folder / "browser-audits" / candidate_sha / name
            target.parent.mkdir(parents=True)
            target.write_bytes(raw)
            result = progress.candidate_browser_evidence(root, source_sha, candidate_sha)
            self.assertEqual(result["real_browser_viewports_passed"],12)
            self.assertEqual(result["candidate_sha256"],candidate_sha)
            self.assertFalse(result["quality1000_verified"])
            (folder / (candidate_sha + ".zip")).write_bytes(b"tampered")
            with self.assertRaisesRegex(RuntimeError,"PRIVATE_QA_CANDIDATE_HASH_MISMATCH"):
                progress.candidate_browser_evidence(root, source_sha, candidate_sha)

if __name__=="__main__":
    unittest.main()
