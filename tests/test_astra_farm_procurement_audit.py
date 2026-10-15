"""Procurement product tests; all vendor values are invented test fixtures."""
from copy import deepcopy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"product_prototypes"/"farm_procurement_audit"
spec=importlib.util.spec_from_file_location("farm_procurement_engine_qa",P/"procurement_audit.py")
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
spec=importlib.util.spec_from_file_location("farm_procurement_report_qa",P/"render_report.py")
printer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(printer)


def sample():
    return json.loads((P/"example_synthetic.json").read_text(encoding="utf-8"))


def offers(out,scenario="base"):
    return {o["supplier"]:o for o in out["scenarios"][scenario]["offers"]}


class ProcurementQuoteAuditTests(unittest.TestCase):
    def test_exact_landed_cost_and_net_quantity(self):
        p=sample();r=audit.evaluate(p);a=offers(r)["Synthetic Provider North"]
        with self.subTest("explicit discount and freight"):
            expected=(Decimal(100)/Decimal(".95"))*Decimal(5)*Decimal(".95")+Decimal(45)
            self.assertEqual(Decimal(a["total_landed_cost"]),expected.quantize(Decimal(".01")))
        self.assertEqual(r["scenarios"]["base"]["lowest_cost_eligible_supplier_under_inputs"],"Synthetic Provider North")
        self.assertEqual(a["landed_cost_per_net_required_unit"],audit.shown(expected/100))

    def test_late_cheapest_supplier_is_blocked(self):
        row=offers(audit.evaluate(sample()))["Synthetic Provider Late"]
        self.assertIn("DELIVERY_AFTER_DEADLINE",row["reasons"])
        self.assertFalse(row["eligible_for_cost_comparison"])
        self.assertFalse(row["verified_quote"])

    def test_below_capacity_and_minimum_order(self):
        p=sample()
        p["offers"][0]["minimum_order_units"]="180"
        p["offers"][0]["available_units"]="120"
        row=offers(audit.evaluate(p))["Synthetic Provider North"]
        self.assertEqual(row["gross_order_units"],"180.00")
        self.assertIn("INSUFFICIENT_DECLARED_CAPACITY",row["reasons"])

    def test_source_labels_absent_cannot_be_eligible(self):
        p=sample();p["offers"][0]["source_label"]=""
        row=offers(audit.evaluate(p))["Synthetic Provider North"]
        self.assertIn("QUOTE_PROVENANCE_MISSING",row["reasons"])

    def test_stress_increases_cost_explicitly(self):
        out=audit.evaluate(sample());b=offers(out,"base")["Synthetic Provider North"];a=offers(out,"adverse")["Synthetic Provider North"]
        self.assertGreater(Decimal(a["total_landed_cost"]),Decimal(b["total_landed_cost"]))
        self.assertEqual(out["scenarios"]["adverse"]["all_offers_ineligible"],False)

    def test_waste_over_100_percent_blocks_candidate_without_crash(self):
        p=sample();p["offers"][0]["waste_pct"]="99"
        p["stress_cases"]["adverse"]["waste_extra_pp"]="3"
        row=offers(audit.evaluate(p),"adverse")["Synthetic Provider North"]
        self.assertIn("WASTE_AT_OR_ABOVE_100_PERCENT",row["reasons"])
        self.assertIsNone(row["total_landed_cost"])

    def test_zero_eligible_has_no_supplier(self):
        p=sample();p["deadline_days"]=0
        out=audit.evaluate(p)
        self.assertTrue(out["scenarios"]["base"]["all_offers_ineligible"])
        self.assertIsNone(out["scenarios"]["base"]["lowest_cost_eligible_supplier_under_inputs"])

    def test_discount_and_tax_convention_is_explicit_and_exact(self):
        p=sample()
        for o in p["offers"]:
            o.update(unit_price="10",waste_pct="0",discount_pct="10",
                     tax_pct="10",setup_flat="5",freight_flat="20")
        v=offers(audit.evaluate(p))["Synthetic Provider North"]
        self.assertEqual(v["discounted_material_cost"],"900.00")
        self.assertEqual(v["tax_cost"],"90.50")
        self.assertEqual(v["total_landed_cost"],"1015.50")

    def test_invalid_numeric_inputs_are_rejected(self):
        for value in ("-1","NaN","Infinity","10000000000000",1.8,True):
            with self.subTest(value=value):
                p=sample();p["offers"][0]["unit_price"]=value
                with self.assertRaises(audit.AuditInputError):audit.evaluate(p)

    def test_invalid_quote_schema_duplicate_supplier_and_units_are_rejected(self):
        p=sample();p["unit"]="kg and tonne"
        with self.assertRaises(audit.AuditInputError):audit.evaluate(p)
        p=sample();p["offers"][0]["extra_unknown"]="unknown"
        with self.assertRaises(audit.AuditInputError):audit.evaluate(p)
        p=sample();p["offers"][1]["supplier"]=p["offers"][0]["supplier"]
        with self.assertRaises(audit.AuditInputError):audit.evaluate(p)

    def test_base_case_must_be_neutral(self):
        p=sample();p["stress_cases"]["base"]["price_multiplier"]="1.1"
        with self.assertRaises(audit.AuditInputError):audit.evaluate(p)

    def test_noninteger_lead_time_and_due_date_are_rejected(self):
        p=sample();p["deadline_days"]=True
        with self.assertRaises(audit.AuditInputError):audit.evaluate(p)
        p=sample();p["offers"][0]["lead_days"]=7.5
        with self.assertRaises(audit.AuditInputError):audit.evaluate(p)

    def test_whole_pack_ceil_calculation_and_actual_purchase_units(self):
        p=sample()
        p["offers"][0].update(
            unit_price="90",pricing_basis="per_pack",pack_size_base_units="20")
        r=audit.evaluate(p)
        o=offers(r)["Synthetic Provider North"]
        self.assertEqual(o["quote_pricing_basis"],"per_pack")
        self.assertEqual(o["whole_packs_ordered"],"6")
        self.assertEqual(o["gross_order_units"],"120.00")
        self.assertEqual(o["gross_units_before_pack_rounding"],"105.26")
        self.assertEqual(o["pack_size_base_units"],"20.00")
        self.assertEqual(o["quoted_price_normalized_per_base_unit"],"4.50")
        self.assertEqual(o["net_usable_units_from_order"],"114.00")
        self.assertEqual(o["surplus_usable_units"],"14.00")
        self.assertEqual(o["discounted_material_cost"],"513.00")
        self.assertEqual(o["total_landed_cost"],"558.00")
        self.assertFalse(r["commercial_release_allowed"])
        self.assertFalse(r["market_demand_verified"])

    def test_pack_pricing_handles_minimum_order_with_ceiling(self):
        p=sample()
        p["offers"][0].update(
            unit_price="90",pricing_basis="per_pack",
            pack_size_base_units="20",minimum_order_units="150",
            available_units="500")
        o=offers(audit.evaluate(p))["Synthetic Provider North"]
        self.assertEqual(o["whole_packs_ordered"],"8")
        self.assertEqual(o["gross_order_units"],"160.00")
        self.assertEqual(o["net_usable_units_from_order"],"152.00")

    def test_capacity_checks_rounded_pack_qty_not_unrounded_demand(self):
        p=sample()
        p["offers"][0].update(
            unit_price="90",pricing_basis="per_pack",
            pack_size_base_units="20",available_units="110")
        o=offers(audit.evaluate(p))["Synthetic Provider North"]
        self.assertEqual(o["gross_order_units"],"120.00")
        self.assertIn("INSUFFICIENT_DECLARED_CAPACITY",o["reasons"])
        self.assertFalse(o["eligible_for_cost_comparison"])

    def test_pack_scenario_adverse_recalculates_count_and_quote_multiplier(self):
        p=sample()
        p["offers"][0].update(unit_price="100",pricing_basis="per_pack",
                              pack_size_base_units="20",discount_pct="0")
        p["stress_cases"]["adverse"].update(
            waste_extra_pp="25",price_multiplier="1.5",
            freight_multiplier="2")
        r=audit.evaluate(p)
        b=offers(r,"base")["Synthetic Provider North"]
        a=offers(r,"adverse")["Synthetic Provider North"]
        self.assertEqual(b["whole_packs_ordered"],"6")
        self.assertEqual(a["whole_packs_ordered"],"8")
        self.assertEqual(b["total_landed_cost"],"645.00")
        self.assertEqual(a["total_landed_cost"],"1290.00")

    def test_invalid_quote_basis_and_pack_sizes_are_rejected(self):
        for patch in [
            {"pack_size_base_units":"20"},
            {"pricing_basis":"per_pack"},
            {"pricing_basis":"per_base_unit","pack_size_base_units":"20"},
            {"pricing_basis":"per_pack","pack_size_base_units":"0"},
            {"pricing_basis":"per_pack","pack_size_base_units":"-1"},
            {"pricing_basis":"per_pack","pack_size_base_units":"NaN"},
            {"pricing_basis":"per_pack","pack_size_base_units":False},
            {"pricing_basis":"per_pack","pack_size_base_units":2.5},
            {"pricing_basis":"per_pack","pack_size_base_units":"1000000001"},
        ]:
            with self.subTest(patch=patch):
                p=sample();p["offers"][0].update(patch)
                with self.assertRaises(audit.AuditInputError):
                    audit.evaluate(p)

    def test_large_pack_does_not_falsely_claim_savings(self):
        p=sample()
        p["offers"][0].update(
            pricing_basis="per_pack",pack_size_base_units="1000",
            unit_price="4200",available_units="2000")
        o=offers(audit.evaluate(p))["Synthetic Provider North"]
        self.assertEqual(o["whole_packs_ordered"],"1")
        self.assertEqual(o["gross_order_units"],"1000.00")
        self.assertEqual(o["quoted_price_normalized_per_base_unit"],"4.20")
        self.assertEqual(o["surplus_usable_units"],"850.00")
        self.assertEqual(o["total_landed_cost"],"4035.00")
        self.assertNotEqual(
            audit.evaluate(p)["scenarios"]["base"][
                "lowest_cost_eligible_supplier_under_inputs"],
            "Synthetic Provider North")

    def test_invalid_waste_scenario_has_no_pack_purchase_approval(self):
        p=sample()
        p["offers"][0].update(pricing_basis="per_pack",
                              pack_size_base_units="25",waste_pct="99")
        p["stress_cases"]["adverse"]["waste_extra_pp"]="2"
        o=offers(audit.evaluate(p),"adverse")["Synthetic Provider North"]
        self.assertIsNone(o["total_landed_cost"])
        self.assertIsNone(o["whole_packs_ordered"])
        self.assertIn("WASTE_AT_OR_ABOVE_100_PERCENT",o["reasons"])

    def test_quote_basis_default_is_backward_compatible(self):
        p=sample()
        o=offers(audit.evaluate(p))["Synthetic Provider North"]
        self.assertEqual(o["quote_pricing_basis"],"per_base_unit")
        self.assertIsNone(o["pack_size_base_units"])
        self.assertIsNone(o["whole_packs_ordered"])
        self.assertEqual(o["quoted_price_normalized_per_base_unit"],"5.00")
        self.assertEqual(o["gross_units_before_pack_rounding"],"105.26")

    def test_arithmetic_gap_is_explicitly_not_realized_savings(self):
        p=sample()
        r=audit.evaluate(p)
        rows=r["scenarios"]["base"]["offers"]
        eligible=[x for x in rows if x["eligible_for_cost_comparison"]]
        self.assertEqual(len(eligible),2)
        a=Decimal(eligible[0]["total_landed_cost"])
        b=Decimal(eligible[1]["total_landed_cost"])
        self.assertEqual(
            r["scenarios"]["base"][
                "arithmetic_cost_gap_to_second_eligible_not_realized_savings"],
            audit.shown(b-a))
        self.assertEqual(
            r["scenarios"]["base"][
                "second_lowest_cost_eligible_supplier_under_inputs"],
            eligible[1]["supplier"])
        self.assertIn("COST_SPREAD_IS_NOT_REALIZED_SAVINGS",r["warnings"])

    def test_no_second_eligible_offer_means_no_spread(self):
        p=sample()
        p["offers"][1]["lead_days"]=30
        r=audit.evaluate(p)
        self.assertIsNone(
            r["scenarios"]["base"][
                "arithmetic_cost_gap_to_second_eligible_not_realized_savings"])
        self.assertIsNone(
            r["scenarios"]["base"][
                "second_lowest_cost_eligible_supplier_under_inputs"])

    def test_rounding_never_buys_a_fractional_pack(self):
        p=sample()
        p["offers"][0].update(pricing_basis="per_pack",
                              pack_size_base_units="7",
                              unit_price="35")
        x=offers(audit.evaluate(p))["Synthetic Provider North"]
        self.assertEqual(x["whole_packs_ordered"],"16")
        self.assertEqual(x["gross_order_units"],"112.00")
        self.assertEqual(x["surplus_usable_units"],"6.40")

    def test_report_is_deterministic_and_market_flags_remain_false(self):
        p=sample();p2=deepcopy(p)
        a=audit.evaluate(p);b=audit.evaluate(p2)
        self.assertEqual(a,b)
        self.assertEqual(p,p2)
        self.assertEqual(len(a["input_sha256"]),64)
        self.assertIsNone(a["quality_score"])
        self.assertFalse(a["commercial_release_allowed"])
        self.assertFalse(a["market_demand_verified"])
        self.assertFalse(a["sources_independently_verified"])

    def test_print_html_escapes_user_supplier_text(self):
        p=sample();p["offers"][0]["supplier"]="<script>alert('x')</script>"
        out=printer.report_html(audit.evaluate(p))
        self.assertNotIn("<script>alert('x')</script>",out)
        self.assertIn("&lt;script&gt;",out)
        self.assertIn("Not a verified quote",out)
        self.assertIn("Lowest arithmetic eligible offer",out)

    def test_html_refuses_false_commercial_claim(self):
        o=audit.evaluate(sample());o["commercial_release_allowed"]=True
        with self.assertRaises(ValueError):printer.report_html(o)

    def test_cli_and_html_reports_are_private_and_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);src=home/"in.json";target=home/"out.json";html=home/"report.html"
            src.write_text(json.dumps(sample()),encoding="utf-8")
            script=str(P/"procurement_audit.py")
            proc=subprocess.run([sys.executable,script,"--input",str(src),"--output",str(target)],
                                capture_output=True,text=True,timeout=15)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertEqual(target.stat().st_mode & 0o777,0o600)
            self.assertNotEqual(subprocess.run([sys.executable,script,"--input",str(src),
                "--output",str(target)],capture_output=True,timeout=10).returncode,0)
            pp=subprocess.run([sys.executable,str(P/"render_report.py"),"--report",
                str(target),"--html",str(html)],capture_output=True,text=True,timeout=15)
            self.assertEqual(pp.returncode,0,pp.stderr)
            self.assertEqual(html.stat().st_mode & 0o777,0o600)

    def test_distributable_standalone_self_test(self):
        p=subprocess.run([sys.executable,str(P/"self_test.py")],
                         capture_output=True,text=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("PROCUREMENT_SELF_TEST=PASS",p.stdout)


if __name__=="__main__":
    unittest.main()
