"""Independent mathematical benchmark: 300 deterministic SYNTHETIC examples.

One hundred cases each for orchard NPV, supplier landed cost and two-crop
water/land optimization. References use fractions-based implementations
independent of the original product engines. These are *not* market evidence,
buyer interviews, domain expert signoff or commercial quality ratings.
"""
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from fractions import Fraction
import importlib.util
from itertools import combinations
from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"product_prototypes"


def imported(slug,name):
    path=P/slug/(name+".py")
    s=importlib.util.spec_from_file_location("independent_math_"+slug,path)
    m=importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


orchard=imported("orchard_decision_audit","decision_audit")
procurement=imported("farm_procurement_audit","procurement_audit")
water=imported("farm_water_land_margin_audit","water_margin_audit")


def pennies(fraction):
    with localcontext() as ctx:
        ctx.prec=60
        value=Decimal(fraction.numerator)/Decimal(fraction.denominator)
        return str(value.quantize(Decimal("0.01"),rounding=ROUND_HALF_EVEN))


def independently_optimize_two_crop(caps, uses, profits, land, water_cap):
    # Enumerate all pairwise intersections of the six constraint boundaries
    # using exact rational arithmetic. This is intentionally a DIFFERENT
    # implementation of the solver than Astra's general n-crop algorithm.
    lines=[
        (1,0,0), (1,0,caps[0]),
        (0,1,0), (0,1,caps[1]),
        (1,1,land), (uses[0],uses[1],water_cap),
    ]
    optimum=Fraction(0)
    for line_a,line_b in combinations(lines,2):
        a,b,c=line_a
        d,e,f=line_b
        det=a*e-b*d
        if det==0:
            continue
        x=Fraction(c*e-b*f,det)
        y=Fraction(a*f-c*d,det)
        if not(0<=x<=caps[0] and 0<=y<=caps[1]):
            continue
        if x+y>land or uses[0]*x+uses[1]*y>water_cap:
            continue
        optimum=max(optimum,profits[0]*x+profits[1]*y)
    return optimum


class IndependentTechnicalQualityBenchmark(unittest.TestCase):
    def test_100_orchard_npv_cases_against_independent_fraction_reference(self):
        for i in range(100):
            with self.subTest(synthetic_case=i):
                rate=(i%7)*5
                year0=100+(i*7)%401
                revenues=[0,200+(i*11)%270,210+(i*13)%300]
                variable=[0,40+(i*3)%57,38+(i*5)%70]
                fixed=[0,12+i%9,12+(i*2)%9]
                capital=[year0,0,0]
                terminal=[0,0,(i*5)%90]
                def build_rows(multiplier):
                    return [
                        {"year":year,"revenue":str(revenues[year]*multiplier),
                         "variable_cost":str(variable[year]*multiplier),
                         "fixed_cost":str(fixed[year]),
                         "capital_cost":str(capital[year]),
                         "terminal_value":str(terminal[year])}
                        for year in range(3)]
                payload={
                    "currency":"USD","unit":"whole_farm","money_basis":"real",
                    "horizon_years":2,"discount_rate_pct":str(rate),
                    "reference_option":"Synthetic A",
                    "options":[
                        {"name":"Synthetic A","years":build_rows(1)},
                        {"name":"Synthetic B","years":build_rows(2)},
                    ],
                    "stress_scenarios":{
                        "downside":{"price_factor":"0.9","yield_factor":"0.9",
                                    "variable_cost_factor":"1.1"},
                        "upside":{"price_factor":"1.1","yield_factor":"1.1",
                                  "variable_cost_factor":"0.9"},
                    },
                    "assumptions":[],
                }
                result=orchard.analyze(payload)
                fraction_rate=Fraction(100+rate,100)
                cashflows=[
                    revenues[y]+terminal[y]-variable[y]-fixed[y]-capital[y]
                    for y in range(3)]
                expected=sum((Fraction(cf)/(fraction_rate**y)
                              for y,cf in enumerate(cashflows)),Fraction(0))
                option=next(o for o in result["scenarios"]["base"]
                            if o["option"]=="Synthetic A")
                self.assertEqual(option["npv"],pennies(expected))
                self.assertFalse(result["store_listing_authorized"])
                self.assertFalse(result["market_demand_verified"])

    def test_100_procurement_cost_cases_against_independent_rational_formula(self):
        fixture=json.loads((P/"farm_procurement_audit"/"example_synthetic.json").read_text())
        for i in range(100):
            with self.subTest(synthetic_case=i):
                case=json.loads(json.dumps(fixture))
                case["net_units_required"]="100"
                case["deadline_days"]=365
                chosen=case["offers"][0]
                unit_price=1+i%37
                waste=i%29
                discount=(i*3)%23
                tax=(i*5)%19
                setup=(i*7)%31
                freight=(i*11)%79
                chosen.update({
                    "unit_price":str(unit_price),"waste_pct":str(waste),
                    "discount_pct":str(discount),"tax_pct":str(tax),
                    "setup_flat":str(setup),"freight_flat":str(freight),
                    "minimum_order_units":"0","available_units":"10000",
                    "lead_days":0,"source_label":"SYNTHETIC RECORD ONLY",
                    "quote_ref":"SYNTHETIC-"+str(i),
                })
                output=procurement.evaluate(case)
                supplied={o["supplier"]:o for o in output["scenarios"]["base"]["offers"]}
                row=supplied[chosen["supplier"]]
                gross=Fraction(10000,100-waste)
                after_discount=gross*unit_price*Fraction(100-discount,100)
                taxable=after_discount+setup
                total=taxable*Fraction(100+tax,100)+freight
                self.assertEqual(row["total_landed_cost"],pennies(total))
                self.assertTrue(row["eligible_for_cost_comparison"])
                self.assertFalse(row["verified_quote"])
                self.assertFalse(output["commercial_release_allowed"])

    def test_100_water_land_lp_cases_against_independent_fraction_vertex_solver(self):
        for i in range(100):
            with self.subTest(synthetic_case=i):
                caps=(1+(i*3)%8,1+(i*7)%9)
                uses=(1+(i*5)%10,1+(i*11)%10)
                profits=((i*7)%31-6,(i*13)%37-8)
                land=1+(i*3)%14
                water_cap=(i*7)%100
                parsed=[
                    {"name":"Synthetic A","max_area":Decimal(caps[0]),
                     "water":Decimal(uses[0]),"margin":Decimal(profits[0])},
                    {"name":"Synthetic B","max_area":Decimal(caps[1]),
                     "water":Decimal(uses[1]),"margin":Decimal(profits[1])},
                ]
                result=water.solve(parsed,Decimal(land),Decimal(water_cap))
                expected=independently_optimize_two_crop(
                    caps,uses,profits,land,water_cap)
                with localcontext() as ctx:
                    ctx.prec=60
                    expected_decimal=Decimal(expected.numerator)/Decimal(expected.denominator)
                self.assertLessEqual(
                    abs(result["total_margin"]-expected_decimal),Decimal("0.000000001"))
                area=result["areas"]
                self.assertTrue(all(Decimal(0)<=x<=parsed[n]["max_area"]
                                    for n,x in enumerate(area)))
                self.assertLessEqual(result["land_used"],Decimal(land))
                self.assertLessEqual(result["water_used"],Decimal(water_cap))


if __name__=="__main__":
    unittest.main()
