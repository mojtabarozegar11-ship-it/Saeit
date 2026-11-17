"""Real-source, offline proof that a Moj Prop quote is not payment or fake acceptance.

No Django, mail, blockchain, customer database, or production mutation.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
import unittest

from core.mojprop_quote_contract import (
    QuoteContractError, make_quote_snapshot, validate_acceptance_reference,
)


class QuoteEvidenceBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
        self.base = dict(
            lead=SimpleNamespace(request_id="MOJPROP-20261115-QUOTEB"),
            status="issued", version=1, title="Agricultural economics review",
            scope="Economic assessment based on dated sources, modeled expenses, "
                  "scenario assumptions and explicit customer-facing limitations.",
            exclusions="Third party costs and live market execution excluded.",
            amount=Decimal("125.00"), currency="USD", delivery_days=7,
            reviewed_at=self.now - timedelta(hours=2),
            issued_at=self.now - timedelta(hours=1),
            expires_at=self.now + timedelta(days=4),
            accepted_at=None, acceptance_reference="",
        )

    def snapshot(self, **patches):
        return make_quote_snapshot(
            SimpleNamespace(**{**self.base, **patches}), now=self.now
        )

    def reject(self, **patches):
        with self.assertRaises(QuoteContractError):
            self.snapshot(**patches)

    def test_01_valid_issued_quote_has_no_payment_claim(self):
        data = self.snapshot()
        self.assertEqual(data["amount"], "125.00")
        self.assertFalse(data["payable"])
        self.assertEqual(data["payment_status"], "not_collected")

    def test_02_valid_accepted_quote_requires_past_consent(self):
        data = self.snapshot(
            status="accepted",
            accepted_at=self.now - timedelta(minutes=5),
            acceptance_reference="buyer-signature:2026-11-15",
        )
        self.assertEqual(data["status"], "accepted")

    def test_03_future_customer_acceptance_is_rejected(self):
        self.reject(
            status="accepted", accepted_at=self.now + timedelta(seconds=1),
            acceptance_reference="buyer-signature:future",
        )

    def test_04_future_acceptance_at_expiry_is_rejected(self):
        self.reject(
            status="accepted", accepted_at=self.base["expires_at"],
            acceptance_reference="buyer-signature:future",
        )

    def test_05_accepted_quote_without_timestamp_rejected(self):
        self.reject(status="accepted", acceptance_reference="buyer-signature:missing")

    def test_06_accepted_quote_without_evidence_rejected(self):
        self.reject(status="accepted", accepted_at=self.now - timedelta(minutes=1))

    def test_07_accepted_quote_before_issue_rejected(self):
        self.reject(
            status="accepted",
            accepted_at=self.base["issued_at"] - timedelta(seconds=1),
            acceptance_reference="buyer-signature:early",
        )

    def test_08_accepted_quote_at_issue_allowed(self):
        result = self.snapshot(
            status="accepted", accepted_at=self.base["issued_at"],
            acceptance_reference="buyer-signature:same-time",
        )
        self.assertEqual(result["status"], "accepted")

    def test_09_accepted_quote_at_now_allowed(self):
        result = self.snapshot(
            status="accepted", accepted_at=self.now,
            acceptance_reference="buyer-signature:just-now",
        )
        self.assertEqual(result["status"], "accepted")

    def test_10_issued_quote_cannot_hold_acceptance_reference(self):
        self.reject(acceptance_reference="signed-but-not-accepted")

    def test_11_issued_quote_cannot_hold_acceptance_timestamp(self):
        self.reject(accepted_at=self.now - timedelta(minutes=1))

    def test_12_currency_list_rejected_as_domain_error(self):
        self.reject(currency=["USD"])

    def test_13_currency_dict_rejected_as_domain_error(self):
        self.reject(currency={"USD": True})

    def test_14_currency_number_rejected(self):
        self.reject(currency=3)

    def test_15_currency_bool_rejected(self):
        self.reject(currency=True)

    def test_16_supported_irr_currency_still_allowed(self):
        self.assertEqual(self.snapshot(currency="IRR")["currency"], "IRR")

    def test_17_exact_max_twelve_digit_amount_allowed(self):
        self.assertEqual(
            self.snapshot(amount=Decimal("9999999999.99"))["amount"],
            "9999999999.99",
        )

    def test_18_amount_one_cent_over_database_limit_rejected(self):
        self.reject(amount=Decimal("10000000000.00"))

    def test_19_giant_decimal_exponent_rejected_cleanly(self):
        self.reject(amount=Decimal("1E+1000000"))

    def test_20_tiny_fractional_cent_rejected(self):
        self.reject(amount=Decimal("0.0000001"))

    def test_21_amount_more_than_two_decimal_places_rejected(self):
        self.reject(amount=Decimal("125.001"))

    def test_22_decimal_nan_rejected(self):
        self.reject(amount=Decimal("NaN"))

    def test_23_decimal_infinity_rejected(self):
        self.reject(amount=Decimal("Infinity"))

    def test_24_decimal_negative_infinity_rejected(self):
        self.reject(amount=Decimal("-Infinity"))

    def test_25_non_decimal_amount_rejected(self):
        self.reject(amount=125.0)

    def test_26_bidi_override_cannot_fake_acceptance_evidence(self):
        with self.assertRaises(QuoteContractError):
            validate_acceptance_reference("buyer-" + chr(0x202E) + "approved")

    def test_27_bidi_isolate_cannot_fake_acceptance_evidence(self):
        with self.assertRaises(QuoteContractError):
            validate_acceptance_reference("buyer-" + chr(0x2066) + "approved")

    def test_28_terminal_del_control_rejected_in_evidence(self):
        with self.assertRaises(QuoteContractError):
            validate_acceptance_reference("buyer-" + chr(0x7F) + "approved")

    def test_29_c1_control_rejected_in_evidence(self):
        with self.assertRaises(QuoteContractError):
            validate_acceptance_reference("buyer-" + chr(0x85) + "approved")

    def test_30_persian_acceptance_text_remains_allowed(self):
        self.assertEqual(
            validate_acceptance_reference("پذیرش خریدار: ۱۴۰۵/۰۸/۲۴"),
            "پذیرش خریدار: ۱۴۰۵/۰۸/۲۴",
        )

    def test_31_valid_offer_never_claims_revenue(self):
        data = self.snapshot()
        self.assertEqual(data["revenue_status"], "not_received")
        self.assertEqual(data["delivery_status"], "not_delivered")

    def test_32_future_issuance_rejected(self):
        self.reject(issued_at=self.now + timedelta(seconds=1))

    def test_33_expired_quote_rejected(self):
        self.reject(expires_at=self.now)

    def test_34_naive_acceptance_timestamp_rejected(self):
        self.reject(
            status="accepted", accepted_at=datetime(2026, 11, 15, 11, 59),
            acceptance_reference="buyer-signature:naive",
        )

    def test_35_valid_signed_reference_is_normalized(self):
        self.assertEqual(
            validate_acceptance_reference("  buyer-confirmed-2026  "),
            "buyer-confirmed-2026",
        )


    def test_36_title_cannot_inject_fake_payment_line(self):
        self.reject(title="Budget planning\nPayment received: yes")

    def test_37_title_cannot_inject_fake_receipt_with_tab(self):
        self.reject(title="Budget planning\tPAID RECEIPT")

    def test_38_unicode_line_separator_cannot_spoof_title(self):
        self.reject(title="Budget planning" + chr(0x2028) + "Payment received")

    def test_39_unicode_paragraph_separator_cannot_spoof_title(self):
        self.reject(title="Budget planning" + chr(0x2029) + "Delivery complete")

    def test_40_regular_persian_single_line_title_remains_valid(self):
        self.assertEqual(
            self.snapshot(title="بررسی اقتصادی هزینه تولید")["title"],
            "بررسی اقتصادی هزینه تولید",
        )


if __name__ == "__main__":
    unittest.main()
