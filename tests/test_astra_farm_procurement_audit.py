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
