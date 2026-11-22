"""Numerical/edge-case validation of real farm economics without fake receipts."""
import importlib.util
from decimal import Decimal
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("farm",ROOT/"scripts/mojtaba_farm_break_even.py")
farm=importlib.util.module_from_spec(spec)
spec.loader.exec_module(farm)


def example(**kwargs):
    values = {
        "canonical_bot":"mojtaba.bot.ai","period":"annual",
        "area_ha":"10","yield_kg_per_ha":"1000",
        "sale_price_irr_per_kg":"200000",
        "variable_cost_irr_per_kg":"100000",
        "fixed_cost_irr":"500000000",
        "price_sensitivity_fraction":"0.10",
        "yield_sensitivity_fraction":"0.10",
        "cost_sensitivity_fraction":"0.10",
        "synthetic_example":True,
    }
    values.update(kwargs)
    return values

class FarmEconomics(unittest.TestCase):
    def test_complete_real_arithmetic(self):
        r=farm.model(example())
        self.assertEqual(r["volume_kg"],"10000")
        self.assertEqual(r["gross_revenue_irr"],"2000000000")
        self.assertEqual(r["variable_cost_irr"],"1000000000")
        self.assertEqual(r["fixed_cost_irr"],"500000000")
        self.assertEqual(r["total_cost_irr"],"1500000000")
        self.assertEqual(r["estimated_profit_irr"],"500000000")
        self.assertEqual(r["unit_contribution_irr_per_kg"],"100000")
        self.assertEqual(r["breakeven_quantity_kg_ceil"],"5000")
        self.assertEqual(r["breakeven_sale_price_irr_per_kg_ceil"],"150000")
        self.assertEqual(r["breakeven_revenue_irr_ceil"],"1000000000")
        self.assertEqual(r["margin_of_safety_kg"],"5000")

    def test_27_scenarios_include_midpoint(self):
        r=farm.model(example())
        self.assertEqual(r["scenario_count"],27)
        self.assertEqual(len(r["sensitivity_scenarios"]),27)
        self.assertEqual(len({
            (x["price_direction"],x["yield_direction"],x["variable_cost_direction"])
            for x in r["sensitivity_scenarios"]}),27)
        middle=[x for x in r["sensitivity_scenarios"]
                if (x["price_direction"],x["yield_direction"],x["variable_cost_direction"])==(0,0,0)]
        self.assertEqual(middle[0]["profit_irr"],r["estimated_profit_irr"])

    def test_declining_prices_and_yields_and_higher_cost_reduce_profit(self):
        r=farm.model(example())
        worst=next(x for x in r["sensitivity_scenarios"] if
                   (x["price_direction"],x["yield_direction"],x["variable_cost_direction"])==(-1,-1,1))
        best=next(x for x in r["sensitivity_scenarios"] if
                   (x["price_direction"],x["yield_direction"],x["variable_cost_direction"])==(1,1,-1))
        self.assertLess(int(worst["profit_irr"]),int(r["estimated_profit_irr"]))
        self.assertGreater(int(best["profit_irr"]),int(r["estimated_profit_irr"]))

    def test_profit_loss_scenarios_both_reported(self):
        r=farm.model(example(fixed_cost_irr="1150000000"))
        self.assertTrue(any(x["loss_scenario"] for x in r["sensitivity_scenarios"]))
        self.assertTrue(any(not x["loss_scenario"] for x in r["sensitivity_scenarios"]))

    def test_nonpositive_contribution_blocks_break_even_quantity(self):
        r=farm.model(example(sale_price_irr_per_kg="100000",
                             variable_cost_irr_per_kg="100000"))
        self.assertIsNone(r["breakeven_quantity_kg_ceil"])
        self.assertIsNone(r["breakeven_revenue_irr_ceil"])
        self.assertTrue(r["unit_contribution_nonpositive"])
        self.assertLess(Decimal(r["estimated_profit_irr"]),0)

    def test_overspend_cannot_prove_profitable_unit(self):
        r=farm.model(example(sale_price_irr_per_kg="70000",
                             variable_cost_irr_per_kg="100000"))
        self.assertTrue(r["unit_contribution_nonpositive"])
        self.assertIsNone(r["margin_of_safety_kg"])

    def test_zero_fixed_cost_breakeven_zero(self):
        r=farm.model(example(fixed_cost_irr="0"))
        self.assertEqual(r["breakeven_quantity_kg_ceil"],"0")
        self.assertEqual(r["breakeven_sale_price_irr_per_kg_ceil"],"100000")

    def test_threshold_rounds_up(self):
        r=farm.model(example(fixed_cost_irr="100000001"))
        self.assertEqual(r["breakeven_quantity_kg_ceil"],"1001")

    def test_non_integer_yield_remains_precise(self):
        r=farm.model(example(area_ha="1.1250",yield_kg_per_ha="1000.25"))
        self.assertEqual(Decimal(r["volume_kg"]),Decimal("1.1250")*Decimal("1000.25"))

    def test_unaudited_real_aggregate_input_is_not_faked_to_synthetic(self):
        r=farm.model(example(synthetic_example=False))
        self.assertFalse(r["synthetic_example"])
        self.assertFalse(r["input_figures_independently_verified"])
        self.assertFalse(r["quote_approved"])
        self.assertFalse(r["payment_collected"])

    def test_only_one_canonical_bot(self):
        with self.assertRaisesRegex(ValueError,"NON_CANONICAL"):
            farm.model(example(canonical_bot="other.bot.ai"))

    def test_no_identity_or_customer_fields_allowed(self):
        for key in ("buyer_email","customer_name","wallet_address","invoice_id"):
            with self.subTest(key=key),self.assertRaises(ValueError):
                farm.model(example(**{key:"PRIVATE"}))

    def test_no_unverified_currency_or_unit_conversion(self):
        with self.assertRaises(ValueError):
            farm.model(example(currency="USD"))

    def test_period_is_exact_enum(self):
        for bad in (None,"weekly","lifetime",123):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                farm.model(example(period=bad))

    def test_invalid_area_or_yield_rejected(self):
        for key in ("area_ha","yield_kg_per_ha"):
            for bad in (0,True, "-1","0","0.0000","1e7","NaN","00.1","1.00001"):
                with self.subTest(key=key,bad=bad),self.assertRaises(ValueError):
                    farm.model(example(**{key:bad}))

    def test_zero_or_negative_price_rejected(self):
        for value in ("0","-4","10.25","NaN",3):
            with self.subTest(value=value),self.assertRaises(ValueError):
                farm.model(example(sale_price_irr_per_kg=value))

    def test_money_inputs_no_fractional_irr(self):
        for key in ("variable_cost_irr_per_kg","fixed_cost_irr"):
            for bad in ("-1","0.01","1e8",1,True,"099"):
                with self.subTest(key=key,bad=bad),self.assertRaises(ValueError):
                    farm.model(example(**{key:bad}))

    def test_zero_sensitivity_all_scenarios_have_same_profit(self):
        r=farm.model(example(price_sensitivity_fraction="0",
              yield_sensitivity_fraction="0",cost_sensitivity_fraction="0"))
        self.assertEqual({x["profit_irr"] for x in r["sensitivity_scenarios"]},
                         {r["estimated_profit_irr"]})

    def test_sensitivity_over_30_percent_rejected(self):
        for key in ("price_sensitivity_fraction","yield_sensitivity_fraction",
                    "cost_sensitivity_fraction"):
            for bad in ("0.3001","0.99","1","-0.1",1,True,"0.10001"):
                with self.subTest(key=key,bad=bad),self.assertRaises(ValueError):
                    farm.model(example(**{key:bad}))

    def test_output_does_not_claim_customer_acceptance(self):
        r=farm.model(example())
        for key in ("invoice_created","quote_approved","payment_collected",
                    "production_deployed","input_figures_independently_verified"):
            self.assertFalse(r[key])
        self.assertEqual(r["canonical_bot"],"mojtaba.bot.ai")
        self.assertEqual(r["currency"],"IRR")

    def test_input_is_not_mutated(self):
        original=example()
        snapshot=dict(original)
        farm.model(original)
        self.assertEqual(original,snapshot)

if __name__=="__main__":unittest.main()
