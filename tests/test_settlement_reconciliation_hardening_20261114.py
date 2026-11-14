"""Adversarial revenue-integrity regression pack: no network or customer data."""
import unittest
from dataclasses import replace
from apps.management.settlement_reconciliation import Settlement, reconcile, _money


def receipt(**changes):
    row = Settlement("order-1", "USD", "30.00", "r1", "settled", True, "5.00")
    return replace(row, **changes)


class SettlementHardeningTests(unittest.TestCase):
    # 20 distinct gates with a named executable regression each.
    def test_gate_01_string_false_not_paid(self):
        self.assertEqual(reconcile([receipt(verified="False")], "USD")["confirmed_receipts"], 0)

    def test_gate_02_string_true_not_paid(self):
        self.assertEqual(reconcile([receipt(verified="true")], "USD")["confirmed_receipts"], 0)

    def test_gate_03_integer_one_not_paid(self):
        self.assertEqual(reconcile([receipt(verified=1)], "USD")["confirmed_receipts"], 0)

    def test_gate_04_float_one_not_paid(self):
        self.assertEqual(reconcile([receipt(verified=1.0)], "USD")["confirmed_receipts"], 0)

    def test_gate_05_test_environment_not_paid(self):
        self.assertEqual(reconcile([receipt(environment="test")], "USD")["confirmed_receipts"], 0)

    def test_gate_06_environment_case_change_not_paid(self):
        self.assertEqual(reconcile([receipt(environment="Production")], "USD")["confirmed_receipts"], 0)

    def test_gate_07_status_case_change_not_paid(self):
        self.assertEqual(reconcile([receipt(status="Settled")], "USD")["confirmed_receipts"], 0)

    def test_gate_08_missing_receipt_not_paid(self):
        self.assertEqual(reconcile([receipt(receipt_id="")], "USD")["confirmed_receipts"], 0)

    def test_gate_09_blank_receipt_not_paid(self):
        self.assertEqual(reconcile([receipt(receipt_id="   ")], "USD")["confirmed_receipts"], 0)

    def test_gate_10_missing_order_not_paid(self):
        self.assertEqual(reconcile([receipt(order_id="")], "USD")["confirmed_receipts"], 0)

    def test_gate_11_nonstring_identifiers_not_paid(self):
        self.assertEqual(reconcile([receipt(order_id=22)], "USD")["confirmed_receipts"], 0)

    def test_gate_12_control_characters_not_paid(self):
        self.assertEqual(reconcile([receipt(receipt_id="r\n1")], "USD")["confirmed_receipts"], 0)

    def test_gate_13_overlong_receipt_not_paid(self):
        self.assertEqual(reconcile([receipt(receipt_id="a" * 257)], "USD")["confirmed_receipts"], 0)

    def test_gate_14_duplicate_pending_then_settled_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            reconcile([receipt(status="pending"), receipt()], "USD")

    def test_gate_15_float_money_is_rejected(self):
        with self.assertRaises(ValueError):
            reconcile([receipt(amount=30.0)], "USD")

    def test_gate_16_huge_exponent_is_rejected(self):
        with self.assertRaises(ValueError):
            reconcile([receipt(amount="1e99999999")], "USD")

    def test_gate_17_oversized_integer_is_rejected(self):
        with self.assertRaises(ValueError):
            reconcile([receipt(amount="1" * 31)], "USD")

    def test_gate_18_excess_fractional_precision_is_rejected(self):
        with self.assertRaises(ValueError):
            reconcile([receipt(amount="1." + "1" * 19)], "USD")

    def test_gate_19_currency_whitespace_is_rejected(self):
        with self.assertRaises(ValueError):
            reconcile([receipt()], "USD ")

    def test_gate_20_non_settlement_records_are_rejected(self):
        with self.assertRaises(ValueError):
            reconcile([{"verified": True, "amount": "30"}], "USD")

    def test_split_payments_count_by_unique_receipt_not_order(self):
        summary = reconcile([receipt(), receipt(receipt_id="r2", amount="2", refunded_amount="0")], "USD")
        self.assertEqual(summary["confirmed_receipts"], 2)
        self.assertEqual(summary["net_received"], "27.00")

    def test_trx_and_usdt_codes_supported_separately(self):
        self.assertEqual(reconcile([receipt(currency="TRX")], "TRX")["confirmed_receipts"], 1)
        self.assertEqual(reconcile([receipt(currency="USDT-TRC20")], "USDT-TRC20")["confirmed_receipts"], 1)

    def test_exact_smallest_fractions_without_rounding(self):
        self.assertEqual(_money("0.000001"), _money("0.000001"))
        self.assertEqual(reconcile([receipt(amount="0.000001", refunded_amount="0")], "USD")["net_received"], "0.000001")

    def test_large_amount_and_fraction_retain_exact_precision(self):
        a = "9" * 30 + "." + "1" * 18
        b = "0." + "1" * 18
        result = reconcile([receipt(amount=a, refunded_amount="0"),
                            receipt(receipt_id="r2", amount=b, refunded_amount="0")], "USD")
        self.assertEqual(result["net_received"], "9" * 30 + "." + "2" * 18)

    def test_empty_batch_has_zero_proven_income(self):
        self.assertEqual(reconcile([], "USD")["net_received"], "0")

    def test_non_iterable_input_rejected(self):
        with self.assertRaises(ValueError):
            reconcile(None, "USD")

    def test_record_batch_limit_fail_closed(self):
        row = receipt(receipt_id="not-unique")
        def huge():
            for n in range(100_001):
                yield replace(row, receipt_id="r" + str(n), status="pending")
        with self.assertRaisesRegex(ValueError, "too large"):
            reconcile(huge(), "USD")

    def test_plus_sign_and_surrounding_whitespace_not_accepted(self):
        for x in ("+1", " 1", "1 "):
            with self.subTest(x=x), self.assertRaises(ValueError):
                reconcile([receipt(amount=x)], "USD")

    def test_invalid_refund_input_rejected(self):
        with self.assertRaises(ValueError):
            reconcile([receipt(refunded_amount="nan")], "USD")


if __name__ == "__main__":
    unittest.main()
