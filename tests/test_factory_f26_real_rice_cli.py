import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location(
    "f26_rice_runtime",
    Path(__file__).resolve().parents[1]/"scripts"/"factory_f26_real_rice_cli.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

FEATURES=("14000","520","190","80","0.7","15000","0.6")

class RiceInferenceCLITests(unittest.TestCase):
    def test_real_morphology_finite_input_and_reject_negative(self):
        values=m.numbers(FEATURES)
        self.assertEqual(len(values),7)
        for index,bad in [(0,"NaN"),(0,"-1"),(4,"1.1"),(6,"0"),(1,"inf")]:
            row=list(FEATURES)
            row[index]=bad
            with self.assertRaises(ValueError):
                m.numbers(row)
        self.assertEqual(m.numbers(FEATURES)[0],14000.0)

    def test_reject_invalid_order_and_convex_area(self):
        row=list(FEATURES)
        row[2]="40"
        with self.assertRaisesRegex(ValueError,"MORPHOLOGY"):
            m.numbers(row)
        row=list(FEATURES)
        row[5]="12000"
        with self.assertRaisesRegex(ValueError,"MORPHOLOGY"):
            m.numbers(row)

    def test_read_csv_exact_schema_no_shortcuts(self):
        with tempfile.TemporaryDirectory() as folder:
            src=Path(folder)/"valid.csv"
            with src.open("w",encoding="utf8",newline="") as output:
                w=csv.writer(output)
                w.writerow(m.FIELDS)
                w.writerow(FEATURES)
            from types import SimpleNamespace
            args=SimpleNamespace(csv=str(src),features=None)
            self.assertEqual(len(m.read_cases(args)),1)
            src.write_text("Area,Perimeter\n1,2\n")
            with self.assertRaisesRegex(ValueError,"HEADER"):
                m.read_cases(args)
            src.write_text(",".join(m.FIELDS)+"\n"+"1,2,3,4,5,6,7\n")
            with self.assertRaisesRegex(ValueError,"MORPHOLOGY"):
                m.read_cases(args)

    def test_reject_fake_unsigned_research_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/"manifest.json").write_text(json.dumps({
                "schema":m.SCHEMA+".artifact-manifest",
                "family_id":"F26",
                "artifact_sha256":{
                    "rice_cultivar_real_pilot.onnx":"0"*64,
                    "model_card.json":"0"*64,
                    "ATTRIBUTION_AND_LIMITS.txt":"0"*64},
                "holdout_data_real_and_not_synthetic":True,
                "independent_specialist_approved":False,
                "quality_1000_certified":False,
                "commercial_release_authorized":False
            }))
            (root/"model_card.json").write_text(json.dumps({
                "schema":m.SCHEMA,
                "family":"F26",
                "research_only":False,
                "quality_1000_certified":True,
                "commercial_release_authorized":True
            }))
            with self.assertRaisesRegex(ValueError,"INVALID_RESEARCH_PROVENANCE"):
                m.verify_model(root)

if __name__=="__main__":
    unittest.main()
