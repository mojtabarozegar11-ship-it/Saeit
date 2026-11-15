import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from commercial_revenue_gate import (
    CommercialGateError,
    CommercialState,
    OfferContract,
    OfferType,
    PaymentEvidence,
    SQLiteCommercialLedger,
    transition_state,
    validate_offer,
    validate_payment_evidence,
    validate_signal_request,
)


class CommercialGateTests(unittest.TestCase):
    def offer(self, **changes):
        values = {
            "offer_id": "moj-s04",
            "offer_type": OfferType.MOJ_PROP,
            "tenant_id": "moj_prop",
            "canonical_host": "mojplaywin.com",
            "currency": "TRX",
            "price": Decimal("30"),
        }
        values.update(changes)
        return OfferContract(**values)

    def payment(self, **changes):
        values = {
            "order_id": "order-52",
            "invoice_id": "invoice-52",
            "provider": "manual-review",
            "network": "TRON",
            "asset": "TRX",
            "amount": Decimal("30"),
            "currency": "TRX",
            "transaction_id": "txid-52-verified",
            "chain_finalized": True,
            "amount_matches": True,
            "recipient_matches_private_invoice": True,
            "independently_reconciled": True,
            "human_reviewed": True,
        }
        values.update(changes)
        return PaymentEvidence(**values)

    def test_valid_offer_with_private_manual_gates(self):
        validate_offer(self.offer(), tenant_registry={"moj_prop": "mojplaywin.com"})

    def test_invalid_offer_id_is_rejected(self):
        with self.assertRaisesRegex(CommercialGateError, "offer_id_invalid"):
            validate_offer(self.offer(offer_id="bad id"))

    def test_host_with_scheme_is_rejected(self):
        with self.assertRaisesRegex(CommercialGateError, "canonical_host_invalid"):
            validate_offer(self.offer(canonical_host="https://mojplaywin.com"))

    def test_cross_tenant_scope_is_rejected(self):
        with self.assertRaisesRegex(CommercialGateError, "tenant_scope_mismatch"):
            validate_offer(self.offer(), tenant_registry={"moj_prop": "other.example"})

    def test_public_wallet_is_rejected(self):
        with self.assertRaisesRegex(CommercialGateError, "public_wallet_prohibited"):
            validate_offer(self.offer(public_wallet_published=True))

    def test_automatic_payment_is_rejected(self):
        with self.assertRaisesRegex(CommercialGateError, "automatic_payment_disabled"):
            validate_offer(self.offer(automatic_payment_enabled=True))

    def test_active_prop_requires_all_release_gates(self):
        with self.assertRaisesRegex(CommercialGateError, "moj_prop_release_gates_incomplete"):
            validate_offer(self.offer(active=True, owner_approved=True, rights_cleared=True))

    def test_signal_cannot_enable_financial_calls(self):
        with self.assertRaisesRegex(CommercialGateError, "financial_signal_disabled"):
            validate_offer(self.offer(offer_type=OfferType.SIGNAL, financial_call_enabled=True))

    def test_signal_request_blocks_buy_sell_language(self):
        with self.assertRaisesRegex(CommercialGateError, "financial_signal_disabled"):
            validate_signal_request(requested_action="sell")

    def test_signal_request_allows_research(self):
        validate_signal_request(requested_action="research_summary")

    def test_payment_requires_tron_trx(self):
        with self.assertRaisesRegex(CommercialGateError, "payment_chain_asset_mismatch"):
            validate_payment_evidence(self.payment(asset="USDT"), expected_order_id="order-52", expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")

    def test_payment_requires_matching_order(self):
        with self.assertRaisesRegex(CommercialGateError, "payment_order_mismatch"):
            validate_payment_evidence(self.payment(), expected_order_id="other", expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")

    def test_payment_requires_matching_invoice(self):
        with self.assertRaisesRegex(CommercialGateError, "payment_invoice_mismatch"):
            validate_payment_evidence(self.payment(), expected_order_id="order-52", expected_invoice_id="other", expected_amount=Decimal("30"), expected_currency="TRX")

    def test_payment_requires_matching_amount(self):
        with self.assertRaisesRegex(CommercialGateError, "payment_amount_mismatch"):
            validate_payment_evidence(self.payment(amount=Decimal("29")), expected_order_id="order-52", expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")

    def test_payment_requires_matching_currency(self):
        with self.assertRaisesRegex(CommercialGateError, "payment_currency_mismatch"):
            validate_payment_evidence(self.payment(currency="USD"), expected_order_id="order-52", expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")

    def test_payment_requires_finality_and_manual_review(self):
        with self.assertRaisesRegex(CommercialGateError, "payment_evidence_incomplete"):
            validate_payment_evidence(self.payment(chain_finalized=False), expected_order_id="order-52", expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")

    def test_payment_returns_stable_digest(self):
        first = validate_payment_evidence(self.payment(), expected_order_id="order-52", expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")
        second = validate_payment_evidence(self.payment(), expected_order_id="order-52", expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")
        self.assertEqual(first, second)

    def test_state_cannot_skip_from_ordered_to_settled(self):
        with self.assertRaisesRegex(CommercialGateError, "invalid_state_transition"):
            transition_state(CommercialState.ORDERED, CommercialState.SETTLED, payment_evidence=self.payment())

    def test_settlement_requires_evidence(self):
        with self.assertRaisesRegex(CommercialGateError, "settlement_evidence_required"):
            transition_state(CommercialState.PAYMENT_PENDING, CommercialState.SETTLED)

    def test_fulfillment_requires_manifest_hash(self):
        with self.assertRaisesRegex(CommercialGateError, "fulfillment_manifest_required"):
            transition_state(CommercialState.FULFILLMENT_PENDING, CommercialState.FULFILLED)

    def test_verified_revenue_requires_attestation(self):
        with self.assertRaisesRegex(CommercialGateError, "settlement_evidence_required"):
            transition_state(CommercialState.FULFILLED, CommercialState.VERIFIED_REVENUE)

    def test_sqlite_ledger_persists_order_and_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "ledger.sqlite3")
            ledger = SQLiteCommercialLedger(path)
            ledger.create_order(order_id="order-52", offer_id="moj-s04", amount=Decimal("30"), currency="TRX")
            self.assertEqual(ledger.snapshot("order-52")["state"], "ordered")
            ledger.close()
            reopened = SQLiteCommercialLedger(path)
            self.assertEqual(reopened.snapshot("order-52")["offer_id"], "moj-s04")
            reopened.close()

    def test_sqlite_ledger_rejects_duplicate_order(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            kwargs = {"order_id": "order-52", "offer_id": "moj-s04", "amount": Decimal("30"), "currency": "TRX"}
            ledger.create_order(**kwargs)
            with self.assertRaisesRegex(CommercialGateError, "order_already_exists"):
                ledger.create_order(**kwargs)
            ledger.close()

    def test_sqlite_ledger_rejects_replay_with_changed_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04", amount=Decimal("30"), currency="TRX")
            ledger.advance(order_id="order-52", target=CommercialState.QUOTED, event_id="quote-52", payload_digest="a" * 64)
            with self.assertRaisesRegex(CommercialGateError, "event_replay_mismatch"):
                ledger.advance(order_id="order-52", target=CommercialState.SETTLED, event_id="quote-52", payload_digest="b" * 64, payment_evidence=self.payment())
            ledger.close()

    def test_sqlite_ledger_rejects_cross_order_event_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04", amount=Decimal("30"), currency="TRX")
            ledger.create_order(order_id="order-53", offer_id="moj-s04", amount=Decimal("30"), currency="TRX")
            ledger.advance(order_id="order-52", target=CommercialState.QUOTED, event_id="shared-event", payload_digest="a" * 64)
            with self.assertRaisesRegex(CommercialGateError, "event_replay_order_mismatch"):
                ledger.advance(order_id="order-53", target=CommercialState.QUOTED, event_id="shared-event", payload_digest="a" * 64)
            self.assertEqual(ledger.snapshot("order-53")["state"], "ordered")
            ledger.close()


    def test_transition_rejects_non_boolean_evidence_flags(self):
        with self.assertRaisesRegex(CommercialGateError, "payment_evidence_incomplete"):
            validate_payment_evidence(
                self.payment(chain_finalized="true"),
                expected_order_id="order-52",
                expected_invoice_id="invoice-52",
                expected_amount=Decimal("30"),
                expected_currency="TRX",
            )

    def test_settlement_rejects_incomplete_evidence_object(self):
        with self.assertRaisesRegex(CommercialGateError, "payment_evidence_incomplete"):
            transition_state(
                CommercialState.PAYMENT_PENDING,
                CommercialState.SETTLED,
                payment_evidence=self.payment(human_reviewed=False),
            )

    def test_verified_revenue_requires_settlement_evidence(self):
        with self.assertRaisesRegex(CommercialGateError, "settlement_evidence_required"):
            transition_state(
                CommercialState.FULFILLED,
                CommercialState.VERIFIED_REVENUE,
                verified_revenue=True,
            )

    def test_verified_revenue_rejects_incomplete_evidence(self):
        with self.assertRaisesRegex(CommercialGateError, "payment_evidence_incomplete"):
            transition_state(
                CommercialState.FULFILLED,
                CommercialState.VERIFIED_REVENUE,
                payment_evidence=self.payment(chain_finalized=False),
                verified_revenue=True,
            )

    def test_sqlite_settlement_rejects_wrong_order_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(
                order_id="order-52", offer_id="moj-s04",
                amount=Decimal("30"), currency="TRX",
            )
            with self.assertRaisesRegex(CommercialGateError, "payment_order_mismatch"):
                ledger.advance(
                    order_id="order-52",
                    target=CommercialState.SETTLED,
                    event_id="settle-52",
                    payload_digest="a" * 64,
                    payment_evidence=self.payment(order_id="other-order"),
                )
            ledger.close()

    def test_sqlite_settlement_rejects_wrong_amount_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(
                order_id="order-52", offer_id="moj-s04",
                amount=Decimal("30"), currency="TRX",
            )
            with self.assertRaisesRegex(CommercialGateError, "payment_amount_mismatch"):
                ledger.advance(
                    order_id="order-52",
                    target=CommercialState.SETTLED,
                    event_id="settle-52",
                    payload_digest="a" * 64,
                    payment_evidence=self.payment(amount=Decimal("29")),
                )
            ledger.close()

    def test_sqlite_settlement_rejects_wrong_currency_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(
                order_id="order-52", offer_id="moj-s04",
                amount=Decimal("30"), currency="TRX",
            )
            with self.assertRaisesRegex(CommercialGateError, "payment_currency_mismatch"):
                ledger.advance(
                    order_id="order-52",
                    target=CommercialState.SETTLED,
                    event_id="settle-52",
                    payload_digest="a" * 64,
                    payment_evidence=self.payment(currency="USD"),
                )
            ledger.close()

    def test_sqlite_settlement_requires_evidence_digest_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(
                order_id="order-52", offer_id="moj-s04",
                amount=Decimal("30"), currency="TRX",
            )
            with self.assertRaisesRegex(CommercialGateError, "settlement_payload_mismatch"):
                ledger.advance(
                    order_id="order-52",
                    target=CommercialState.SETTLED,
                    event_id="settle-52",
                    payload_digest="a" * 64,
                    payment_evidence=self.payment(),
                )
            ledger.close()

    def test_sqlite_verified_revenue_requires_evidence_again(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(
                order_id="order-52", offer_id="moj-s04",
                amount=Decimal("30"), currency="TRX",
            )
            for target, event in (
                (CommercialState.QUOTED, "quote-52"),
                (CommercialState.INVOICED, "invoice-52"),
                (CommercialState.PAYMENT_PENDING, "pending-52"),
            ):
                ledger.advance(
                    order_id="order-52", target=target,
                    event_id=event, payload_digest=("a" * 64),
                )
            evidence = self.payment()
            from commercial_revenue_gate import validate_payment_evidence
            digest = validate_payment_evidence(
                evidence, expected_order_id="order-52",
                expected_invoice_id="invoice-52",
                expected_amount=Decimal("30"), expected_currency="TRX",
            )
            ledger.advance(
                order_id="order-52", target=CommercialState.SETTLED,
                event_id="settle-52", payload_digest=digest,
                payment_evidence=evidence,
            )
            ledger.advance(
                order_id="order-52", target=CommercialState.FULFILLMENT_PENDING,
                event_id="fulfill-pending-52", payload_digest="b" * 64,
            )
            ledger.advance(
                order_id="order-52", target=CommercialState.FULFILLED,
                event_id="fulfilled-52", payload_digest="c" * 64,
                fulfillment_manifest_sha256="d" * 64,
            )
            with self.assertRaisesRegex(CommercialGateError, "settlement_evidence_required"):
                ledger.advance(
                    order_id="order-52",
                    target=CommercialState.VERIFIED_REVENUE,
                    event_id="verified-52",
                    payload_digest="e" * 64,
                    verified_revenue=True,
                )
            ledger.close()

    def test_sqlite_ledger_deduplicates_identical_event(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04", amount=Decimal("30"), currency="TRX")
            first = ledger.advance(order_id="order-52", target=CommercialState.QUOTED, event_id="quote-52", payload_digest="a" * 64)
            second = ledger.advance(order_id="order-52", target=CommercialState.SETTLED, event_id="quote-52", payload_digest="a" * 64, payment_evidence=self.payment())
            self.assertEqual(first, second)
            self.assertEqual(ledger.snapshot("order-52")["state"], "quoted")
            ledger.close()


if __name__ == "__main__":
    unittest.main()

