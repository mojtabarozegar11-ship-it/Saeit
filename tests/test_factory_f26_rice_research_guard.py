"""Guard declines unfamiliar grain measurements even when classifier confident."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

p=Path(__file__).resolve().parents[1]/"scripts"/"factory_f26_rice_research_guard.py"
s=importlib.util.spec_from_file_location("rice_guard_under_test",str(p))
g=importlib.util.module_from_spec(s)
s.loader.exec_module(g)

class RiceGuardRegression(unittest.TestCase):
    def test_training_only_quantiles(self):
        training=[[100+i,400+i/10,200+i/10,80+i/100,
                   0.8+i/10000,110+i,0.6+i/10000]
                  for i in range(400)]
        bounds=g.bounds(training)
        self.assertEqual(len(bounds),7)
        self.assertTrue(bounds[0]["min"]>100)
        self.assertTrue(bounds[0]["max"]<499)
        self.assertTrue(all(v["max"]>v["min"] for v in bounds))

    def test_confident_safe_vs_abstain_for_ood_and_uncertainty(self):
        x=[125,450,210,80,0.85,145,0.65]
        envelope=[{"min":100,"max":500},{"min":400,"max":600},
                  {"min":200,"max":300},{"min":70,"max":95},
                  {"min":0.7,"max":0.95},{"min":100,"max":550},
                  {"min":0.55,"max":0.8}]
        good=g.decision(x,0.92,envelope)
        self.assertTrue(good["accepted_for_research_only"])
        uncertain=g.decision(x,0.55,envelope)
        self.assertFalse(uncertain["accepted_for_research_only"])
        self.assertIn("model_probability_below_research_threshold",
                      uncertain["abstention_reasons"])
        x[0]=1_000_000
        ood=g.decision(x,0.98,envelope)
        self.assertFalse(ood["accepted_for_research_only"])
        self.assertEqual(ood["out_of_bounds_features"],["Area"])
        self.assertEqual(ood["abstention_reasons"],["outside_training_distribution"])

    def test_forged_model_hash_and_quality_policy_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            model=p/"model"
            model.mkdir()
            (model/"model_card.json").write_text(json.dumps({
                "dataset":{"download_archive_sha256":"a"*64},
                "onnx_model_sha256":"b"*64}))
            portable=p/"portable-spec.json"
            portable.write_text(json.dumps({"model_sha256":"b"*64}))
            guard={
                "schema":g.SCHEMA, "family":"F26","research_only":True,
                "quality_1000_certified":False,
                "independent_field_validated":False,
                "commercial_release_authorized":False,
                "source_dataset_sha256":"a"*64,
                "model_onnx_sha256":"b"*64,
                "portable_spec_sha256":hashlib.sha256(portable.read_bytes()).hexdigest(),
                "features":list(g.FIELDS),
                "min_model_confidence":0.80,
                "domain_bounds_derived_from_training_only":True,
                "heldout_test_not_used_to_tune_bounds":True,
                "raw_image_input_supported":False,
                "source_train_count":2000,
                "source_validation_count":700,
                "source_test_count":700,
                "feature_bounds":[{"min":0.1,"max":100} for _ in range(7)]}
            self.assertIs(g.verify(guard,model,portable),guard)
            guard["quality_1000_certified"]=True
            with self.assertRaisesRegex(ValueError,"UNVERIFIED_PROVENANCE"):
                g.verify(guard,model,portable)
            guard["quality_1000_certified"]=False
            guard["model_onnx_sha256"]="f"*64
            with self.assertRaisesRegex(ValueError,"UNVERIFIED_PROVENANCE"):
                g.verify(guard,model,portable)

if __name__=="__main__":
    unittest.main()
