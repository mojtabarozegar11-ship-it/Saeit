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

    def test_source_bound_passport_starter_retains_only_real_order_claims(self):
        report=m.build(self.root)
        starters=report["passport_starters"]
        self.assertEqual(len(starters),1)
        self.assertEqual(report["counts"]["new_private_passport_starters"],1)
        meta=starters[0]
        starter=self.root/"product-lifecycle"/"passport-starters"/meta["work_order"]/(meta["source_sha256"]+"-"+meta["starter_sha256"]+".json")
        data=json.loads(starter.read_text())
        self.assertEqual(data["schema"],"saeit.factory.passport-starter.v1")
        self.assertEqual(data["candidate_fields"]["title"]["value"],"Original offline worksheet")
        self.assertFalse(data["candidate_fields"]["title"]["independently_verified"])
        self.assertNotIn("asset_licenses",data["candidate_fields"])
        self.assertFalse(data["is_official_product_passport"])
        self.assertFalse(data["commercial_release"])
        self.assertFalse(data["human_review_signature_verified"])
        self.assertFalse((self.root/"product-lifecycle"/"passports").exists())
        self.assertEqual(starter.stat().st_mode&0o777,0o600)
        again=m.build(self.root)
        self.assertEqual(again["counts"].get("new_private_passport_starters",0),0)

    def test_current_source_bound_specialist_QA_is_actionable_but_never_approved(self):
        import hashlib
        wo="WO-00000001"
        source=self.orders/(wo+".json")
        order=json.loads(source.read_text())
        order.update(requesting_site="mojplaywin.com",source_product_id="original_python_product",
                     source_sha256="b"*64,source_artifact_sha256="c"*64)
        source.write_text(json.dumps(order))
        instruction_sha=hashlib.sha256(source.read_bytes()).hexdigest()
        qa={"schema":"saeit.factory.specialist-native-prescreen.v1",
            "source_sha256":"b"*64,"original_factory_artifact_sha256":"c"*64,
            "automated_format_prescreen_passed":False,
            "automated_technical_blockers":["MISSING_OR_UNSUPPORTED_FAMILY_PROVENANCE"],
            "commercial_release":False,"final_work_order_completed":False}
        qa_dir=self.root/"design-state/mojplaywin-native-specialist-evidence/original_python_product"
        qa_dir.mkdir(parents=True)
        data=(json.dumps(qa,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode()
        fingerprint=hashlib.sha256(data).hexdigest()
        (qa_dir/("b"*64+"-"+fingerprint+".json")).write_bytes(data)
        row={"schema":"saeit.factory.specialist-work-order-dossier.v1",
             "work_order":wo,"source_work_order_sha256":instruction_sha,
             "original_source_sha256":"b"*64,"source_artifact_sha256":"c"*64,
             "specialist_prescreen_sha256":fingerprint,
             "engineering_work_order_completed":False,"commercial_approval":False}
        side=self.root/"production-instructions/mojplaywin-specialist-order-reports"
        side.mkdir(parents=True)
        (side/(wo+"-"+fingerprint+".json")).write_text(json.dumps(row))
        result=m.build(self.root)
        self.assertEqual(result["counts"]["site_origin_specialist_qa_linked"],1)
        packet_path=self.root/"product-lifecycle/owner-review-queue"/wo
        packet=json.loads(next(packet_path.glob("*.json")).read_text())
        technical=packet["verified_private_technical_prescreen"]
        self.assertEqual(technical["status"],"authentic_automated_format_evidence_available")
        self.assertFalse(technical["format_prescreen_passed"])
        self.assertIn("MISSING_OR_UNSUPPORTED_FAMILY_PROVENANCE",technical["technical_blockers"])
        self.assertFalse(technical["expert_review_completed"])
        self.assertFalse(technical["rights_approved"])
        self.assertFalse(packet["commercial_release"])
        original=json.loads(source.read_text());original["subject"]="new revision of real order"
        source.write_text(json.dumps(original))
        stale=m.build(self.root)
        self.assertEqual(stale["counts"]["site_origin_specialist_qa_missing_or_stale"],1)
        new_packet=[json.loads(p.read_text()) for p in packet_path.glob("*.json")]
        self.assertTrue(any(p["verified_private_technical_prescreen"]["status"]==
                            "technical_specialist_evidence_missing_or_stale" for p in new_packet))

    def test_new_source_sha_bound_family_qa_supersedes_only_old_missing_family(self):
        import hashlib
        wo="WO-00000001"
        order={"requesting_site":"mojplaywin.com","source_product_id":"legacy_product","source_sha256":"b"*64,
               "source_artifact_sha256":"c"*64}
        root=self.root
        folder=root/"design-state/mojplaywin-native-specialist-evidence/legacy_product"
        folder.mkdir(parents=True)
        dossiers=root/"production-instructions/mojplaywin-specialist-order-reports"
        dossiers.mkdir(parents=True)
        work_order_sha="d"*64
        for restored in (False,True):
            data={"schema":"saeit.factory.specialist-native-prescreen.v1",
                  "source_sha256":order["source_sha256"],
                  "original_factory_artifact_sha256":order["source_artifact_sha256"],
                  "automated_format_prescreen_passed":restored,
                  "automated_technical_blockers":[] if restored else ["MISSING_OR_UNSUPPORTED_FAMILY_PROVENANCE"],
                  "commercial_release":False,"final_work_order_completed":False,
                  "family_id":"F20" if restored else None,
                  "family_provenance_source":("sha256_matched_original_manufacturing_qa" if restored else "not_verified"),
                  "family_provenance_receipt_sha256":"e"*64 if restored else None}
            contents=m.serialize(data)
            fingerprint=hashlib.sha256(contents).hexdigest()
            (folder/(order["source_sha256"]+"-"+fingerprint+".json")).write_bytes(contents)
            packet={"schema":"saeit.factory.specialist-work-order-dossier.v1",
                    "work_order":wo,"source_work_order_sha256":work_order_sha,
                    "original_source_sha256":order["source_sha256"],
                    "source_artifact_sha256":order["source_artifact_sha256"],
                    "specialist_prescreen_sha256":fingerprint,
                    "family_id":data["family_id"],
                    "engineering_work_order_completed":False,"commercial_approval":False}
            (dossiers/(wo+"-"+fingerprint+".json")).write_text(json.dumps(packet))
        chosen=m.linked_specialist_review(root,wo,order,work_order_sha)
        self.assertTrue(chosen["format_prescreen_passed"])
        self.assertTrue(chosen["source_original_provenance_restored"])
        self.assertFalse(chosen["rights_approved"])
        self.assertFalse(chosen["owner_release_approved"])

    def test_equivalent_immutable_qa_schema_upgrade_is_not_false_conflict(self):
        import hashlib
        wo="WO-00000001"
        order={"requesting_site":"mojplaywin.com","source_product_id":"existing_native",
               "source_sha256":"a"*64,"source_artifact_sha256":"b"*64}
        folder=self.root/"design-state/mojplaywin-native-specialist-evidence/existing_native"
        folder.mkdir(parents=True)
        records=self.root/"production-instructions/mojplaywin-specialist-order-reports"
        records.mkdir(parents=True)
        for modern in (False,True):
            proof={"schema":"saeit.factory.specialist-native-prescreen.v1",
                   "family_id":"F20","source_sha256":"a"*64,
                   "original_factory_artifact_sha256":"b"*64,
                   "automated_format_prescreen_passed":True,
                   "automated_technical_blockers":[],
                   "commercial_release":False,"final_work_order_completed":False}
            if modern:
                proof.update(family_provenance_source="warehouse_manifest",
                             family_provenance_receipt_sha256=None)
            raw=m.serialize(proof)
            fingerprint=hashlib.sha256(raw).hexdigest()
            (folder/("a"*64+"-"+fingerprint+".json")).write_bytes(raw)
            packet={"schema":"saeit.factory.specialist-work-order-dossier.v1",
                    "work_order":wo,"source_work_order_sha256":"d"*64,
                    "original_source_sha256":"a"*64,
                    "source_artifact_sha256":"b"*64,
                    "family_id":"F20","specialist_prescreen_sha256":fingerprint,
                    "engineering_work_order_completed":False,"commercial_approval":False}
            (records/(wo+"-"+fingerprint+".json")).write_text(json.dumps(packet))
        selected=m.linked_specialist_review(self.root,wo,order,"d"*64)
        self.assertTrue(selected["format_prescreen_passed"])
        self.assertTrue(selected["source_has_explicit_provenance_revision"])
        self.assertFalse(selected["owner_release_approved"])
        self.assertFalse(selected["rights_approved"])
        # A different family with equally green superficial status is a
        # genuine contradiction and cannot be reconciled by chronology.
        changed=dict(proof,family_id="F21")
        raw=m.serialize(changed)
        fingerprint=hashlib.sha256(raw).hexdigest()
        (folder/("a"*64+"-"+fingerprint+".json")).write_bytes(raw)
        packet=dict(packet,family_id="F21",specialist_prescreen_sha256=fingerprint)
        (records/(wo+"-"+fingerprint+".json")).write_text(json.dumps(packet))
        with self.assertRaisesRegex(RuntimeError,"OWNER_SPECIALIST_MULTIPLE_CURRENT_QA"):
            m.linked_specialist_review(self.root,wo,order,"d"*64)

    def test_invalid_forged_specialist_sidecar_is_refused(self):
        import hashlib
        wo="WO-00000001"
        p=self.orders/(wo+".json")
        order=json.loads(p.read_text())
        order.update(requesting_site="mojplaywin.com",source_product_id="original_python_product",
                     source_sha256="b"*64,source_artifact_sha256="c"*64)
        p.write_text(json.dumps(order))
        checksum=hashlib.sha256(p.read_bytes()).hexdigest()
        directory=self.root/"production-instructions/mojplaywin-specialist-order-reports"
        directory.mkdir(parents=True)
        (directory/(wo+"-"+"a"*64+".json")).write_text(json.dumps({
            "schema":"saeit.factory.specialist-work-order-dossier.v1",
            "work_order":wo,"source_work_order_sha256":checksum,
            "original_source_sha256":"b"*64,"source_artifact_sha256":"f"*64,
            "specialist_prescreen_sha256":"a"*64,
            "engineering_work_order_completed":False,"commercial_approval":False}))
        with self.assertRaisesRegex(RuntimeError,"OWNER_SPECIALIST_BAD_WORK_ORDER_EVIDENCE"):
            m.build(self.root)

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
