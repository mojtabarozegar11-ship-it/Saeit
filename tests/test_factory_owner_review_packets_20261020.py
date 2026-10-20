"""Review packet intake is genuine, private and never grants publication."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts/factory_owner_review_packets_20261020.py"
spec = importlib.util.spec_from_file_location("owner_review_packets",PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ReviewPacketTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.orders = self.root/"production-instructions"/"orders"
        self.orders.mkdir(parents=True)
        self.orders.joinpath("WO-00000001.json").write_text(json.dumps({
            "id":"WO-00000001","status":"issued","phase":"engineering_specification",
            "origin":"factory_invention","subject":"Original offline worksheet"
        }))
        self.orders.joinpath("WO-00000002.json").write_text(json.dumps({
            "id":"WO-00000002","status":"issued","phase":"research_rework",
            "origin":"local-factory-research","blocker":"real evidence needed"
        }))

    def test_generated_private_review_is_not_a_passport_or_an_approval(self):
        report = m.build(self.root)
        self.assertEqual(report["counts"]["manufacturing_orders"],1)
        self.assertEqual(report["counts"]["research_waiting_for_real_evidence"],1)
        self.assertEqual(report["counts"]["missing_passport"],1)
        self.assertEqual(report["counts"]["new_private_packets"],1)
        self.assertEqual(report["products_activated"],0)
        self.assertEqual(report["sites_contacted"],0)
        queue=self.root/"product-lifecycle"/"owner-review-queue"
        candidates=list(queue.rglob("WO-00000001/*.json"))
        self.assertEqual(len(candidates),1)
        packet=json.loads(candidates[0].read_text())
        self.assertEqual(packet["schema"],m.SCHEMA)
        self.assertIn("independent_reviewer_id",packet["passport_fields_missing"])
        self.assertFalse(packet["commercial_release"])
        self.assertFalse(packet["manufacturing_approval"])
        self.assertFalse(packet["store_publication"])
        self.assertFalse((self.root/"product-lifecycle"/"passports").exists())
        self.assertEqual(candidates[0].stat().st_mode & 0o777,0o600)
        self.assertEqual(m.build(self.root)["counts"].get("new_private_packets",0),0)

    def test_real_zip_sha_and_oversized_entry_count_are_not_falsely_certified(self):
        import hashlib
        import zipfile
        for name,n in (("good_product",1),("bad_product",81)):
            folder=self.root/"digital-products"/name
            folder.mkdir(parents=True)
            z=folder/(name+"-internal-qa.zip")
            with zipfile.ZipFile(z,"w",zipfile.ZIP_DEFLATED) as pack:
                for i in range(n):
                    pack.writestr(name+"/item"+str(i)+".txt","real QA data")
            archive_sha=hashlib.sha256(z.read_bytes()).hexdigest()
            (folder/"manufacturing_manifest.json").write_text(json.dumps({
                "recipe":name,"qa_status":"passed","source_sha256":"a"*64,
                "artifact_sha256":archive_sha}))
        result=m.build(self.root)
        self.assertEqual(result["technical_readiness"]["goods_inspected"],2)
        self.assertEqual(result["technical_readiness"]["technically_verified"],1)
        self.assertEqual(result["technical_readiness"]["technical_rework_required"],1)
        dashboard=json.loads((self.root/"product-lifecycle"/"product-technical-readiness"/"dashboard.json").read_text())
        by_id={item["recipe"]:item for item in dashboard["items"]}
        self.assertTrue(by_id["good_product"]["technical_ok"])
        self.assertIn("ARCHIVE_LIMIT",by_id["bad_product"]["blockers"])
        self.assertEqual(dashboard["commercial_approval_count"],0)
        self.assertFalse((self.root/"product-lifecycle"/"passports").exists())
        self.assertEqual(m.build(self.root)["technical_readiness"]["goods_inspected"],2)

    def test_exact_f34_exception_requires_proven_verified_100_files(self):
        import hashlib
        import zipfile
        recipe="fieldwork_ui_48_icons"
        folder=self.root/"digital-products"/recipe
        folder.mkdir(parents=True)
        filenames=([f"icons/icon_{i:02d}.svg" for i in range(48)]
                   +[f"icons/icon_{i:02d}.png" for i in range(48)]
                   +["README.md","LICENSE.txt","catalog.json","preview.html"])
        archive=folder/(recipe+"-internal-qa.zip")
        with zipfile.ZipFile(archive,"w") as pack:
            for name in filenames:pack.writestr(recipe+"/"+name,"real bytes")
        sha=hashlib.sha256(archive.read_bytes()).hexdigest()
        checks={"gate"+str(i):True for i in range(10)}
        manifest={"recipe":recipe,"qa_status":"passed","family_id":"F34",
          "source_sha256":"a"*64,"artifact_sha256":sha,"files":filenames,
          "qa_measurements":{"review_kind":"separate_automated_technical_verification",
            "validated_archive_members":100,"archive_sha256":sha,
            "critical_defects":[],"gates":checks}}
        meta=folder/"manufacturing_manifest.json"
        meta.write_text(json.dumps(manifest))
        self.assertEqual(m.build(self.root)["technical_readiness"]["technically_verified"],1)
        manifest["qa_measurements"]["gates"]["gate0"]=False
        meta.write_text(json.dumps(manifest))
        self.assertEqual(m.build(self.root)["technical_readiness"]["technical_rework_required"],1)
        dashboard=json.loads((self.root/"product-lifecycle"/"product-technical-readiness"/"dashboard.json").read_text())
        self.assertIn("F34_EXACT_EVIDENCE_INVALID",dashboard["items"][0]["blockers"])

    def test_hash_tamper_is_blocked_without_approving_good_qa(self):
        import hashlib
        import zipfile
        name="tampered_product"
        folder=self.root/"digital-products"/name
        folder.mkdir(parents=True)
        z=folder/(name+"-internal-qa.zip")
        with zipfile.ZipFile(z,"w") as pack:
            pack.writestr(name+"/readme.txt","local source")
        (folder/"manufacturing_manifest.json").write_text(json.dumps({
            "recipe":name,"qa_status":"passed","source_sha256":"a"*64,
            "artifact_sha256":"f"*64}))
        result=m.build(self.root)
        dashboard=json.loads((self.root/"product-lifecycle"/"product-technical-readiness"/"dashboard.json").read_text())
        self.assertEqual(result["technical_readiness"]["technical_rework_required"],1)
        self.assertIn("ARTIFACT_HASH_MISMATCH",dashboard["items"][0]["blockers"])

    def test_invalid_order_and_symlink_are_refused(self):
        (self.orders/"WO-00000003.json").write_text(json.dumps({
            "id":"WO-00000004","status":"issued"
        }))
        with self.assertRaisesRegex(RuntimeError,"REVIEW_BAD_ORDER_PROVENANCE"):
            m.build(self.root)
        (self.orders/"WO-00000003.json").unlink()
        (self.orders/"extra.json").write_text("{}")
        with self.assertRaisesRegex(RuntimeError,"REVIEW_UNEXPECTED_ORDER_SOURCE"):
            m.build(self.root)

    def test_empty_existing_passport_never_grants_approval(self):
        path=self.root/"product-lifecycle"/"passports"
        path.mkdir(parents=True)
        (path/"WO-00000001.json").write_text(json.dumps({"work_order":"WO-00000001"}))
        result=m.build(self.root)
        self.assertEqual(result["counts"]["incomplete_passport"],1)
        self.assertEqual(result["approval_records_written"],0)
        self.assertEqual(result["products_activated"],0)

if __name__=="__main__":
    unittest.main()
