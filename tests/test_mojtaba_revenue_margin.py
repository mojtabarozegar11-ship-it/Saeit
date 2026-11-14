"""Margin arithmetic uses Decimal and never produces an approved invoice."""
import importlib.util
from pathlib import Path
import sys
import unittest
from decimal import Decimal

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import mojtaba_revenue_margin as m


def request(offer_id="website_diagnosis", **changes):
    row=dict(canonical_bot="mojtaba.bot.ai",offer_id=offer_id,
        currency="USD",direct_cost="20.00",overhead_cost="5.00",
        processor_fee_fraction="0.0200",target_margin_fraction="0.3000",
        synthetic_example=True)
    row.update(changes)
    return row


class MarginPreviewTests(unittest.TestCase):
    def test_deterministic_usd_price_floor(self):
        r=m.estimate(request())
        self.assertEqual(r["gross_price_floor_synthetic"],"36.77")
        self.assertEqual(r["currency"],"USD")
        self.assertFalse(r["quote_approved"])
        self.assertFalse(r["payment_authorized"])

    def test_simple_irr_margin_review(self):
        r=m.estimate(request(offer_id="farm_economics",currency="IRR",
            direct_cost="1000000",overhead_cost="200000",
            processor_fee_fraction="0",target_margin_fraction="0.2"))
        self.assertEqual(r["gross_price_floor_synthetic"],"1500000")
        self.assertEqual(r["currency"],"IRR")

    def test_floor_meets_margin_before_tax(self):
        r=m.estimate(request(direct_cost="44.99",overhead_cost="3.12",
                             target_margin_fraction="0.26"))
        price=Decimal(r["gross_price_floor_synthetic"])
        margin=(price-Decimal("0.02")*price-Decimal("48.11"))/price
        self.assertGreaterEqual(margin,Decimal("0.26"))

    def test_real_accounting_input_refused(self):
        with self.assertRaises(ValueError):
            m.estimate(request(synthetic_example=False))

    def test_foreign_currency_refused(self):
        with self.assertRaises(ValueError):
            m.estimate(request(currency="IRR"))

    def test_no_wallet_pii_or_extra_fields(self):
        with self.assertRaises(ValueError):
            m.estimate(request(customer_email="buyer@example.com"))

    def test_no_second_bot(self):
        with self.assertRaises(ValueError):
            m.estimate(request(canonical_bot="other.bot.ai"))

    def test_nonnegative_decimal_costs_only(self):
        for value in ("-1", "NaN", "Infinity", "$10", "1e3", "00.2",
                      "0.001", "1.000", "9999999999999", 25, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.estimate(request(direct_cost=value))

    def test_irr_disallows_fractional_costs(self):
        with self.assertRaises(ValueError):
            m.estimate(request(offer_id="farm_economics",currency="IRR",
                direct_cost="40.50"))

    def test_zero_cost_cannot_generate_zero_price(self):
        with self.assertRaises(ValueError):
            m.estimate(request(direct_cost="0",overhead_cost="0"))

    def test_rates_are_bounded(self):
        for value in ("0.26", "0.8000", "-0.1", "1", "0.00001"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.estimate(request(processor_fee_fraction=value))
        with self.assertRaises(ValueError):
            m.estimate(request(target_margin_fraction="0.71"))

    def test_not_live_not_paid_not_tax_advice(self):
        r=m.estimate(request())
        self.assertFalse(r["invoice_created"])
        self.assertFalse(r["revenue_verified"])
        self.assertFalse(r["production_deployed"])
        self.assertIn("before any taxes",r["assumptions"])

    def test_all_ten_offer_codes_supported_with_correct_currency(self):
        from mojtaba_revenue_portfolio import OFFERS
        for code,offer in OFFERS.items():
            cur="IRR" if offer.domain=="zomorodmelal.ir" else "USD"
            r=m.estimate(request(offer_id=code,currency=cur,
                direct_cost="100",overhead_cost="10"))
            self.assertEqual(r["offer_id"],code)
            self.assertEqual(r["currency"],cur)

if __name__=="__main__":unittest.main()
