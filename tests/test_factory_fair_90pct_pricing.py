"""Factory pricing must not inflate a publicly free tool or invent price history."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import unittest
from scripts.factory_fair_90pct_pricing import assess,quote,DEFAULT


class FairFactoryPrices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy=json.loads(DEFAULT.read_text("utf-8"))

    def test_all_verified_products_receive_quote(self):
        rows=assess(self.policy)
        self.assertEqual({r["recipe"] for r in rows},
            {"farm_enterprise_economics","water_budget_economics"})

    def test_public_free_tool_remains_free(self):
        quote_farm=assess(self.policy)[0]
        self.assertEqual(quote_farm["launch_quote"],"0.00")
        self.assertFalse(quote_farm["eligible_to_activate_paid_checkout"])
        self.assertEqual(quote_farm["launch_reduction_percent"],"not_applicable_free")

    def test_water_budget_fair_quote_and_90_percent_reduction(self):
        water=next(x for x in assess(self.policy) if x["recipe"]=="water_budget_economics")
        self.assertEqual(water["fair_value_reference"],"9.90")
        self.assertEqual(water["launch_quote"],"0.99")
        self.assertFalse(water["allow_fake_former_price_claim"])
        self.assertFalse(water["eligible_to_activate_paid_checkout"])
        self.assertEqual(Decimal(water["launch_quote"]),Decimal(water["fair_value_reference"])*Decimal("0.10"))

    def test_no_fake_msrp_badge(self):
        bad=copy.deepcopy(self.policy)
        bad["pricing_rule"]["reference_price_display_allowed"]=True
        with self.assertRaises(ValueError):
            assess(bad)

    def test_duplicate_recipe_rejected(self):
        bad=copy.deepcopy(self.policy)
        bad["assessments"][1]=copy.deepcopy(bad["assessments"][0])
        with self.assertRaises(ValueError):
            assess(bad)

    def test_unsupported_factory_product_cannot_be_blindly_priced(self):
        record=copy.deepcopy(self.policy["assessments"][1])
        record["recipe"]="unknown_product"
        with self.assertRaises(ValueError):
            quote(record)

    def test_free_public_asset_cannot_be_repriced_as_paid(self):
        record=copy.deepcopy(self.policy["assessments"][0])
        record["fair_normal_price_usd"]="49.90"
        record["introductory_price_usd"]="4.99"
        with self.assertRaises(ValueError):
            quote(record)

    def test_discount_tamper_rejected(self):
        record=copy.deepcopy(self.policy["assessments"][1])
        record["introductory_price_usd"]="1.49"
        with self.assertRaises(ValueError):
            quote(record)

    def test_subcent_and_negative_price_rejected(self):
        for val in ("-1.00","9.999","NaN","Infinity"):
            record=copy.deepcopy(self.policy["assessments"][1])
            record["fair_normal_price_usd"]=val
            with self.assertRaises((ValueError,ArithmeticError)):
                quote(record)

    def test_zero_price_internal_math_not_a_discount_claim(self):
        record=self.policy["assessments"][0]
        output=quote(record)
        self.assertFalse(output["paid_quote_only"])
