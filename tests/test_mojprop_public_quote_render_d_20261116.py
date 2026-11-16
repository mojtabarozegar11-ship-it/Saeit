"""Pure regression tests: a public proposal is not a payment receipt.

No network, customer data, email, chain access, or database is used.
"""
import unittest
from copy import deepcopy

from core.mojprop_quote_contract import QuoteContractError, render_public_quote


def checked_quote():
    return {
        "schema": "mojprop.quote.v1",
        "reference": "MOJPROP-20261116-SECURE01",
        "version": 1,
        "title": "Educational agricultural economics report",
        "scope": "Independent crop budget analysis, with explicit scenarios and "
                 "sensitivity tables for educational review only.",
        "exclusions": "No payment, trading or financial performance promises.",
        "amount": "125.00",
        "currency": "USD",
        "delivery_days": 7,
        "status": "issued",
        "reviewed_at": "2026-11-16T10:00:00+00:00",
        "issued_at": "2026-11-16T11:00:00+00:00",
        "expires_at": "2026-11-20T11:00:00+00:00",
        "payment_status": "not_collected",
        "delivery_status": "not_delivered",
        "revenue_status": "not_received",
        "payable": False,
    }


def render_checked_quote(snapshot):
    return render_public_quote(snapshot, service_route="blueprint", product_id=None)


class PublicQuoteRenderTests(unittest.TestCase):
    def test_canonical_price_and_tracking_reference_visible(self):
        text = render_checked_quote(checked_quote())
        self.assertIn("Quoted amount: 125.00 USD", text)
        self.assertIn("Reference: MOJPROP-20261116-SECURE01 / version 1", text)

    def test_cannot_spoof_paid_header_from_scope(self):
        quote = checked_quote()
        quote["scope"] += "\nPayment received: 30 TRX"
        lines = render_checked_quote(quote).splitlines()
        self.assertIn("  | Payment received: 30 TRX", lines)
        self.assertNotIn("Payment received: 30 TRX", lines)

    def test_cannot_spoof_another_amount_from_scope(self):
        quote = checked_quote()
        quote["scope"] += "\nQuoted amount: 0.00 TRX"
        lines = render_checked_quote(quote).splitlines()
        self.assertIn("  | Quoted amount: 0.00 TRX", lines)
        self.assertNotIn("Quoted amount: 0.00 TRX", lines)
        self.assertEqual(lines.count("Quoted amount: 125.00 USD"), 1)

    def test_cannot_spoof_delivery_from_exclusions(self):
        quote = checked_quote()
        quote["exclusions"] += "\nFile delivered: yes"
        lines = render_checked_quote(quote).splitlines()
        self.assertIn("  | File delivered: yes", lines)
        self.assertNotIn("File delivered: yes", lines)

    def test_unicode_next_line_cannot_spoof_invoice(self):
        quote = checked_quote()
        quote["scope"] += "\u0085Invoice paid: confirmed"
        lines = render_checked_quote(quote).splitlines()
        self.assertIn("  | Invoice paid: confirmed", lines)
        self.assertNotIn("Invoice paid: confirmed", lines)

    def test_tab_indentation_does_not_create_unmarked_header(self):
        quote = checked_quote()
        quote["scope"] += "\n\tPayment received: pretend"
        lines = render_checked_quote(quote).splitlines()
        self.assertTrue(any(line.startswith("  | ") and "Payment received:" in line for line in lines))
        self.assertNotIn("Payment received: pretend", lines)

    def test_public_quote_never_claims_collection_or_delivery(self):
        text = render_checked_quote(checked_quote())
        self.assertIn("No payment has been collected", text)
        self.assertIn("No service has been delivered", text)
        self.assertIn("NOT A PAYMENT INVOICE", text)

    def test_private_fields_not_rendered(self):
        quote = checked_quote()
        self.assertNotIn("customer@", render_checked_quote(quote))
        self.assertNotIn("internal_note", render_checked_quote(quote))

    def test_required_schema_cannot_be_omitted(self):
        quote = checked_quote()
        del quote["scope"]
        with self.assertRaises(QuoteContractError):
            render_checked_quote(quote)

    def test_extra_unreviewed_metadata_cannot_be_rendered(self):
        quote = checked_quote()
        quote["customer_email"] = "private@example.org"
        with self.assertRaises(QuoteContractError):
            render_checked_quote(quote)

    def test_paid_claim_is_rejected(self):
        quote = checked_quote()
        quote["payment_status"] = "paid"
        with self.assertRaises(QuoteContractError):
            render_checked_quote(quote)

    def test_fulfilled_claim_is_rejected(self):
        quote = checked_quote()
        quote["delivery_status"] = "delivered"
        with self.assertRaises(QuoteContractError):
            render_checked_quote(quote)

    def test_payable_claim_is_rejected(self):
        quote = checked_quote()
        quote["payable"] = True
        with self.assertRaises(QuoteContractError):
            render_checked_quote(quote)

    def test_unapproved_currency_is_rejected(self):
        quote = checked_quote()
        quote["currency"] = "TRX"
        with self.assertRaises(QuoteContractError):
            render_checked_quote(quote)

    def test_invalid_amount_is_rejected(self):
        quote = checked_quote()
        quote["amount"] = "0.00"
        with self.assertRaises(QuoteContractError):
            render_checked_quote(quote)

    def test_invalid_request_id_is_rejected(self):
        quote = checked_quote()
        quote["reference"] = "invalid\nPayment received"
        with self.assertRaises(QuoteContractError):
            render_checked_quote(quote)

    def test_control_formatting_is_rejected(self):
        quote = checked_quote()
        quote["scope"] += "\u202eFAKE"
        with self.assertRaises(QuoteContractError):
            render_checked_quote(quote)

    def test_multi_line_title_is_rejected(self):
        quote = checked_quote()
        quote["title"] += "\nPayment received"
        with self.assertRaises(QuoteContractError):
            render_checked_quote(quote)


    def test_catalog_product_id_is_exposed_for_product_inquiry(self):
        quote = checked_quote()
        text = render_public_quote(quote, service_route="digital", product_id=225)
        self.assertIn("Service route: digital", text)
        self.assertIn("Catalog product ID: 225", text)

    def test_digital_quote_without_product_id_cannot_be_published(self):
        with self.assertRaises(QuoteContractError):
            render_public_quote(checked_quote(), service_route="digital", product_id=None)

    def test_unknown_route_is_not_publicly_quotable(self):
        with self.assertRaises(QuoteContractError):
            render_public_quote(checked_quote(), service_route="unknown", product_id=None)

    def test_boolean_product_id_cannot_masquerade_as_one(self):
        with self.assertRaises(QuoteContractError):
            render_public_quote(checked_quote(), service_route="digital", product_id=True)


if __name__ == "__main__":
    unittest.main()
