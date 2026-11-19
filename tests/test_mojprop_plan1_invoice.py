"""Tests for the fail-closed real MOJ-PROP-01 invoice contract."""
from datetime import datetime, timedelta, timezone
import unittest

from services.mojprop_plan1_invoice import (
    AMOUNT_SUN, CONTRACT_VERSION, InvoiceReleaseDenied, RELEASE_GATES,
    assess_release, issue_plan1_invoice,
)

OWNER = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"
START = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


def good_attestations():
    return {key: True for key in RELEASE_GATES}


class Plan1InvoiceContractTests(unittest.TestCase):
    def good_decision(self):
        return assess_release(
            attestations=good_attestations(),
            owner_declared_active=True,
            independent_capital_proof=True,
            protected_recipient=OWNER,
            route_registered=True,
        )

    def test_exact_30_trx_amount_is_immutable(self):
        invoice = issue_plan1_invoice(
            decision=self.good_decision(), email="buyer@example.com",
            order_ref="MOJPROP01-ABCDEF123456", recipient=OWNER,
            issued_at=START, expires_at=START + timedelta(hours=1),
            buyer_terms_acceptance="terms-accepted-1",
            contract_sha256="a" * 64,
        )
        self.assertEqual(invoice.amount_sun, AMOUNT_SUN)
        self.assertEqual(invoice.contract_version, CONTRACT_VERSION)

    def test_any_missing_independent_gate_blocks_invoice(self):
        for key in RELEASE_GATES:
            with self.subTest(key=key):
                gates = good_attestations()
                gates[key] = False
                result = assess_release(
                    attestations=gates, owner_declared_active=True,
                    independent_capital_proof=True, protected_recipient=OWNER,
                    route_registered=True)
                self.assertFalse(result.invoice_enabled)
                self.assertIn(key, result.blockers)

    def test_owner_flag_does_not_replace_independent_capital_proof(self):
        result = assess_release(
            attestations=good_attestations(), owner_declared_active=True,
            independent_capital_proof=False, protected_recipient=OWNER,
            route_registered=True)
        self.assertFalse(result.invoice_enabled)
        self.assertIn("independent_plan1_capital_proof_missing", result.blockers)

    def test_invalid_recipient_blocks_release(self):
        result = assess_release(
            attestations=good_attestations(), owner_declared_active=True,
            independent_capital_proof=True, protected_recipient="Tinvalid",
            route_registered=True)
        self.assertFalse(result.invoice_enabled)

    def test_invoice_requires_aware_bounded_times(self):
        with self.assertRaises(InvoiceReleaseDenied):
            issue_plan1_invoice(
                decision=self.good_decision(), email="buyer@example.com",
                order_ref="MOJPROP01-ABCDEF123456", recipient=OWNER,
                issued_at=START, expires_at=START + timedelta(days=2),
                buyer_terms_acceptance="terms-accepted-1",
                contract_sha256="a" * 64,
            )

    def test_email_order_and_contract_are_bound(self):
        for field, value in (
            ("email", "not-an-email"), ("order_ref", "MOJPROP01-../../"),
            ("contract_sha256", "not-a-digest"),
        ):
            kwargs = dict(
                decision=self.good_decision(), email="buyer@example.com",
                order_ref="MOJPROP01-ABCDEF123456", recipient=OWNER,
                issued_at=START, expires_at=START + timedelta(hours=1),
                buyer_terms_acceptance="terms-accepted-1",
                contract_sha256="a" * 64,
            )
            kwargs[field] = value
            with self.subTest(field=field), self.assertRaises(InvoiceReleaseDenied):
                issue_plan1_invoice(**kwargs)

    def test_disabled_decision_cannot_be_overridden_by_payload(self):
        result = assess_release(
            attestations=good_attestations(), owner_declared_active=True,
            independent_capital_proof=True, protected_recipient=OWNER,
            route_registered=False)
        with self.assertRaises(InvoiceReleaseDenied):
            issue_plan1_invoice(
                decision=result, email="buyer@example.com",
                order_ref="MOJPROP01-ABCDEF123456", recipient=OWNER,
                issued_at=START, expires_at=START + timedelta(hours=1),
                buyer_terms_acceptance="terms-accepted-1",
                contract_sha256="a" * 64,
            )


if __name__ == "__main__":
    unittest.main()
