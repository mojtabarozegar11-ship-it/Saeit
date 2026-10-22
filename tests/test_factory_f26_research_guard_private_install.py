"""Private admission must accept string CLI paths and reject tampered ONNX bytes."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

SRC=Path(__file__).resolve().parents[1]/"deploy"/"factory_f26_research_guard_private_install.py"
spec=importlib.util.spec_from_file_location("f26_guard_install",str(SRC))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
h=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()

class GuardAdmission(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.base=self.root/"f26-real-data-research"
        self.base.mkdir()
        self.previous="39737218790-1"
        self.run="39740000001-1"
        self.model=self.base/self.previous
        self.portable=self.base/("portable-"+self.previous)
        self.stage=self.base/(".incoming-guard-"+self.run)
        for p in (self.model,self.portable,self.stage):
            p.mkdir()
        (self.model/"rice_cultivar_real_pilot.onnx").write_bytes(b"genuine model proof bytes")
        self.sha=h(self.model/"rice_cultivar_real_pilot.onnx")
        self.dataset_sha="b"*64
        self._j(self.model/"model_card.json",{
            "onnx_model_sha256":self.sha,
            "dataset":{"download_archive_sha256":self.dataset_sha},
            "quality_1000_certified":False})
        self._j(self.model/"private-f26-real-data-receipt.json",{
            "schema":"saeit.factory.f26.real-rice-research-pilot.v1.vps-admission",
            "run_id":self.previous,
            "research_model_sha256":self.sha,
            "commercial_release_allowed":False,
            "professional_quality_1000_certified":False,
            "previous_f26_native_48_models_preserved":True})
        (self.portable/"portable-spec.json").write_text(json.dumps({
            "model_sha256":self.sha}))
        codes={}
        for name in ("factory_f26_rice_onnx_portable.py","factory_f26_real_rice_cli.py"):
            f=self.portable/name
            f.write_text("print('private audited original')\n")
            codes[name]=h(f)
        self._j(self.portable/"private-portable-deployment-receipt.json",{
            "schema":"saeit.factory.f26.portable-private-admission.v1",
            "source_run":self.previous,
            "real_model_sha256":self.sha,
            "quality_1000_certified":False,
            "commercial_release":False,
            "public_site_changes":0,
            "portable_source_sha256":codes})
        self._j(self.stage/"guard-spec.json",{
            "schema":m.SCHEMA,"family":"F26",
            "research_only":True,"commercial_release_authorized":False,
            "quality_1000_certified":False,"independent_field_validated":False,
            "domain_bounds_derived_from_training_only":True,
            "heldout_test_not_used_to_tune_bounds":True,
            "raw_image_input_supported":False,
            "source_test_count":762,
            "holdout":{"samples":762},
            "model_onnx_sha256":self.sha,
            "source_dataset_sha256":self.dataset_sha,
            "portable_spec_sha256":h(self.portable/"portable-spec.json")})
        (self.stage/"rice-samples.csv").write_text("row,safe\n1,1\n")
        (self.stage/"factory_f26_rice_research_guard.py").write_text(
            "# guard functional test mock, all admission byte checks real\n")
        self.manifest={
            name:h(self.stage/name) for name in m.FILES}
        self._j(self.stage/"hash-manifest.json",self.manifest)
    @staticmethod
    def _j(path,value):
        path.write_text(json.dumps(value,sort_keys=True)+"\n")

    def test_manifest_string_path_is_accepted(self):
        self.assertEqual(m.document(str(self.stage/"hash-manifest.json")),
                         self.manifest)

    def test_original_onnx_tampering_rejected_before_write(self):
        self.assertEqual(m.locate(self.root, m.document(self.stage/"guard-spec.json"))[0],
                         self.previous)
        (self.model/"rice_cultivar_real_pilot.onnx").write_text("tampered model")
        with self.assertRaisesRegex(RuntimeError,"NO_MODEL_AND_RUNTIME_SAME_PROVENANCE"):
            m.locate(self.root, m.document(self.stage/"guard-spec.json"))
        self.assertFalse((self.base/("guard-"+self.run)).exists())

    def test_private_guard_full_admission_receipt_and_no_site_writes(self):
        def real_runner(command,**_):
            out=Path(command[-1])
            if "private-unfamiliar" in str(out):
                data={"schema":m.SCHEMA+".private-inference",
                      "rows":1,"abstentions":1,
                      "predictions":[{"research_prediction":None,
                            "abstention_reasons":["outside_training_distribution"]}]}
            else:
                data={"schema":m.SCHEMA+".private-inference",
                      "rows":12,"abstentions":2,
                      "quality_1000_certified":False,
                      "commercial_release_authorized":False,
                      "original_model_sha256":self.sha,
                      "guard_spec_sha256":self.manifest["guard-spec.json"]}
            self._j(out,data)
            return SimpleNamespace(returncode=0,stdout="F26_GUARDED_OFFLINE_PREDICTIONS=PASS",stderr="")
        with patch.object(m.subprocess,"run",side_effect=real_runner):
            m.install(self.root,self.run,str(self.stage/"hash-manifest.json"),"a"*40)
        final=self.base/("guard-"+self.run)
        d=m.document(final/"private-domain-guard-receipt.json")
        self.assertEqual(d["real_uci_grains_trialled"],12)
        self.assertTrue(d["unfamiliar_input_abstained"])
        self.assertEqual(d["previous_research_run"],self.previous)
        self.assertFalse(d["commercial_release_authorized"])
        self.assertEqual(d["public_site_changes"],0)
        self.assertTrue((self.model/"rice_cultivar_real_pilot.onnx").is_file())
        with self.assertRaisesRegex(RuntimeError,"STAGE_EXISTS_OR_UNSAFE"):
            m.install(self.root,self.run,str(final/"hash-manifest.json"),"a"*40)

if __name__=="__main__":
    unittest.main()
