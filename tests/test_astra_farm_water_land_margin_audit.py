"""Third specialist product independent math, safety and UI/output QA."""
from copy import deepcopy
from decimal import Decimal as D
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"product_prototypes"/"farm_water_land_margin_audit"
spec=importlib.util.spec_from_file_location("astra_lp_engine_tests",P/"water_margin_audit.py")
eng=importlib.util.module_from_spec(spec);spec.loader.exec_module(eng)
spec=importlib.util.spec_from_file_location("astra_lp_report_tests",P/"render_report.py")
render=importlib.util.module_from_spec(spec);spec.loader.exec_module(render)


def sample():
    return json.loads((P/"example_synthetic.json").read_text(encoding="utf-8"))


def simple():
    p=sample()
    p["land_hectares"]="4";p["water_m3_available"]="10";p["drought_water_fraction"]="0.5"
    p["crops"]=p["crops"][:2]
    a,b=p["crops"]
    a.update(max_hectares="4",water_m3_per_hectare="5",revenue_per_hectare="12",variable_cost_per_hectare="4")
    b.update(max_hectares="4",water_m3_per_hectare="1",revenue_per_hectare="9",variable_cost_per_hectare="4")
    return p


class WaterLandAuditTests(unittest.TestCase):
    def test_two_constraint_vertex_solution_by_hand(self):
        result=eng.audit(simple())["baseline"]
        self.assertEqual([r["hectares"] for r in result["allocation"]],["1.5000","2.5000"])
        self.assertEqual(result["total_gross_margin"],"24.50")
        self.assertEqual(result["water_m3_used"],"10.00")
        self.assertEqual(result["allocated_land_hectares"],"4.0000")
        self.assertTrue(result["optimal_for_given_linear_model"])

    def test_drought_economic_loss_and_reallocation(self):
        report=eng.audit(simple())
        self.assertEqual(report["water_scarcity"]["total_gross_margin"],"20.75")
        self.assertEqual(report["hypothetical_gross_margin_loss_under_water_scarcity"],"3.75")
        self.assertEqual([r["hectares"] for r in report["water_scarcity"]["allocation"]],
                         ["0.2500","3.7500"])

    def test_less_water_never_increases_optimal_objective_with_same_inputs(self):
        x=eng.audit(sample())
        self.assertGreaterEqual(D(x["baseline"]["total_gross_margin"]),
                                D(x["water_scarcity"]["total_gross_margin"]))
        self.assertEqual(x["currency"],"USD")
        self.assertFalse(x["sale_ready"])
        self.assertFalse(x["sources_independently_verified"])

    def test_all_negative_margins_means_no_planting(self):
        p=sample()
        for c in p["crops"]:
            c["revenue_per_hectare"]="5"
            c["variable_cost_per_hectare"]="100"
        r=eng.audit(p)["baseline"]
        self.assertEqual(r["total_gross_margin"],"0.00")
        self.assertTrue(all(q["hectares"]=="0.0000" for q in r["allocation"]))

    def test_no_water_means_no_planting_for_positive_water_requirements(self):
        p=sample();p["water_m3_available"]="0"
        r=eng.audit(p)["baseline"]
        self.assertEqual(r["water_m3_used"],"0.00")
        self.assertEqual(r["total_gross_margin"],"0.00")

    def test_zero_drought_water_is_handled_without_zero_division(self):
        p=sample();p["drought_water_fraction"]="0"
        r=eng.audit(p)["water_scarcity"]
        self.assertEqual(r["total_gross_margin"],"0.00")

    def test_independent_coarse_brute_grid_never_exceeds_solver(self):
        s=simple()
        optimum=D(eng.audit(s)["baseline"]["total_gross_margin"])
        brute=D(0)
        for ia,ib in itertools.product(range(9),repeat=2):
            a=D(ia)/2;b=D(ib)/2
            if a+b<=4 and 5*a+b<=10:
                brute=max(brute,8*a+5*b)
        self.assertGreaterEqual(optimum,brute)

    def test_one_crop_cap_zero_other_cap_valid(self):
        p=simple()
        p["crops"][0]["max_hectares"]="0"
        r=eng.audit(p)["baseline"]
        self.assertEqual(r["allocation"][0]["hectares"],"0.0000")
        self.assertEqual(r["allocation"][1]["hectares"],"4.0000")

    def test_validation_rejects_float_bool_nan_negative(self):
        bad=("NaN","Infinity","-1",True,1.0)
        for value in bad:
            with self.subTest(value=value):
                p=sample();p["crops"][0]["water_m3_per_hectare"]=value
                with self.assertRaises(eng.ModelInputError):eng.audit(p)

    def test_unknown_schema_duplicate_crop_and_invalid_area_blocked(self):
        p=sample();p["whatever"]=999
        with self.assertRaises(eng.ModelInputError):eng.audit(p)
        p=sample();p["crops"][1]["name"]=p["crops"][0]["name"]
        with self.assertRaises(eng.ModelInputError):eng.audit(p)
        p=sample();p["land_hectares"]="0"
        with self.assertRaises(eng.ModelInputError):eng.audit(p)

    def test_unsupported_source_status_rejected(self):
        p=sample();p["crops"][0]["source_status"]="verified by model"
        with self.assertRaises(eng.ModelInputError):eng.audit(p)

    def test_missing_evidence_warnings_preserve_false_review(self):
        p=sample();p["crops"][0]["source_reference"]=""
        r=eng.audit(p)
        self.assertIn("INPUT_SOURCE_MISSING:"+p["crops"][0]["name"],r["warnings"])
        self.assertFalse(r["market_demand_verified"])
        self.assertFalse(r["store_publication_authorized"])
        self.assertIsNone(r["quality_score"])

    def test_report_escaping_and_malicious_crop_name(self):
        p=sample();p["crops"][0]["name"]="<script>alert(1)</script>"
        html=render.render(eng.audit(p))
        self.assertNotIn("<script>alert(1)</script>",html)
        self.assertIn("&lt;script&gt;",html)
        self.assertIn("Not a certified",html)

    def test_html_refuses_external_fabricated_release_claim(self):
        doc=eng.audit(sample());doc["sale_ready"]=True
        with self.assertRaises(ValueError):render.render(doc)

    def test_zero_third_crop_has_deterministic_tie(self):
        s=sample();s["crops"][2]["max_hectares"]="0"
        a=eng.audit(s);b=eng.audit(deepcopy(s))
        self.assertEqual(a,b)
        self.assertEqual(len(a["input_sha256"]),64)
        self.assertEqual(a["baseline"]["allocation"][2]["hectares"],"0.0000")

    def test_cli_and_printout_are_private_files_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);src=p/"in.json";dest=p/"out.json";html=p/"out.html"
            src.write_text(json.dumps(sample()))
            first=subprocess.run([sys.executable,str(P/"water_margin_audit.py"),
                "--input",str(src),"--output",str(dest)],capture_output=True,text=True,timeout=10)
            self.assertEqual(first.returncode,0,first.stderr)
            self.assertEqual(dest.stat().st_mode&0o777,0o600)
            again=subprocess.run([sys.executable,str(P/"water_margin_audit.py"),
                "--input",str(src),"--output",str(dest)],capture_output=True,timeout=10)
            self.assertNotEqual(again.returncode,0)
            proc=subprocess.run([sys.executable,str(P/"render_report.py"),
                "--report",str(dest),"--html",str(html)],capture_output=True,text=True,timeout=10)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertEqual(html.stat().st_mode&0o777,0o600)

    def test_independent_zip_self_test(self):
        proc=subprocess.run([sys.executable,str(P/"self_test.py")],
                            capture_output=True,text=True,timeout=10)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertIn("ASTRA_WATER_LAND_INDEPENDENT_SELF_TEST=PASS",proc.stdout)


if __name__=="__main__":
    unittest.main()
