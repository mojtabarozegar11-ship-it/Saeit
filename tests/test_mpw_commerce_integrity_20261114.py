"""Exact order, invoice and webhook pure contracts; no DB/network/payment use."""
import hashlib
import json
from decimal import Decimal
import unittest

from core.commerce_integrity import (
    strict_id, strict_quantity, strict_key, valid_currency, valid_provider,
    valid_event_id, valid_provider_ref, valid_provider_allowlist, exact_money,
    exact_total, provider_amount, ledger_reference, parse_strict_webhook_json,
)


class CommerceIntegrityPureTests(unittest.TestCase):
    def assert_rejected(self, fn, *args):
        with self.assertRaises(ValueError):
            fn(*args)

    def test_01_canonical_integer_id(self):
        self.assertEqual(strict_id(123), 123)
        self.assertEqual(strict_id("123"), 123)

    def test_02_boolean_order_id_denied(self):
        self.assert_rejected(strict_id, True)

    def test_03_float_order_id_denied(self):
        self.assert_rejected(strict_id, 1.0)

    def test_04_array_order_id_denied(self):
        self.assert_rejected(strict_id, [1])

    def test_05_leading_zero_order_id_denied(self):
        self.assert_rejected(strict_id, "00042")

    def test_06_negative_and_zero_id_denied(self):
        for x in (0, -1, "0", "-1", ""):
            with self.subTest(value=x):
                self.assert_rejected(strict_id, x)

    def test_07_oversized_id_denied(self):
        self.assert_rejected(strict_id, "2" * 200)

    def test_08_quantity_capped(self):
        self.assertEqual(strict_quantity("100"), 100)
        self.assert_rejected(strict_quantity, "101")

    def test_09_noncanonical_quantity_denied(self):
        for x in (True, 1.2, "1.0", "1e3", " 1", "01", {}):
            with self.subTest(value=str(x)):
                self.assert_rejected(strict_quantity, x)

    def test_10_long_and_malformed_idempotency_key_denied(self):
        for x in ("short", "a" * 129, "with spaces", "a\nsecretkey", True, 12):
            with self.subTest(value=repr(x)[:20]):
                self.assert_rejected(strict_key, x)

    def test_11_valid_idempotency_key_accepted(self):
        self.assertEqual(strict_key("pay-order-20026_ABC"), "pay-order-20026_ABC")

    def test_12_currency_only_uppercase_ascii(self):
        self.assertTrue(valid_currency("IRR"))
        self.assertTrue(valid_currency("USD"))
        self.assertTrue(valid_currency("TRX"))
        for x in ("usd", "US", " USDT", "USDT-X", True, ["USD"]):
            self.assertFalse(valid_currency(x))

    def test_13_nonfinite_money_denied(self):
        for x in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
            self.assert_rejected(exact_money, x)

    def test_14_nonpositive_money_denied(self):
        for x in (Decimal("0"), Decimal("-1"), Decimal("0.00")):
            self.assert_rejected(exact_money, x)

    def test_15_float_string_bool_money_denied(self):
        for x in (1.0, "10.00", True, 10):
            self.assert_rejected(exact_money, x)

    def test_16_money_fractional_scale_enforced(self):
        self.assertEqual(exact_money(Decimal("20.10")), Decimal("20.10"))
        self.assert_rejected(exact_money, Decimal("20.001"))

    def test_17_total_calculated_without_rounding(self):
        self.assertEqual(exact_total(Decimal("125.50"), 3), Decimal("376.50"))

    def test_18_total_overflow_denied_before_database_write(self):
        self.assert_rejected(exact_total, Decimal("999999999999.99"), 2)

    def test_19_provider_demo_or_sandbox_denied(self):
        for x in ("demo", "test", "sandbox", "not_configured", ""):
            self.assertFalse(valid_provider(x))

    def test_20_provider_event_ids_bounded(self):
        self.assertTrue(valid_provider("named-provider"))
        self.assertTrue(valid_event_id("event_2000:a-1"))
        self.assertFalse(valid_event_id("../unsafe"))
        self.assertFalse(valid_event_id("x" * 101))

    def test_21_explicit_provider_allowlist_only(self):
        self.assertTrue(valid_provider_allowlist(("named-provider",), "named-provider"))
        for x in ((), None, "named-provider", ["demo"], ["named-provider", "demo"]):
            self.assertFalse(valid_provider_allowlist(x, "named-provider"))

    def test_22_provider_reference_requires_real_bounded_value(self):
        self.assertTrue(valid_provider_ref("provider-ref-1"))
        for x in (None, "", "short", 0, "x" * 129, ["bad"]):
            self.assertFalse(valid_provider_ref(x))

    def test_23_amount_decimal_string_only(self):
        self.assertEqual(provider_amount("250.00"), Decimal("250.00"))
        for x in (250, 250.0, "2.5e2", "NaN", "Infinity", "0", "-1"):
            self.assert_rejected(provider_amount, x)

    def test_24_amount_bounds_enforced(self):
        self.assert_rejected(provider_amount, "9999999999999.00")
        self.assert_rejected(provider_amount, "1.001")

    def test_25_ledger_reference_matches_revenue_audit_contract(self):
        result = ledger_reference("named-provider", "evt-A")
        self.assertTrue(result.startswith("payment:"))
        self.assertEqual(len(result), 72)
        self.assertRegex(result, r"^payment:[a-f0-9]{64}$")

    def test_26_distinct_provider_and_event_never_share_reference(self):
        a = ledger_reference("ab-c", "e")
        b = ledger_reference("ab", "c-e")
        self.assertNotEqual(a, b)

    def test_27_same_provider_event_is_idempotent(self):
        self.assertEqual(
            ledger_reference("named-provider", "ev-1"),
            ledger_reference("named-provider", "ev-1"),
        )

    def test_28_invalid_provider_cannot_create_ledger(self):
        self.assert_rejected(ledger_reference, "demo", "evt-1")

    def test_29_bounded_json_object_accepted(self):
        raw = b'{"event_type":"payment.succeeded","payment_intent_id":1}'
        self.assertEqual(parse_strict_webhook_json(raw)["payment_intent_id"], 1)

    def test_30_duplicate_json_key_rejected(self):
        self.assert_rejected(parse_strict_webhook_json, b'{"amount":"1","amount":"2"}')

    def test_31_nan_json_rejected(self):
        self.assert_rejected(parse_strict_webhook_json, b'{"amount":NaN}')

    def test_32_array_json_rejected(self):
        self.assert_rejected(parse_strict_webhook_json, b'[]')

    def test_33_non_utf8_json_rejected(self):
        self.assert_rejected(parse_strict_webhook_json, b'{"x":"\xff"}')

    def test_34_unknown_json_field_rejected(self):
        self.assert_rejected(parse_strict_webhook_json, b'{"buyer_email":"private"}')

    def test_35_oversized_payload_rejected(self):
        self.assert_rejected(parse_strict_webhook_json, b"x" * 16385)

    def test_36_empty_json_body_rejected(self):
        self.assert_rejected(parse_strict_webhook_json, b"")

    def test_37_boolean_json_amount_not_treated_as_money(self):
        value = parse_strict_webhook_json(b'{"amount":true}')["amount"]
        self.assert_rejected(provider_amount, value)

    def test_38_reference_cannot_contain_whitespace_or_unicode(self):
        for x in ("buyer test", "مشتری", "foo\nbar"):
            self.assertFalse(valid_provider_ref(x))


if __name__ == "__main__":
    unittest.main()
