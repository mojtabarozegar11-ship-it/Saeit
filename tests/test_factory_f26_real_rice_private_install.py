"""Only byte-verified real-data F26 research evidence reaches private VPS."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

SPEC=importlib.util.spec_from_file_location(
    "f26_research_admission",
    Path(__file__).resolve().parents[1]/"deploy"/"factory_f26_real_rice_private_install.py")
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def sample_docs():
    model=b"\x08\x09\x12\x06F26onnx-test-model-payload"
    card={
      "schema":"saeit.factory.f26.real-rice-research-pilot.v1",
      "family":"F26",
      "dataset":{"doi":"https://doi.org/10.24432/C5MW4Z",
          "license":"Creative Commons Attribution 4.0 International (CC BY 4.0)",
          "download_archive_sha256":"e"*64},
      "onnx_model_sha256":sha(model),
      "research_only":True,
      "independent_field_validation":False,
      "independent_specialist_approval":False,
      "quality_1000_certified":False,
      "commercial_release_authorized":False,
      "metrics":{"dataset_raw_count":3810,"heldout_rows":762,
                 "heldout_balanced_accuracy":0.92573,
                 "onnx_vs_sklearn_label_mismatch_count":0}
    }
    files={"rice_cultivar_real_pilot.onnx":model,
           "model_card.json":json.dumps(card).encode(),
           "ATTRIBUTION_AND_LIMITS.txt":b"Real UCI rice CC BY 4.0 source attribution research pilot.\n"}
    manifest={
        "schema":"saeit.factory.f26.real-rice-research-pilot.v1.artifact-manifest",
        "source_archive_sha256":"e"*64,
        "artifact_sha256":{k:sha(v) for k,v in files.items()},
        "holdout_data_real_and_not_synthetic":True,
        "source_verified_by_pinned_sha256":True,
        "quality_1000_certified":False,
        "commercial_release_authorized":False}
    files["manifest.json"]=json.dumps(manifest).encode()
    return files

class F26PrivateAdmissionTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        nat=self.root/"native-candidate-evidence"/"39723793879-1"
        nat.mkdir(parents=True)
        a={
           "schema":"saeit.factory.native-six-vps-aggregate.v1",
           "six_families_verified":6,
           "candidate_native_file_count":56,
           "private_only":True,
           "production_release_authorized":False,
           "files":[{"family":"F26","native_candidate_files":48,
                     "verified_on_vps":True,"archive_sha256":"a"*64}]}
        aggregate=json.dumps(a).encode()
        (nat/"verified-six-private-native.json").write_bytes(aggregate)
        review=self.root/"quality-excellence"/"six-native-rework"/nat.name
        review.mkdir(parents=True)
        (review/"review.json").write_text(json.dumps({
             "source_aggregate_sha256":sha(aggregate),
             "completed_professional_quality_1000_certifications":0}))
        area=self.root/"f26-real-data-research"
        area.mkdir()
        self.run_id="39728000000-1"
        self.stage=area/(".incoming-"+self.run_id)
        self.stage.mkdir()
    def build(self,files):
        out=io.BytesIO()
        with tarfile.open(fileobj=out,mode="w") as tar:
            for name,blob in files.items():
                spec=tarfile.TarInfo(name)
                spec.size=len(blob)
                tar.addfile(spec,io.BytesIO(blob))
        content=out.getvalue()
        (self.stage/"f26-research.tar").write_bytes(content)
        return sha(content)

    def test_actual_source_chain_and_private_no_sale_receipt(self):
        digest=self.build(sample_docs())
        module.run(self.root,self.run_id,"f"*40,digest)
        target=self.root/"f26-real-data-research"/self.run_id
        self.assertTrue(target.is_dir())
        report=json.loads((target/"private-f26-real-data-receipt.json").read_text())
        self.assertEqual(report["real_world_rice_rows"],3810)
        self.assertEqual(report["previous_f26_native_48_models_preserved"],True)
        self.assertEqual(report["prior_native_f26_archive_sha256"],"a"*64)
        self.assertFalse(report["commercial_release_allowed"])
        self.assertFalse(report["professional_quality_1000_certified"])

    def test_reject_owner_or_expert_certification_self_claim(self):
        files=sample_docs()
        card=json.loads(files["model_card.json"].decode())
        card["independent_specialist_approval"]=True
        files["model_card.json"]=json.dumps(card).encode()
        manifest=json.loads(files["manifest.json"].decode())
        manifest["artifact_sha256"]["model_card.json"]=sha(files["model_card.json"])
        files["manifest.json"]=json.dumps(manifest).encode()
        digest=self.build(files)
        with self.assertRaisesRegex(RuntimeError,"INCOMPLETE_FIELD_OR_HOLDOUT_EVIDENCE"):
            module.run(self.root,self.run_id,"f"*40,digest)
        self.assertFalse((self.root/"f26-real-data-research"/self.run_id).exists())

    def test_reject_changed_archive_digest(self):
        self.build(sample_docs())
        with self.assertRaisesRegex(RuntimeError,"TAR_MISMATCH"):
            module.run(self.root,self.run_id,"f"*40,"0"*64)

    def test_missing_prior_independent_vps_batch_not_accepted(self):
        self.build(sample_docs())
        (self.root/"native-candidate-evidence"/"39723793879-1"/"verified-six-private-native.json").unlink()
        digest=sha((self.stage/"f26-research.tar").read_bytes())
        with self.assertRaisesRegex(RuntimeError,"NO_VALID_INDEPENDENT_NATIVE_SOURCE"):
            module.run(self.root,self.run_id,"f"*40,digest)

if __name__=="__main__":
    unittest.main()
