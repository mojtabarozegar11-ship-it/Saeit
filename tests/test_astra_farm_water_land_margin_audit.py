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

    def test_water_frontier_exact_hand_calculation_and_intervals(self):
        report = eng.audit(simple())
        frontier = report["water_sensitivity_frontier"]
        self.assertEqual(len(frontier), 5)
        self.assertEqual([x["water_budget_m3"] for x in frontier],
                         ["0.00", "2.50", "5.00", "7.50", "10.00"])
        self.assertEqual([x["optimal_gross_margin"] for x in frontier],
                         ["0.00", "12.50", "20.75", "22.63", "24.50"])
        self.assertEqual(
            [x["average_incremental_gross_margin_per_m3"] for x in frontier],
            [None, "5.000000", "3.300000", "0.750000", "0.750000"])
        self.assertEqual(frontier[-1]["optimal_gross_margin"],
                         report["baseline"]["total_gross_margin"])
        self.assertEqual(frontier[0]["added_water_allowance_m3"], None)
        self.assertTrue(all(x["market_water_price_or_dual_shadow_price"] is None
                            and x["farm_result_verified"] is False
                            for x in frontier))

    def test_frontier_monotonic_margins_and_diminishing_interval_gains(self):
        for p in (sample(), simple()):
            frontier = eng.audit(p)["water_sensitivity_frontier"]
            amounts = [D(row["optimal_gross_margin"]) for row in frontier]
            self.assertTrue(all(b >= a for a, b in zip(amounts, amounts[1:])))
            slopes = [D(row["average_incremental_gross_margin_per_m3"])
                      for row in frontier[1:]]
            self.assertTrue(all(b <= a + D("0.000002")
                                for a, b in zip(slopes, slopes[1:])))

    def test_zero_available_water_has_undefined_interval_value(self):
        payload = sample()
        payload["water_m3_available"] = "0"
        frontier = eng.audit(payload)["water_sensitivity_frontier"]
        self.assertEqual(len(frontier), 5)
        self.assertTrue(all(x["optimal_gross_margin"] == "0.00"
                            and x["average_incremental_gross_margin_per_m3"] is None
                            for x in frontier))

    def test_report_rejects_market_value_promotion(self):
        doc = eng.audit(sample())
        doc["water_sensitivity_frontier"][1][
            "market_water_price_or_dual_shadow_price"] = "1234.00"
        with self.assertRaisesRegex(ValueError, "cannot claim verification"):
            render.render(doc)

    def test_report_explains_interval_not_market_water_price(self):
        report = eng.audit(sample())
        html = render.render(report)
        self.assertIn("Water allowance sensitivity", html)
        self.assertIn("NOT a market water price", html)
        self.assertIn(
            "SENSITIVITY_INTERVAL_AVERAGE_NOT_MARKET_PRICE_OR_INSTANTANEOUS_DUAL",
            report["warnings"])

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
