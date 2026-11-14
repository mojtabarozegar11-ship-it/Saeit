"""Offline proof that one canonical bot owns inquiry-only commercial policy."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "mojtaba_revenue_portfolio", ROOT / "scripts/mojtaba_revenue_portfolio.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def inquiry(offer_id="farm_economics", **override):
    row = {"canonical_bot": "mojtaba.bot.ai", "offer_id": offer_id,
           "scope_items": 1, "evidence_items": 2, "consent": True,
           "rights_documents": 0, "inventory_documents": 0,
           "delivery_documents": 0, "synthetic_example": True}
    row.update(override)
    return row


class CanonicalCatalog(unittest.TestCase):
    def test_ten_distinct_offers(self):
        self.assertEqual(len(module.OFFERS), 10)

    def test_all_offers_on_two_existing_sites(self):
        self.assertEqual({x.domain for x in module.OFFERS.values()},
                         {"zomorodmelal.ir", "mojplaywin.com"})

    def test_all_offers_have_source_paths(self):
        for x in module.OFFERS.values():
            with self.subTest(x=x.code):
                self.assertTrue((ROOT / x.source).is_file(), x.source)

    def test_no_external_payment_or_trader_in_catalog(self):
        for x in module.OFFERS.values():
            self.assertEqual(x.commercial_mode, "inquiry_only")
            self.assertNotIn("wallet", x.lawful_channel)
            self.assertNotIn("exchange", x.lawful_channel)

    def test_catalog_is_immutable(self):
        with self.assertRaises(TypeError):
            module.OFFERS["extra"] = "a second bot"


class IntakeGovernance(unittest.TestCase):
    def test_valid_farm_is_only_manual_scope_review(self):
        r = module.evaluate(inquiry())
        self.assertEqual(r["decision"], "manual_scope_review")
        self.assertEqual(r["canonical_bot"], "mojtaba.bot.ai")

    def test_inquiry_never_claims_order_or_delivery(self):
        for offer in module.OFFERS:
            r = module.evaluate(inquiry(offer))
            self.assertEqual(r["order_state"], "inquiry_only")
            self.assertFalse(r["delivery_verified"])
            self.assertFalse(r["payment_verified"])
            self.assertFalse(r["price_approved"])
            self.assertFalse(r["invoice_authorized"])
            self.assertFalse(r["auto_send"])

    def test_noncanonical_bot_rejected(self):
        for name in ("another.bot.ai", "Mojtaba Bot", "", None):
            with self.subTest(name=name), self.assertRaises(ValueError):
                module.evaluate(inquiry(canonical_bot=name))

    def test_external_customer_identifiers_rejected(self):
        for key in ("email", "phone", "wallet", "password", "api_key",
                    "name", "customer", "card", "payment_id"):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "PERSONAL"):
                module.evaluate(inquiry(**{key: "sensitive"}))

    def test_unknown_field_rejected(self):
        with self.assertRaises(ValueError):
            module.evaluate(inquiry(promised_annual_revenue=100000))

    def test_non_dict_rejected(self):
        for value in (None, [], "{}", 3, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.evaluate(value)

    def test_unknown_offer_rejected(self):
        with self.assertRaises(ValueError):
            module.evaluate(inquiry("instant_money"))

    def test_missing_consent_blocks(self):
        r = module.evaluate(inquiry(consent=False))
        self.assertIn("NO_CONTACT_CONSENT", r["blockers"])

    def test_missing_evidence_blocks(self):
        r = module.evaluate(inquiry(evidence_items=0))
        self.assertIn("EVIDENCE_MISSING", r["blockers"])

    def test_unbounded_scope_blocks(self):
        for count in (0, 4, 20):
            r = module.evaluate(inquiry(scope_items=count))
            self.assertIn("SCOPE_REQUIRES_REVIEW", r["blockers"])

    def test_counts_reject_boolean_string_negative_and_decimal(self):
        for key in ("scope_items", "evidence_items", "rights_documents",
                    "inventory_documents", "delivery_documents"):
            for bad in (True, False, -1, 21, "1", 1.2, None):
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    module.evaluate(inquiry(**{key: bad}))

    def test_boolean_fields_are_exact(self):
        for field in ("consent", "synthetic_example"):
            for bad in (1, "yes", None):
                with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                    module.evaluate(inquiry(**{field: bad}))

    def test_no_rights_no_digital_offer(self):
        for code in ("digital_publication", "game_license"):
            with self.subTest(code=code):
                r = module.evaluate(inquiry(code))
                self.assertIn("RIGHTS_NOT_DOCUMENTED", r["blockers"])
                self.assertIn("DELIVERABLE_NOT_DOCUMENTED", r["blockers"])
                self.assertIn("PRODUCT_NOT_LIVE_OR_PROVEN", r["blockers"])

    def test_even_self_claimed_rights_cannot_prove_live_product(self):
        r = module.evaluate(inquiry("game_license", rights_documents=9,
                                    delivery_documents=3))
        self.assertIn("PRODUCT_NOT_LIVE_OR_PROVEN", r["blockers"])
        self.assertFalse(r["production_deployed"])

    def test_stock_required_for_catalog_and_cafe(self):
        for code in ("cafe_b2b", "company_catalog"):
            r = module.evaluate(inquiry(code))
            self.assertIn("STOCK_OR_CAPACITY_NOT_DOCUMENTED", r["blockers"])

    def test_stock_document_count_not_live_confirmation(self):
        r = module.evaluate(inquiry("company_catalog", inventory_documents=4))
        self.assertTrue(r["all_document_counts_unverified"])
        self.assertFalse(r["production_deployed"])

    def test_educational_trading_is_not_trading_authority(self):
        r = module.evaluate(inquiry("trading_education", evidence_items=4))
        self.assertIn("NO_TRADING_EXECUTION_ALLOWED", r["blockers"])
        self.assertFalse(r["trade_execution_authorized"])

    def test_no_personal_data_echoed(self):
        r = module.evaluate(inquiry())
        self.assertNotIn("email", json.dumps(r))
        self.assertNotIn("password", json.dumps(r))
        self.assertIsNone(r["collected_revenue"])


class KpiFalsificationGuards(unittest.TestCase):
    @staticmethod
    def numbers(**changes):
        row = dict(views=100, inquiries=20, qualified=10, approved_quotes=5,
                   paid_orders=2, delivered_orders=1, synthetic_example=True)
        row.update(changes)
        return row

    def test_correct_synthetic_funnel_ratios(self):
        r = module.synthetic_kpis(self.numbers())
        self.assertEqual(r["inquiry_rate"], "0.2000")
        self.assertEqual(r["qualification_rate"], "0.5000")
        self.assertEqual(r["quote_to_paid_rate"], "0.4000")
        self.assertEqual(r["paid_to_delivery_rate"], "0.5000")

    def test_zero_denominator_returns_unknown_not_fabricated_zero(self):
        r = module.synthetic_kpis(self.numbers(
            views=0, inquiries=0, qualified=0, approved_quotes=0,
            paid_orders=0, delivered_orders=0))
        self.assertIsNone(r["inquiry_rate"])
        self.assertIsNone(r["quote_to_paid_rate"])

    def test_real_kpi_claim_refused(self):
        with self.assertRaisesRegex(ValueError, "REQUIRE_INDEPENDENT"):
            module.synthetic_kpis(self.numbers(synthetic_example=False))

    def test_invalid_sequence_refused(self):
        with self.assertRaisesRegex(ValueError, "ORDER"):
            module.synthetic_kpis(self.numbers(paid_orders=9))

    def test_negative_and_boolean_denied(self):
        with self.assertRaises(ValueError):
            module.synthetic_kpis(self.numbers(views=-1))
        with self.assertRaises(ValueError):
            module.synthetic_kpis(self.numbers(inquiries=True))

    def test_source_test_success_cannot_create_revenue(self):
        r = module.no_revenue_claims_from_source(500, receipts_verified=True)
        self.assertIsNone(r["verified_collected_revenue"])
        self.assertIsNone(r["verified_paid_orders"])
        self.assertFalse(r["receipt_attestation_from_source_only"])

    def test_money_parser_is_not_a_quote(self):
        from decimal import Decimal
        self.assertEqual(module.validate_manual_money_range("29.50"), Decimal("29.50"))
        for bad in ("-1", "NaN", "Infinity", "10.000", "$30", "1e8",
                    "9999999999999999999", "1,000", " 5", "", 100):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                module.validate_manual_money_range(bad)

    def test_unsupported_kpi_keys_refused(self):
        with self.assertRaises(ValueError):
            module.synthetic_kpis(dict(self.numbers(), customer_email="secret"))

if __name__ == "__main__":
    unittest.main()
