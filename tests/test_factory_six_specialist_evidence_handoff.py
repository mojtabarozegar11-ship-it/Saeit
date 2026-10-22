"""Review handoff is real evidence routing, not forged third-party approval."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,str(path))
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

handoff=module(ROOT/"scripts"/"factory_six_specialist_evidence_handoff.py","handoff_under_test")
fixture=module(ROOT/"tests"/"test_factory_six_native_independent_rework.py","handoff_fixture")
review=module(ROOT/"scripts"/"factory_six_native_independent_rework.py","handoff_reviewer")

class SixSpecialistEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        fixture.fixtures(self.root,labelled_accessibility=True)
        review.run(self.root,"39714521227-1")
        self.f26=patch.object(handoff,"f26_real_pilot",return_value={
            "real_uci_pilot_independently_verified":True,
            "source_run":"39739940717-1",
            "receipt_sha256":"3"*64,
            "model_sha256":"4"*64,
            "dataset_source_sha256":"5"*64,
            "real_dataset_count":3810,
            "heldout_count":762,
            "independent_field_testing_complete":False,
            "commercial_release":False,"quality_1000_certified":False})
        self.f26.start()
        self.addCleanup(self.f26.stop)

    def test_exact_six_immutable_hash_bound_real_requests_no_forgery(self):
        manifest=handoff.build(self.root,ROOT/"scripts"/"factory_f26_real_rice_readonly_vps_proof.py")
        self.assertEqual(manifest["six_real_product_families_bound"],6)
        self.assertEqual(manifest["native_files_linked"],56)
        self.assertEqual(manifest["third_party_approved_families"],0)
        self.assertEqual(manifest["independent_quality_1000_certified_families"],0)
        self.assertFalse(manifest["commercial_release_allowed"])
        directory=self.root/"quality-excellence/six-expert-handoff/39714521227-1"
        self.assertEqual(len(list(directory.glob("F*.json"))),6)
        for name in handoff.FAMILIES:
            dossier=json.loads((directory/(name+".json")).read_text("utf8"))
            self.assertEqual(dossier["family"],name)
            self.assertEqual(len(dossier["external_review_protocols"]),3)
            self.assertEqual(len(dossier["required_signed_roles"]),4)
            self.assertEqual(dossier["trusted_human_reviewer_identities"],[])
            self.assertEqual(dossier["human_approvals"],[])
            self.assertFalse(dossier["physical_device_testing_verified"])
            self.assertFalse(dossier["independent_quality_1000_certified"])
            self.assertFalse(dossier["commercial_release_authorized"])
            self.assertEqual(
                handoff.sha_file(directory/(name+".json")),
                manifest["case_manifest_sha256"][name])
        again=handoff.build(self.root,ROOT/"scripts"/"factory_f26_real_rice_readonly_vps_proof.py")
        self.assertEqual(manifest,again)

    def test_tampered_native_archive_prevents_any_packet(self):
        source=self.root/"native-candidate-evidence/39714521227-1/F13/technical-native-candidate.zip"
        source.write_bytes(source.read_bytes()+b"spoof")
        with self.assertRaisesRegex(RuntimeError,"HANDOFF_NATIVE_ARTIFACT_CHANGED"):
            handoff.build(self.root,ROOT/"scripts"/"factory_f26_real_rice_readonly_vps_proof.py")
        self.assertFalse((self.root/"quality-excellence/six-expert-handoff").exists())

    def test_mismatched_or_forged_quality_receipt_fails_closed(self):
        path=self.root/"quality-excellence/six-native-rework/39714521227-1/F26.json"
        data=json.loads(path.read_text())
        data["quality_1000_certified"]=True
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(RuntimeError,"HANDOFF_FAMILY_IDENTITY_INTEGRITY_FAILED"):
            handoff.build(self.root,ROOT/"scripts"/"factory_f26_real_rice_readonly_vps_proof.py")

    def test_read_only_dry_run_no_private_files_created(self):
        result=handoff.build(self.root,ROOT/"scripts"/"factory_f26_real_rice_readonly_vps_proof.py",write=False)
        self.assertEqual(result["native_files_linked"],56)
        self.assertFalse((self.root/"quality-excellence/six-expert-handoff").exists())

if __name__=="__main__":
    unittest.main()
