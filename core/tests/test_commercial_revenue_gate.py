import tempfile
import sqlite3
import unittest
from decimal import Decimal, localcontext
from pathlib import Path
from unittest.mock import patch

from core.commercial_revenue_gate import (
    CommercialGateError,
    CommercialState,
    OfferContract,
    OfferType,
    PaymentEvidence,
    ConfirmedRefund,
    SQLiteCommercialLedger,
    transition_state,
    validate_offer,
    validate_payment_evidence,
    validate_signal_request,
    authorize_nonfinancial_signal_dispatch,
    validate_merchant_trx_receipt,
    invoice_commitment,
)


class CommercialGateTests(unittest.TestCase):
    def _offline_ledger(self, path):
        # Explicitly synthetic fixtures; never use these adapters in production.
        return SQLiteCommercialLedger(path, settlement_verifier=lambda _: True,
                                      delivery_verifier=lambda order, manifest: True,
                                      accepted_scope_verifier=lambda order: True)

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
            "transaction_id": "a" * 64,
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

    def test_malformed_domain_labels_are_rejected(self):
        for host in ("mojplaywin..com", "-mojplaywin.com", "mojplaywin-.com",
                     "mojplaywin.com.", ".mojplaywin.com", "localhost", "mojplaywin.c_m"):
            with self.subTest(host=host):
                with self.assertRaisesRegex(CommercialGateError, "canonical_host_invalid"):
                    validate_offer(self.offer(canonical_host=host))

    def test_personal_social_identity_cannot_serve_as_merchant_domain(self):
        with self.assertRaisesRegex(CommercialGateError, "canonical_host_invalid"):
            validate_offer(self.offer(canonical_host="dr.mojtaba.rozegar"))

    def test_valid_subdomain_remains_supported_for_authorized_tenant(self):
        validate_offer(self.offer(canonical_host="shop.mojplaywin.com"),
                       tenant_registry={"moj_prop": "shop.mojplaywin.com"})

    def test_cross_tenant_scope_is_rejected(self):
        with self.assertRaisesRegex(CommercialGateError, "tenant_scope_mismatch"):
            validate_offer(self.offer(), tenant_registry={"moj_prop": "other.example"})

    def test_trx_offer_price_rejects_fractional_sun(self):
        with self.assertRaisesRegex(CommercialGateError, "trx_fractional_sun_forbidden"):
            validate_offer(self.offer(price=Decimal("0.0000001")))

    def test_native_trx_one_sun_remains_valid(self):
        validate_offer(self.offer(price=Decimal("0.000001")))

    def test_trx_payment_evidence_rejects_fractional_sun(self):
        with self.assertRaisesRegex(CommercialGateError, "trx_fractional_sun_forbidden"):
            validate_payment_evidence(
                self.payment(amount=Decimal("0.0000001")),
                expected_order_id="order-52", expected_invoice_id="invoice-52",
                expected_amount=Decimal("0.0000001"), expected_currency="TRX",
            )

    def test_trx_order_rejects_fractional_sun_before_persisting(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            try:
                with self.assertRaisesRegex(CommercialGateError, "trx_fractional_sun_forbidden"):
                    ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                        amount=Decimal("0.0000001"), currency="TRX")
                with self.assertRaisesRegex(CommercialGateError, "order_not_found"):
                    ledger.snapshot("order-52")
            finally:
                ledger.close()

    def test_public_wallet_is_rejected(self):
        with self.assertRaisesRegex(CommercialGateError, "public_wallet_prohibited"):
            validate_offer(self.offer(public_wallet_published=True))

    def test_automatic_payment_is_rejected(self):
        with self.assertRaisesRegex(CommercialGateError, "automatic_payment_disabled"):
            validate_offer(self.offer(automatic_payment_enabled=True))

    def test_active_prop_requires_all_release_gates(self):
        with self.assertRaisesRegex(CommercialGateError, "moj_prop_release_gates_incomplete"):
            validate_offer(self.offer(active=True, owner_approved=True, rights_cleared=True))

    def test_active_non_prop_service_requires_legal_kyc_and_rights(self):
        for service in (OfferType.SIGNAL, OfferType.TRX_GATEWAY,
                        OfferType.DIGITAL_PRODUCT, OfferType.GAME):
            with self.subTest(service=service):
                with self.assertRaisesRegex(CommercialGateError, "offer_release_gates_incomplete"):
                    validate_offer(self.offer(offer_type=service, active=True,
                                              owner_approved=True))

    def test_active_non_prop_service_can_pass_source_validation_with_all_gates(self):
        validate_offer(self.offer(
            offer_type=OfferType.DIGITAL_PRODUCT, active=True,
            owner_approved=True, legal_reviewed=True,
            kyc_ready=True, rights_cleared=True,
            delivery_manifest_sha256="a" * 64,
        ), tenant_registry={"moj_prop": "mojplaywin.com"},
           independent_release_verifier=lambda offer: True)

    def test_active_digital_or_game_offer_requires_file_manifest(self):
        for service in (OfferType.DIGITAL_PRODUCT, OfferType.GAME):
            with self.subTest(service=service):
                with self.assertRaisesRegex(CommercialGateError,
                                            "active_digital_delivery_manifest_required"):
                    validate_offer(self.offer(
                        offer_type=service, active=True,
                        owner_approved=True, legal_reviewed=True,
                        kyc_ready=True, rights_cleared=True,
                    ), tenant_registry={"moj_prop": "mojplaywin.com"})

    def test_active_offer_without_domain_registry_is_blocked(self):
        with self.assertRaisesRegex(CommercialGateError, "tenant_registry_required_for_activation"):
            validate_offer(self.offer(
                active=True, owner_approved=True, legal_reviewed=True,
                kyc_ready=True, rights_cleared=True,
            ))

    def test_active_offer_cross_tenant_host_is_blocked(self):
        with self.assertRaisesRegex(CommercialGateError, "tenant_scope_mismatch"):
            validate_offer(self.offer(
                active=True, owner_approved=True, legal_reviewed=True,
                kyc_ready=True, rights_cleared=True,
            ), tenant_registry={"moj_prop": "other.example"})

    def test_string_boolean_gate_spoofing_is_rejected(self):
        for field in ("active", "owner_approved", "legal_reviewed",
                      "kyc_ready", "rights_cleared",
                      "public_wallet_published", "automatic_payment_enabled"):
            with self.subTest(field=field):
                with self.assertRaisesRegex(CommercialGateError, "offer_gates_must_be_boolean"):
                    validate_offer(self.offer(**{field: "false"}))

    def test_signal_cannot_enable_financial_calls(self):
        with self.assertRaisesRegex(CommercialGateError, "financial_signal_disabled"):
            validate_offer(self.offer(offer_type=OfferType.SIGNAL, financial_call_enabled=True))

    def test_signal_request_blocks_buy_sell_language(self):
        with self.assertRaisesRegex(CommercialGateError, "financial_signal_disabled"):
            validate_signal_request(requested_action="sell")

    def test_signal_request_blocks_embedded_trade_instruction(self):
        for action in ("buy BTC", "please SELL trx", "trade:TRX", "long_position"):
            with self.subTest(action=action):
                with self.assertRaisesRegex(CommercialGateError, "financial_signal_disabled"):
                    validate_signal_request(requested_action=action)

    def test_signal_request_allows_research(self):
        validate_signal_request(requested_action="research_summary")

    def test_nonfinancial_signal_service_codes_are_explicit(self):
        for action in ("research_summary", "operational_alert",
                       "agricultural_cost_report", "service_quality_report"):
            with self.subTest(action=action):
                validate_signal_request(requested_action=action)

    def test_financial_signal_syntax_evasions_are_denied(self):
        for action in ("BUYBTC", "buy_btc", "forex_signal", "خرید بیت کوین",
                       "شراء بيتكوين", "sellNow", "buy signal", "RESEARCH_SUMMARY"):
            with self.subTest(action=action):
                with self.assertRaisesRegex(CommercialGateError, "financial_signal_disabled"):
                    validate_signal_request(requested_action=action)

    def test_truthy_nonboolean_financial_authorization_rejected(self):
        with self.assertRaisesRegex(CommercialGateError, "financial_signal_disabled"):
            validate_signal_request(requested_action="research_summary",
                                    financial_authorized="false")

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
            ledger = self._offline_ledger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(
                order_id="order-52", offer_id="moj-s04",
                amount=Decimal("30"), currency="TRX",
            )
            for target, event in (
                (CommercialState.QUOTED, "quote-52"),
                (CommercialState.INVOICED, "invoice-52"),
                (CommercialState.PAYMENT_PENDING, "pending-52"),
            ):
                digest_for_step = invoice_commitment(
                    order_id="order-52", invoice_id="invoice-52",
                    amount=Decimal("30"), currency="TRX",
                ) if target is CommercialState.INVOICED else "a" * 64
                ledger.advance(
                    order_id="order-52", target=target,
                    event_id=event, payload_digest=digest_for_step,
                )
            ledger.bind_issued_invoice(
                order_id="order-52", invoice_id="invoice-52",
                payload_digest=invoice_commitment(
                    order_id="order-52", invoice_id="invoice-52",
                    amount=Decimal("30"), currency="TRX",
                ),
            )
            evidence = self.payment()
            # Use the same package-qualified import as the test module.
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
                event_id="fulfilled-52", payload_digest="d" * 64,
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
            second = ledger.advance(order_id="order-52", target=CommercialState.QUOTED, event_id="quote-52", payload_digest="a" * 64)
            self.assertEqual(first, second)
            with self.assertRaisesRegex(CommercialGateError, "stale_event_replay"):
                ledger.advance(order_id="order-52", target=CommercialState.SETTLED, event_id="quote-52", payload_digest="a" * 64, payment_evidence=self.payment())
            self.assertEqual(ledger.snapshot("order-52")["state"], "quoted")
            ledger.close()


    def test_tron_transaction_cannot_settle_two_orders(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._offline_ledger(str(Path(directory) / "ledger.sqlite3"))
            for order_id in ("order-52", "order-53"):
                ledger.create_order(order_id=order_id, offer_id="moj-s04", amount=Decimal("30"), currency="TRX")
                for state, prefix in ((CommercialState.QUOTED, "quote"),
                                      (CommercialState.INVOICED, "invoice"),
                                      (CommercialState.PAYMENT_PENDING, "pending")):
                    step_digest = invoice_commitment(
                        order_id=order_id, invoice_id="invoice-" + order_id.split("-")[1],
                        amount=Decimal("30"), currency="TRX",
                    ) if state is CommercialState.INVOICED else "a" * 64
                    ledger.advance(order_id=order_id, target=state,
                                   event_id=f"{prefix}-{order_id}", payload_digest=step_digest)
                ledger.bind_issued_invoice(
                    order_id=order_id, invoice_id="invoice-" + order_id.split("-")[1],
                    payload_digest=invoice_commitment(
                        order_id=order_id, invoice_id="invoice-" + order_id.split("-")[1],
                        amount=Decimal("30"), currency="TRX",
                    ),
                )
            first = self.payment()
            digest1 = validate_payment_evidence(first, expected_order_id="order-52",
                expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")
            ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                           event_id="settle-52", payload_digest=digest1, payment_evidence=first)
            second = self.payment(order_id="order-53", invoice_id="invoice-53")
            digest2 = validate_payment_evidence(second, expected_order_id="order-53",
                expected_invoice_id="invoice-53", expected_amount=Decimal("30"), expected_currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "transaction_already_settled"):
                ledger.advance(order_id="order-53", target=CommercialState.SETTLED,
                               event_id="settle-53", payload_digest=digest2, payment_evidence=second)
            self.assertEqual(ledger.snapshot("order-53")["state"], "payment_pending")
            ledger.close()


    def test_verified_revenue_cannot_swap_settlement_transaction(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._offline_ledger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04", amount=Decimal("30"), currency="TRX")
            for state, event in ((CommercialState.QUOTED, "quote-52"),
                                 (CommercialState.INVOICED, "invoice-52"),
                                 (CommercialState.PAYMENT_PENDING, "pending-52")):
                step_digest = invoice_commitment(
                    order_id="order-52", invoice_id="invoice-52",
                    amount=Decimal("30"), currency="TRX",
                ) if state is CommercialState.INVOICED else "a" * 64
                ledger.advance(order_id="order-52", target=state,
                               event_id=event, payload_digest=step_digest)
            ledger.bind_issued_invoice(
                order_id="order-52", invoice_id="invoice-52",
                payload_digest=invoice_commitment(
                    order_id="order-52", invoice_id="invoice-52",
                    amount=Decimal("30"), currency="TRX",
                ),
            )
            evidence = self.payment()
            digest = validate_payment_evidence(evidence, expected_order_id="order-52",
                expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")
            ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                           event_id="settle-52", payload_digest=digest, payment_evidence=evidence)
            ledger.advance(order_id="order-52", target=CommercialState.FULFILLMENT_PENDING,
                           event_id="fulfill-pending-52", payload_digest="b" * 64)
            ledger.advance(order_id="order-52", target=CommercialState.FULFILLED,
                           event_id="fulfilled-52", payload_digest="d" * 64,
                           fulfillment_manifest_sha256="d" * 64)
            with self.assertRaisesRegex(CommercialGateError, "verified_revenue_settlement_mismatch"):
                ledger.advance(order_id="order-52", target=CommercialState.VERIFIED_REVENUE,
                               event_id="verified-52", payload_digest="e" * 64,
                               payment_evidence=self.payment(transaction_id="b" * 64),
                               verified_revenue=True)
            self.assertEqual(ledger.snapshot("order-52")["state"], "fulfilled")
            ledger.advance(order_id="order-52", target=CommercialState.VERIFIED_REVENUE,
                           event_id="verified-52-valid", payload_digest="e" * 64,
                           payment_evidence=evidence, verified_revenue=True)
            self.assertEqual(ledger.snapshot("order-52")["state"], "verified_revenue")
            ledger.close()


    def test_ledger_rejects_unsafe_event_identifiers_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04", amount=Decimal("30"), currency="TRX")
            for event_id in ("quote" + chr(10) + "spoof", "quote" + chr(9) + "spoof", "x" * 129, "évent-52"):
                with self.subTest(event_id=event_id):
                    with self.assertRaisesRegex(CommercialGateError, "event_id_invalid"):
                        ledger.advance(order_id="order-52", target=CommercialState.QUOTED,
                                       event_id=event_id, payload_digest="a" * 64)
            self.assertEqual(ledger.snapshot("order-52")["state"], "ordered")
            self.assertEqual(ledger.connection.execute(
                "SELECT COUNT(*) FROM order_events WHERE order_id = ?", ("order-52",)
            ).fetchone()[0], 1)
            ledger.advance(order_id="order-52", target=CommercialState.QUOTED,
                           event_id="quote-52", payload_digest="a" * 64)
            self.assertEqual(ledger.snapshot("order-52")["state"], "quoted")
            ledger.close()


    def test_personal_social_subdomains_are_not_merchant_hosts(self):
        with self.assertRaisesRegex(CommercialGateError, "canonical_host_invalid"):
            validate_offer(self.offer(canonical_host="store.dr.mojtaba.rozegar"))

    def test_payment_evidence_must_be_correct_type(self):
        with self.assertRaisesRegex(CommercialGateError, "payment_evidence_invalid"):
            validate_payment_evidence(None, expected_order_id="order-52",
                expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")

    def test_payment_provider_rejects_placeholders_and_invalid_identifiers(self):
        for provider, expected in (("none", "payment_provider_not_configured"),
                                   ("test", "payment_provider_not_configured"),
                                   ("manual review", "provider_invalid")):
            with self.subTest(provider=provider):
                with self.assertRaisesRegex(CommercialGateError, expected):
                    validate_payment_evidence(self.payment(provider=provider), expected_order_id="order-52",
                        expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")

    def test_native_trx_receipt_cannot_use_fiat_invoice_unit(self):
        with self.assertRaisesRegex(CommercialGateError, "native_trx_currency_required"):
            validate_payment_evidence(self.payment(currency="USD"), expected_order_id="order-52",
                expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="USD")

    def test_tron_hash_must_be_canonical_64_hex_digits(self):
        with self.assertRaisesRegex(CommercialGateError, "transaction_id_invalid"):
            validate_payment_evidence(self.payment(transaction_id="txid-52-verified"),
                expected_order_id="order-52", expected_invoice_id="invoice-52",
                expected_amount=Decimal("30"), expected_currency="TRX")

    def test_tron_hash_case_cannot_create_another_receipt(self):
        kwargs = dict(expected_order_id="order-52", expected_invoice_id="invoice-52",
                      expected_amount=Decimal("30"), expected_currency="TRX")
        self.assertEqual(
            validate_payment_evidence(self.payment(transaction_id="A" * 64), **kwargs),
            validate_payment_evidence(self.payment(transaction_id="a" * 64), **kwargs),
        )

    def test_rejects_overly_large_commercial_amounts(self):
        with self.assertRaisesRegex(CommercialGateError, "price_exceeds_safety_cap"):
            validate_offer(self.offer(price=Decimal("1000000000000001")))

    def test_state_transition_rejects_fake_enum(self):
        with self.assertRaisesRegex(CommercialGateError, "invalid_state_transition"):
            transition_state(CommercialState.ORDERED, "quoted")

    def test_verified_revenue_attestation_requires_boolean_true(self):
        with self.assertRaisesRegex(CommercialGateError, "verified_revenue_attestation_required"):
            transition_state(CommercialState.FULFILLED, CommercialState.VERIFIED_REVENUE,
                payment_evidence=self.payment(), verified_revenue="true")

    def test_fulfillment_manifest_rejects_malformed_input_type(self):
        with self.assertRaisesRegex(CommercialGateError, "fulfillment_manifest_required"):
            transition_state(CommercialState.FULFILLMENT_PENDING, CommercialState.FULFILLED,
                fulfillment_manifest_sha256=None)

    def test_staged_ledger_rejects_nonstring_payload_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                amount=Decimal("30"), currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "payload_digest_invalid"):
                ledger.advance(order_id="order-52", target=CommercialState.QUOTED,
                               event_id="quote-52", payload_digest=None)
            ledger.close()

    def test_fulfillment_is_immutably_bound_to_manifest_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._offline_ledger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04", amount=Decimal("30"), currency="TRX")
            for target, key in ((CommercialState.QUOTED, "quote-52"),
                                (CommercialState.INVOICED, "invoice-52"),
                                (CommercialState.PAYMENT_PENDING, "pending-52")):
                step_digest = invoice_commitment(
                    order_id="order-52", invoice_id="invoice-52",
                    amount=Decimal("30"), currency="TRX",
                ) if target is CommercialState.INVOICED else "a" * 64
                ledger.advance(order_id="order-52", target=target, event_id=key, payload_digest=step_digest)
            ledger.bind_issued_invoice(
                order_id="order-52", invoice_id="invoice-52",
                payload_digest=invoice_commitment(
                    order_id="order-52", invoice_id="invoice-52",
                    amount=Decimal("30"), currency="TRX",
                ),
            )
            ev = self.payment()
            digest = validate_payment_evidence(ev, expected_order_id="order-52",
                expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")
            ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                           event_id="settle-52", payload_digest=digest, payment_evidence=ev)
            ledger.advance(order_id="order-52", target=CommercialState.FULFILLMENT_PENDING,
                           event_id="fulfillment-pending-52", payload_digest="b" * 64)
            with self.assertRaisesRegex(CommercialGateError, "fulfillment_payload_mismatch"):
                ledger.advance(order_id="order-52", target=CommercialState.FULFILLED,
                               event_id="fulfilled-52", payload_digest="c" * 64,
                               fulfillment_manifest_sha256="d" * 64)
            self.assertEqual(ledger.snapshot("order-52")["state"], "fulfillment_pending")
            ledger.close()


    def test_invoice_registry_cannot_bind_without_proven_issue_event(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04", amount=Decimal("30"), currency="TRX")
            ref = invoice_commitment(order_id="order-52", invoice_id="invoice-52",
                                     amount=Decimal("30"), currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "invoice_bind_state_invalid"):
                ledger.bind_issued_invoice(order_id="order-52", invoice_id="invoice-52", payload_digest=ref)
            ledger.close()

    def test_settlement_requires_registered_invoice_even_with_matching_amount(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04", amount=Decimal("30"), currency="TRX")
            for state, key in ((CommercialState.QUOTED, "quote-52"),
                               (CommercialState.INVOICED, "invoice-52"),
                               (CommercialState.PAYMENT_PENDING, "pending-52")):
                digest = invoice_commitment(order_id="order-52", invoice_id="invoice-52",
                    amount=Decimal("30"), currency="TRX") if state is CommercialState.INVOICED else "a" * 64
                ledger.advance(order_id="order-52", target=state, event_id=key, payload_digest=digest)
            proof = self.payment()
            payload = validate_payment_evidence(proof, expected_order_id="order-52",
                expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "registered_invoice_required"):
                ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                               event_id="settle-52", payload_digest=payload, payment_evidence=proof)
            self.assertEqual(ledger.snapshot("order-52")["state"], "payment_pending")
            ledger.close()

    def test_invoice_binds_order_price_and_reference(self):
        digest = invoice_commitment(order_id="order-52", invoice_id="invoice-52",
                                    amount=Decimal("30"), currency="TRX")
        self.assertNotEqual(digest, invoice_commitment(
            order_id="order-52", invoice_id="invoice-53", amount=Decimal("30"), currency="TRX"))
        self.assertNotEqual(digest, invoice_commitment(
            order_id="order-52", invoice_id="invoice-52", amount=Decimal("31"), currency="TRX"))



    def test_private_sqlite_ledger_is_owner_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            ledger = SQLiteCommercialLedger(str(path))
            self.assertEqual(path.stat().st_mode & 0o077, 0)
            ledger.close()
            reopened = SQLiteCommercialLedger(str(path))
            reopened.close()

    def test_ledger_refuses_symlink_path(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "actual.sqlite3"
            led = SQLiteCommercialLedger(str(original))
            led.close()
            alias = Path(directory) / "alias.sqlite3"
            alias.symlink_to(original)
            with self.assertRaisesRegex(CommercialGateError, "ledger_symlink_prohibited"):
                SQLiteCommercialLedger(str(alias))

    def test_ledger_refuses_world_readable_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            led = SQLiteCommercialLedger(str(path))
            led.close()
            path.chmod(0o644)
            with self.assertRaisesRegex(CommercialGateError, "ledger_file_permissions_unsafe"):
                SQLiteCommercialLedger(str(path))

    def test_staged_event_history_is_immutable_to_accidental_update(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                amount=Decimal("30"), currency="TRX")
            with self.assertRaisesRegex(sqlite3.DatabaseError, "immutable_order_event"):
                ledger.connection.execute(
                    "UPDATE order_events SET payload_digest = ? WHERE order_id = ?",
                    ("b" * 64, "order-52"))
            self.assertEqual(ledger.connection.execute(
                "SELECT payload_digest FROM order_events WHERE order_id = ?", ("order-52",)
            ).fetchone()[0], ledger.connection.execute(
                "SELECT payload_digest FROM order_events WHERE event_id = ?", ("create:order-52",)
            ).fetchone()[0])
            ledger.close()

    def test_staged_order_history_cannot_be_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                amount=Decimal("30"), currency="TRX")
            with self.assertRaisesRegex(sqlite3.DatabaseError, "immutable_order_event"):
                ledger.connection.execute("DELETE FROM order_events WHERE order_id = ?", ("order-52",))
            ledger.close()


    def _prepare_private_invoice(self, ledger, order_id):
        invoice_id = "invoice-" + order_id.split("-")[-1]
        digest = invoice_commitment(order_id=order_id, invoice_id=invoice_id,
                                    amount=Decimal("30"), currency="TRX")
        ledger.create_order(order_id=order_id, offer_id="moj-s04", amount=Decimal("30"), currency="TRX")
        ledger.advance(order_id=order_id, target=CommercialState.QUOTED,
                       event_id="quoted-" + order_id, payload_digest="a" * 64)
        ledger.advance(order_id=order_id, target=CommercialState.INVOICED,
                       event_id="invoiced-" + order_id, payload_digest=digest)
        ledger.bind_issued_invoice(order_id=order_id, invoice_id=invoice_id, payload_digest=digest)
        ledger.advance(order_id=order_id, target=CommercialState.PAYMENT_PENDING,
                       event_id="pending-" + order_id, payload_digest="b" * 64)
        return invoice_id

    def test_invoice_reference_cannot_be_rebound(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            self._prepare_private_invoice(ledger, "order-52")
            with self.assertRaisesRegex(CommercialGateError, "invoice_already_registered"):
                ledger.bind_issued_invoice(order_id="order-52", invoice_id="invoice-52",
                    payload_digest=invoice_commitment(order_id="order-52", invoice_id="invoice-52",
                                                      amount=Decimal("30"), currency="TRX"))
            ledger.close()

    def test_settlement_rejects_another_invoice_even_with_matching_trx(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            self._prepare_private_invoice(ledger, "order-52")
            wrong = self.payment(invoice_id="invoice-53")
            proof = validate_payment_evidence(wrong, expected_order_id="order-52",
                expected_invoice_id="invoice-53", expected_amount=Decimal("30"), expected_currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "settlement_invoice_mismatch"):
                ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                               event_id="settle-52", payload_digest=proof, payment_evidence=wrong)
            self.assertEqual(ledger.snapshot("order-52")["state"], "payment_pending")
            ledger.close()

    def test_same_tron_tx_different_letter_case_cannot_settle_two_orders(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._offline_ledger(str(Path(directory) / "ledger.sqlite3"))
            self._prepare_private_invoice(ledger, "order-52")
            self._prepare_private_invoice(ledger, "order-53")
            first = self.payment(transaction_id="A" * 64)
            proof1 = validate_payment_evidence(first, expected_order_id="order-52",
                expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")
            ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                           event_id="settled-52", payload_digest=proof1, payment_evidence=first)
            second = self.payment(order_id="order-53", invoice_id="invoice-53",
                                  transaction_id="a" * 64)
            proof2 = validate_payment_evidence(second, expected_order_id="order-53",
                expected_invoice_id="invoice-53", expected_amount=Decimal("30"), expected_currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "transaction_already_settled"):
                ledger.advance(order_id="order-53", target=CommercialState.SETTLED,
                               event_id="settled-53", payload_digest=proof2, payment_evidence=second)
            self.assertEqual(ledger.snapshot("order-53")["state"], "payment_pending")
            ledger.close()

    def test_invalid_expected_invoice_identifier_fails_closed(self):
        with self.assertRaisesRegex(CommercialGateError, "expected_invoice_id_invalid"):
            validate_payment_evidence(self.payment(), expected_order_id="order-52",
                expected_invoice_id="invoice 52", expected_amount=Decimal("30"), expected_currency="TRX")

    def test_snapshot_rejects_invalid_identifier_without_sqlite_error(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            with self.assertRaisesRegex(CommercialGateError, "order_id_required"):
                ledger.snapshot(None)
            ledger.close()

    def test_invalid_ledger_state_enum_does_not_mutate(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04", amount=Decimal("30"), currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "invalid_state_transition"):
                ledger.advance(order_id="order-52", target="quoted",
                               event_id="quoted-52", payload_digest="a" * 64)
            self.assertEqual(ledger.snapshot("order-52")["state"], "ordered")
            ledger.close()

    def test_invoice_registry_disallows_update_and_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            self._prepare_private_invoice(ledger, "order-52")
            with self.assertRaisesRegex(sqlite3.DatabaseError, "immutable_invoice"):
                ledger.connection.execute("UPDATE issued_invoices SET invoice_id = ? WHERE order_id = ?",
                                          ("invoice-53", "order-52"))
            ledger.connection.rollback()
            with self.assertRaisesRegex(sqlite3.DatabaseError, "immutable_invoice"):
                ledger.connection.execute("DELETE FROM issued_invoices WHERE order_id = ?", ("order-52",))
            ledger.connection.rollback()
            ledger.close()

    def test_second_connection_cannot_consume_stale_uncommitted_order_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "ledger.sqlite3")
            first = SQLiteCommercialLedger(path)
            first.create_order(order_id="order-52", offer_id="moj-s04", amount=Decimal("30"), currency="TRX")
            second = SQLiteCommercialLedger(path)
            second.connection.execute("PRAGMA busy_timeout=1")
            first.connection.execute("BEGIN IMMEDIATE")
            try:
                with self.assertRaises(sqlite3.OperationalError):
                    second.advance(order_id="order-52", target=CommercialState.QUOTED,
                                   event_id="quote-52", payload_digest="a" * 64)
            finally:
                first.connection.rollback()
            self.assertEqual(second.snapshot("order-52")["state"], "ordered")
            first.close()
            second.close()


    def test_offer_contract_must_be_exact_type(self):
        with self.assertRaisesRegex(CommercialGateError, "offer_contract_required"):
            validate_offer(None)

    def test_digital_manifest_wrong_type_fails_before_any_public_release(self):
        with self.assertRaisesRegex(CommercialGateError, "delivery_manifest_hash_invalid"):
            validate_offer(self.offer(delivery_manifest_sha256=None))

    def test_manual_trx_gateway_cannot_offer_usd_as_native_trx(self):
        with self.assertRaisesRegex(CommercialGateError, "native_trx_gateway_currency_required"):
            validate_offer(self.offer(offer_type=OfferType.TRX_GATEWAY, currency="USD"))

    def test_zero_transaction_hash_is_not_a_receipt(self):
        with self.assertRaisesRegex(CommercialGateError, "transaction_id_invalid"):
            validate_payment_evidence(self.payment(transaction_id="0" * 64),
                expected_order_id="order-52", expected_invoice_id="invoice-52",
                expected_amount=Decimal("30"), expected_currency="TRX")


    def test_unverified_payment_cannot_settle_or_mutate_order(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            self._prepare_private_invoice(ledger, "order-52")
            evidence = self.payment()
            digest = validate_payment_evidence(evidence, expected_order_id="order-52",
                expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "independent_settlement_verifier_required"):
                ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                    event_id="settled-52", payload_digest=digest, payment_evidence=evidence)
            self.assertEqual(ledger.snapshot("order-52")["state"], "payment_pending")
            ledger.close()

    def test_independent_payment_denial_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"),
                settlement_verifier=lambda _: False)
            self._prepare_private_invoice(ledger, "order-52")
            evidence = self.payment()
            digest = validate_payment_evidence(evidence, expected_order_id="order-52",
                expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "independent_settlement_unverified"):
                ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                    event_id="settled-52", payload_digest=digest, payment_evidence=evidence)
            self.assertEqual(ledger.snapshot("order-52")["state"], "payment_pending")
            ledger.close()

    def test_independent_verifier_error_fails_closed(self):
        def offline(_):
            raise TimeoutError("provider offline")
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"),
                settlement_verifier=offline)
            self._prepare_private_invoice(ledger, "order-52")
            evidence = self.payment()
            digest = validate_payment_evidence(evidence, expected_order_id="order-52",
                expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "independent_settlement_verifier_failed"):
                ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                    event_id="settled-52", payload_digest=digest, payment_evidence=evidence)
            ledger.close()

    def test_truthy_string_verification_is_not_external_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"),
                settlement_verifier=lambda _: "true")
            self._prepare_private_invoice(ledger, "order-52")
            evidence = self.payment()
            digest = validate_payment_evidence(evidence, expected_order_id="order-52",
                expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "independent_settlement_unverified"):
                ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                    event_id="settled-52", payload_digest=digest, payment_evidence=evidence)
            ledger.close()

    def test_verifier_inputs_must_be_callable(self):
        with self.assertRaisesRegex(CommercialGateError, "settlement_verifier_invalid"):
            SQLiteCommercialLedger(":memory:", settlement_verifier="yes")
        with self.assertRaisesRegex(CommercialGateError, "delivery_verifier_invalid"):
            SQLiteCommercialLedger(":memory:", delivery_verifier=1)

    def test_manifest_alone_cannot_prove_customer_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"),
                settlement_verifier=lambda _: True)
            self._prepare_private_invoice(ledger, "order-52")
            evidence = self.payment()
            digest = validate_payment_evidence(evidence, expected_order_id="order-52",
                expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")
            ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                event_id="settled-52", payload_digest=digest, payment_evidence=evidence)
            ledger.advance(order_id="order-52", target=CommercialState.FULFILLMENT_PENDING,
                event_id="pending-delivery-52", payload_digest="b" * 64)
            with self.assertRaisesRegex(CommercialGateError, "independent_delivery_verifier_required"):
                ledger.advance(order_id="order-52", target=CommercialState.FULFILLED,
                    event_id="delivered-52", payload_digest="d" * 64,
                    fulfillment_manifest_sha256="d" * 64)
            self.assertEqual(ledger.snapshot("order-52")["state"], "fulfillment_pending")
            ledger.close()


    def _settled_replay_order(self, path):
        ledger = self._offline_ledger(path)
        self._prepare_private_invoice(ledger, "order-52")
        proof = self.payment()
        digest = validate_payment_evidence(proof, expected_order_id="order-52",
            expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")
        ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                       event_id="settled-52", payload_digest=digest, payment_evidence=proof)
        return ledger, proof, digest

    def test_settled_replay_requires_represented_payment_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger, proof, digest = self._settled_replay_order(str(Path(directory) / "ledger.sqlite3"))
            with self.assertRaisesRegex(CommercialGateError, "settlement_evidence_required"):
                ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                               event_id="settled-52", payload_digest=digest)
            self.assertEqual(ledger.snapshot("order-52")["state"], "settled")
            ledger.close()

    def test_settled_replay_rechecks_independent_provider_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "ledger.sqlite3")
            ledger, proof, digest = self._settled_replay_order(path)
            ledger.close()
            reopened = SQLiteCommercialLedger(path, settlement_verifier=lambda _: False)
            with self.assertRaisesRegex(CommercialGateError, "independent_settlement_unverified"):
                reopened.advance(order_id="order-52", target=CommercialState.SETTLED,
                                 event_id="settled-52", payload_digest=digest, payment_evidence=proof)
            reopened.close()

    def test_settled_replay_rejects_substituted_transfer(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger, proof, digest = self._settled_replay_order(str(Path(directory) / "ledger.sqlite3"))
            with self.assertRaisesRegex(CommercialGateError, "event_replay_mismatch"):
                ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                               event_id="settled-52", payload_digest=digest,
                               payment_evidence=self.payment(transaction_id="b" * 64))
            ledger.close()

    def test_identical_settled_replay_with_valid_external_proof_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger, proof, digest = self._settled_replay_order(str(Path(directory) / "ledger.sqlite3"))
            state = ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                                   event_id="settled-52", payload_digest=digest, payment_evidence=proof)
            self.assertEqual(state, CommercialState.SETTLED)
            self.assertEqual(ledger.connection.execute(
                "SELECT COUNT(*) FROM order_events WHERE event_id = ?", ("settled-52",)
            ).fetchone()[0], 1)
            ledger.close()

    def test_fulfillment_replay_requires_manifest_again(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger, proof, digest = self._settled_replay_order(str(Path(directory) / "ledger.sqlite3"))
            ledger.advance(order_id="order-52", target=CommercialState.FULFILLMENT_PENDING,
                           event_id="fulfill-pending-52", payload_digest="b" * 64)
            ledger.advance(order_id="order-52", target=CommercialState.FULFILLED,
                           event_id="fulfilled-52", payload_digest="d" * 64,
                           fulfillment_manifest_sha256="d" * 64)
            with self.assertRaisesRegex(CommercialGateError, "fulfillment_payload_mismatch"):
                ledger.advance(order_id="order-52", target=CommercialState.FULFILLED,
                               event_id="fulfilled-52", payload_digest="d" * 64)
            ledger.close()

    def test_fulfillment_replay_rechecks_customer_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "ledger.sqlite3")
            ledger, proof, digest = self._settled_replay_order(path)
            ledger.advance(order_id="order-52", target=CommercialState.FULFILLMENT_PENDING,
                           event_id="fulfill-pending-52", payload_digest="b" * 64)
            ledger.advance(order_id="order-52", target=CommercialState.FULFILLED,
                           event_id="fulfilled-52", payload_digest="d" * 64,
                           fulfillment_manifest_sha256="d" * 64)
            ledger.close()
            reopened = SQLiteCommercialLedger(path, delivery_verifier=lambda _order, _manifest: False)
            with self.assertRaisesRegex(CommercialGateError, "independent_delivery_unverified"):
                reopened.advance(order_id="order-52", target=CommercialState.FULFILLED,
                                 event_id="fulfilled-52", payload_digest="d" * 64,
                                 fulfillment_manifest_sha256="d" * 64)
            reopened.close()


    def test_private_ledger_creation_does_not_rely_on_post_create_chmod(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            with patch("core.commercial_revenue_gate.os.chmod",
                       side_effect=AssertionError("unsafe post-create chmod")):
                ledger = SQLiteCommercialLedger(str(path))
            self.assertEqual(path.stat().st_mode & 0o077, 0)
            ledger.close()

    def test_private_ledger_rejects_existing_hardlink(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "original.sqlite3"
            ledger = SQLiteCommercialLedger(str(original))
            ledger.close()
            alias = Path(directory) / "hardlinked.sqlite3"
            alias.hardlink_to(original)
            with self.assertRaisesRegex(CommercialGateError, "ledger_file_permissions_unsafe"):
                SQLiteCommercialLedger(str(alias))

    def test_private_ledger_rejects_raced_file_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            with patch("core.commercial_revenue_gate.os.open", side_effect=FileExistsError):
                with self.assertRaisesRegex(CommercialGateError, "ledger_creation_race"):
                    SQLiteCommercialLedger(str(path))
            self.assertFalse(path.exists())

    def test_private_ledger_rejects_writable_parent_on_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            ledger = SQLiteCommercialLedger(str(path))
            ledger.close()
            parent = path.parent
            parent.chmod(0o777)
            try:
                with self.assertRaisesRegex(CommercialGateError, "ledger_parent_writable_by_others"):
                    SQLiteCommercialLedger(str(path))
            finally:
                parent.chmod(0o700)


    def test_equal_trx_values_use_identical_invoice_commitment(self):
        digests = [invoice_commitment(order_id="order-52", invoice_id="invoice-52",
            amount=Decimal(value), currency="TRX") for value in ("30", "30.00", "3E+1")]
        self.assertEqual(len(set(digests)), 1)

    def test_payment_digest_normalizes_equivalent_decimal_spellings(self):
        first = validate_payment_evidence(self.payment(amount=Decimal("30.0")),
            expected_order_id="order-52", expected_invoice_id="invoice-52",
            expected_amount=Decimal("30"), expected_currency="TRX")
        second = validate_payment_evidence(self.payment(amount=Decimal("30.000000")),
            expected_order_id="order-52", expected_invoice_id="invoice-52",
            expected_amount=Decimal("30"), expected_currency="TRX")
        self.assertEqual(first, second)

    def test_canonical_order_amount_survives_private_ledger_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "ledger.sqlite3")
            ledger = SQLiteCommercialLedger(path)
            ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                amount=Decimal("30.0000"), currency="TRX")
            self.assertEqual(ledger.snapshot("order-52")["amount"], "30")
            ledger.close()
            restored = SQLiteCommercialLedger(path)
            self.assertEqual(restored.snapshot("order-52")["amount"], "30")
            restored.close()

    def test_other_currency_rejects_unbounded_tiny_precision(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            with self.assertRaisesRegex(CommercialGateError, "amount_precision_exceeds_safe_limit"):
                ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                    amount=Decimal("0.00000000000000000000000001"), currency="USD")
            ledger.close()


    def _refundable_ledger(self, directory, *, refund_verifier=None):
        ledger = SQLiteCommercialLedger(
            str(Path(directory) / "ledger.sqlite3"),
            settlement_verifier=lambda evidence: True,
            delivery_verifier=lambda order, digest: True,
            refund_verifier=refund_verifier,
            accepted_scope_verifier=lambda order: True,
        )
        self._prepare_private_invoice(ledger, "order-52")
        receipt = self.payment()
        proof = validate_payment_evidence(receipt,
            expected_order_id="order-52", expected_invoice_id="invoice-52",
            expected_amount=Decimal("30"), expected_currency="TRX")
        ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                       event_id="settled-52", payload_digest=proof, payment_evidence=receipt)
        return ledger

    def _refund_proof(self, **changes):
        fields = dict(order_id="order-52", original_transaction_id="a" * 64,
                      refund_transaction_id="b" * 64, amount=Decimal("11.5"),
                      source_id="independent-provider-52")
        fields.update(changes)
        return ConfirmedRefund(**fields)

    def test_refund_cannot_be_recorded_without_independent_source(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory)
            with self.assertRaisesRegex(CommercialGateError, "independent_refund_verifier_required"):
                ledger.record_confirmed_refund(self._refund_proof())
            self.assertEqual(ledger.outstanding_settled_trx("order-52"), Decimal("30"))
            ledger.close()

    def test_two_confirmed_refunds_update_net_native_trx_without_claiming_profit(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda proof: True)
            ledger.record_confirmed_refund(self._refund_proof(amount=Decimal("11.500000")))
            self.assertEqual(ledger.outstanding_settled_trx("order-52"), Decimal("18.5"))
            ledger.record_confirmed_refund(self._refund_proof(
                amount=Decimal("18.5"), refund_transaction_id="c" * 64,
                source_id="independent-provider-53"))
            self.assertEqual(ledger.outstanding_settled_trx("order-52"), Decimal("0"))
            ledger.close()

    def test_confirmed_refund_tx_cannot_be_used_for_second_order_payment(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda proof: True)
            ledger.record_confirmed_refund(self._refund_proof(refund_transaction_id="B" * 64))
            self._prepare_private_invoice(ledger, "order-53")
            proof = self.payment(
                order_id="order-53", invoice_id="invoice-53",
                transaction_id="b" * 64,
            )
            digest = validate_payment_evidence(
                proof, expected_order_id="order-53",
                expected_invoice_id="invoice-53", expected_amount=Decimal("30"),
                expected_currency="TRX",
            )
            external_calls = []
            ledger._settlement_verifier = lambda evidence: external_calls.append(evidence) or True
            with self.assertRaisesRegex(
                CommercialGateError, "refund_transaction_cannot_settle_order"
            ):
                ledger.advance(
                    order_id="order-53", target=CommercialState.SETTLED,
                    event_id="settled-53", payload_digest=digest,
                    payment_evidence=proof,
                )
            self.assertEqual(external_calls, [])
            self.assertEqual(ledger.snapshot("order-53")["state"], "payment_pending")
            self.assertEqual(ledger.outstanding_settled_trx("order-52"), Decimal("18.5"))
            ledger.close()

    def test_direct_sql_cannot_recredit_refund_tx_as_new_settlement(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda proof: True)
            ledger.record_confirmed_refund(self._refund_proof(refund_transaction_id="b" * 64))
            self._prepare_private_invoice(ledger, "order-53")
            with self.assertRaisesRegex(
                sqlite3.DatabaseError, "refund_transaction_cannot_settle_order"
            ):
                ledger.connection.execute(
                    "INSERT INTO settled_transactions (network, transaction_id, order_id) "
                    "VALUES (?, ?, ?)", ("TRON", "B" * 64, "order-53"),
                )
            ledger.connection.rollback()
            self.assertEqual(ledger.snapshot("order-53")["state"], "payment_pending")
            ledger.close()

    def test_direct_sql_cannot_claim_prior_payment_as_new_refund(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda proof: True)
            with self.assertRaisesRegex(
                sqlite3.DatabaseError, "settlement_transaction_cannot_be_refund"
            ):
                ledger.connection.execute(
                    "INSERT INTO independently_confirmed_refunds "
                    "(refund_tx, order_id, amount_sun, source_id, recorded_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    ("A" * 64, "order-52", 1, "independent-source-new",
                     "2026-11-15T00:00:00+00:00"),
                )
            ledger.connection.rollback()
            self.assertEqual(ledger.outstanding_settled_trx("order-52"), Decimal("30"))
            ledger.close()

    def test_confirmed_refund_fails_if_total_exceeds_original_transfer(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda proof: True)
            ledger.record_confirmed_refund(self._refund_proof(amount=Decimal("20")))
            with self.assertRaisesRegex(CommercialGateError, "refund_exceeds_original_payment"):
                ledger.record_confirmed_refund(self._refund_proof(
                    amount=Decimal("11"), refund_transaction_id="c" * 64))
            self.assertEqual(ledger.outstanding_settled_trx("order-52"), Decimal("10"))
            ledger.close()

    def test_refund_transaction_is_single_use_and_case_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda proof: True)
            ledger.record_confirmed_refund(self._refund_proof(refund_transaction_id="B" * 64))
            with self.assertRaisesRegex(CommercialGateError, "refund_transfer_already_recorded"):
                ledger.record_confirmed_refund(self._refund_proof(refund_transaction_id="b" * 64))
            ledger.close()

    def test_refund_cannot_reuse_incoming_settlement_transaction(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda proof: True)
            with self.assertRaisesRegex(CommercialGateError, "refund_reuses_original_transaction"):
                ledger.record_confirmed_refund(self._refund_proof(
                    refund_transaction_id="a" * 64))
            ledger.close()

    def test_refund_cannot_reference_unrelated_incoming_transfer(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda proof: True)
            with self.assertRaisesRegex(CommercialGateError, "refund_original_transfer_not_matched"):
                ledger.record_confirmed_refund(self._refund_proof(
                    original_transaction_id="d" * 64))
            ledger.close()

    def test_false_refund_verifier_never_reduces_outstanding_balance(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda proof: "yes")
            with self.assertRaisesRegex(CommercialGateError, "independent_refund_unverified"):
                ledger.record_confirmed_refund(self._refund_proof())
            self.assertEqual(ledger.outstanding_settled_trx("order-52"), Decimal("30"))
            ledger.close()

    def test_refund_history_is_immutable_at_sql_layer(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda proof: True)
            ledger.record_confirmed_refund(self._refund_proof())
            with self.assertRaisesRegex(sqlite3.DatabaseError, "immutable_confirmed_refund"):
                ledger.connection.execute("DELETE FROM independently_confirmed_refunds WHERE order_id = ?",
                                          ("order-52",))
            ledger.connection.rollback()
            self.assertEqual(ledger.outstanding_settled_trx("order-52"), Decimal("18.5"))
            ledger.close()

    def test_outstanding_payment_cannot_be_reported_for_unpaid_order(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                amount=Decimal("30"), currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "outstanding_amount_unavailable"):
                ledger.outstanding_settled_trx("order-52")
            ledger.close()


    def test_independent_refund_source_cannot_prove_two_distinct_transfers(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda proof: True)
            ledger.record_confirmed_refund(self._refund_proof(amount=Decimal("10")))
            with self.assertRaisesRegex(CommercialGateError, "refund_source_already_used"):
                ledger.record_confirmed_refund(self._refund_proof(
                    amount=Decimal("10"), refund_transaction_id="c" * 64))
            self.assertEqual(ledger.outstanding_settled_trx("order-52"), Decimal("20"))
            ledger.close()

    def test_large_refund_sums_use_python_precision_not_sqlite_64bit_sum(self):
        # Test fixture injects two already-confirmed records; no live payment
        # or refund is attempted. Each is valid int64 but the sum exceeds int64.
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                amount=Decimal("10000000000000"), currency="TRX")
            ledger.connection.execute(
                "UPDATE orders SET state = ? WHERE order_id = ?",
                (CommercialState.SETTLED.value, "order-52"))
            for tx, source in (("b" * 64, "ext-source-1"), ("c" * 64, "ext-source-2")):
                ledger.connection.execute(
                    "INSERT INTO independently_confirmed_refunds VALUES (?, ?, ?, ?, ?)",
                    (tx, "order-52", 5000000000000000000, source, "2026-11-15T00:00:00+00:00"))
            ledger.connection.commit()
            self.assertEqual(ledger.outstanding_settled_trx("order-52"), Decimal("0"))
            ledger.close()


    def test_unregistered_invoice_does_not_call_external_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            called = []
            def verifier(evidence):
                called.append(evidence)
                return True
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"),
                settlement_verifier=verifier)
            ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                amount=Decimal("30"), currency="TRX")
            ledger.advance(order_id="order-52", target=CommercialState.QUOTED,
                           event_id="quote-52", payload_digest="a" * 64)
            ledger.advance(order_id="order-52", target=CommercialState.INVOICED,
                           event_id="invoice-52", payload_digest=invoice_commitment(
                               order_id="order-52", invoice_id="invoice-52",
                               amount=Decimal("30"), currency="TRX"))
            ledger.advance(order_id="order-52", target=CommercialState.PAYMENT_PENDING,
                           event_id="pending-52", payload_digest="b" * 64)
            ev = self.payment()
            digest = validate_payment_evidence(ev, expected_order_id="order-52",
                expected_invoice_id="invoice-52", expected_amount=Decimal("30"), expected_currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "registered_invoice_required"):
                ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                               event_id="settled-52", payload_digest=digest, payment_evidence=ev)
            self.assertEqual(called, [])
            ledger.close()

    def test_invoice_mismatch_does_not_call_external_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            called = []
            def verifier(evidence):
                called.append(evidence)
                return True
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"),
                settlement_verifier=verifier)
            self._prepare_private_invoice(ledger, "order-52")
            ev = self.payment(invoice_id="invoice-53")
            digest = validate_payment_evidence(ev, expected_order_id="order-52",
                expected_invoice_id="invoice-53", expected_amount=Decimal("30"), expected_currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "settlement_invoice_mismatch"):
                ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                               event_id="settled-52", payload_digest=digest, payment_evidence=ev)
            self.assertEqual(called, [])
            ledger.close()


    def test_all_paid_offer_types_forbid_financial_order_execution(self):
        for category in (OfferType.MOJ_PROP, OfferType.TRX_GATEWAY,
                         OfferType.DIGITAL_PRODUCT, OfferType.GAME):
            with self.subTest(category=category):
                with self.assertRaisesRegex(CommercialGateError, "financial_execution_disabled"):
                    validate_offer(self.offer(offer_type=category, financial_call_enabled=True))

    def test_external_social_platforms_can_never_be_company_checkout_hosts(self):
        for host in ("facebook.com", "www.facebook.com", "m.facebook.com",
                     "instagram.com", "www.instagram.com", "metricool.com",
                     "app.metricool.com", "fb.com"):
            with self.subTest(host=host):
                with self.assertRaisesRegex(CommercialGateError, "canonical_host_invalid"):
                    validate_offer(self.offer(
                        canonical_host=host, active=True, owner_approved=True,
                        legal_reviewed=True, kyc_ready=True, rights_cleared=True),
                        tenant_registry={"moj_prop": host})

    def test_ip_addresses_cannot_be_merchant_host_identifiers(self):
        for host in ("127.0.0.1", "8.8.8.8", "0.0.0.0", "192.168.1.12",
                     "198.51.100.1", "shop.123"):
            with self.subTest(host=host):
                with self.assertRaisesRegex(CommercialGateError, "canonical_host_invalid"):
                    validate_offer(self.offer(canonical_host=host))

    def test_approved_company_subdomains_remain_valid(self):
        validate_offer(self.offer(canonical_host="trade.zomorodmelal.ir"),
                       tenant_registry={"moj_prop": "trade.zomorodmelal.ir"})

    def test_long_decimal_invoice_commitment_never_rounds_to_context(self):
        common = dict(order_id="order-52", invoice_id="invoice-52", currency="USD")
        amount_a = Decimal("0.123456789012345678901234567890123456789")
        amount_b = Decimal("0.123456789012345678901234567890123456788")
        self.assertNotEqual(invoice_commitment(amount=amount_a, **common),
                            invoice_commitment(amount=amount_b, **common))

    def test_offer_rejects_deep_fractional_price_before_sale(self):
        with self.assertRaisesRegex(CommercialGateError, "amount_precision_exceeds_safe_limit"):
            validate_offer(self.offer(price=Decimal("1e-30"), currency="USD"))

    def test_invoice_rejects_pathological_tiny_decimal_without_expansion(self):
        with self.assertRaisesRegex(CommercialGateError, "amount_precision_exceeds_safe_limit"):
            invoice_commitment(order_id="order-52", invoice_id="invoice-52",
                               amount=Decimal("1e-999999"), currency="USD")

    def test_invoice_rejects_unbounded_decimal_digits_without_oom(self):
        with self.assertRaisesRegex(CommercialGateError, "amount_precision_exceeds_safe_limit"):
            invoice_commitment(order_id="order-52", invoice_id="invoice-52",
                               amount=Decimal("0." + "1" * 140), currency="USD")


    def test_full_internal_release_booleans_are_not_authorization(self):
        with self.assertRaisesRegex(CommercialGateError, "independent_release_verifier_required"):
            validate_offer(self.offer(
                active=True, owner_approved=True, legal_reviewed=True,
                kyc_ready=True, rights_cleared=True),
                tenant_registry={"moj_prop": "mojplaywin.com"})

    def test_release_verifier_requires_literal_boolean_true(self):
        for value in (False, "true", 1, None):
            with self.subTest(value=value):
                with self.assertRaisesRegex(CommercialGateError, "independent_release_unverified"):
                    validate_offer(self.offer(
                        active=True, owner_approved=True, legal_reviewed=True,
                        kyc_ready=True, rights_cleared=True),
                        tenant_registry={"moj_prop": "mojplaywin.com"},
                        independent_release_verifier=lambda offer: value)

    def test_release_verifier_unavailable_fails_closed(self):
        def unavailable(_):
            raise OSError("release authorization unavailable")
        with self.assertRaisesRegex(CommercialGateError, "independent_release_verifier_failed"):
            validate_offer(self.offer(
                active=True, owner_approved=True, legal_reviewed=True,
                kyc_ready=True, rights_cleared=True),
                tenant_registry={"moj_prop": "mojplaywin.com"},
                independent_release_verifier=unavailable)

    def test_tenant_registry_type_errors_are_fail_closed(self):
        with self.assertRaisesRegex(CommercialGateError, "tenant_registry_invalid"):
            validate_offer(self.offer(), tenant_registry=["moj_prop"])

    def test_release_verifier_must_be_callable(self):
        with self.assertRaisesRegex(CommercialGateError, "release_verifier_invalid"):
            validate_offer(self.offer(), independent_release_verifier="yes")


    def test_partial_refund_prevents_gross_invoice_as_verified_revenue(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda proof: True)
            ledger.advance(order_id="order-52", target=CommercialState.FULFILLMENT_PENDING,
                           event_id="delivery-pending-52", payload_digest="a" * 64)
            ledger.advance(order_id="order-52", target=CommercialState.FULFILLED,
                           event_id="delivered-52", payload_digest="b" * 64,
                           fulfillment_manifest_sha256="b" * 64)
            ledger.record_confirmed_refund(self._refund_proof(amount=Decimal("1")))
            with self.assertRaisesRegex(CommercialGateError, "refund_reconciliation_required_before_revenue"):
                ledger.advance(order_id="order-52", target=CommercialState.VERIFIED_REVENUE,
                    event_id="revenue-52", payload_digest="c" * 64,
                    payment_evidence=self.payment(), verified_revenue=True)
            self.assertEqual(ledger.snapshot("order-52")["state"], "fulfilled")
            self.assertEqual(ledger.outstanding_settled_trx("order-52"), Decimal("29"))
            ledger.close()

    def test_refunded_verified_event_replay_does_not_reassert_original_gross(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda proof: True)
            ledger.advance(order_id="order-52", target=CommercialState.FULFILLMENT_PENDING,
                           event_id="delivery-pending-52", payload_digest="a" * 64)
            ledger.advance(order_id="order-52", target=CommercialState.FULFILLED,
                           event_id="delivered-52", payload_digest="b" * 64,
                           fulfillment_manifest_sha256="b" * 64)
            ev = self.payment()
            ledger.advance(order_id="order-52", target=CommercialState.VERIFIED_REVENUE,
                           event_id="revenue-52", payload_digest="c" * 64,
                           payment_evidence=ev, verified_revenue=True)
            ledger.record_confirmed_refund(self._refund_proof(amount=Decimal("30")))
            with self.assertRaisesRegex(CommercialGateError, "refund_reconciliation_required_before_revenue"):
                ledger.advance(order_id="order-52", target=CommercialState.VERIFIED_REVENUE,
                               event_id="revenue-52", payload_digest="c" * 64,
                               payment_evidence=ev, verified_revenue=True)
            self.assertEqual(ledger.outstanding_settled_trx("order-52"), Decimal("0"))
            ledger.close()

    def test_invalid_refund_never_calls_external_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            def verified(evidence):
                calls.append(evidence)
                return True
            ledger = self._refundable_ledger(directory, refund_verifier=verified)
            with self.assertRaisesRegex(CommercialGateError, "refund_original_transfer_not_matched"):
                ledger.record_confirmed_refund(self._refund_proof(original_transaction_id="d" * 64))
            with self.assertRaisesRegex(CommercialGateError, "refund_exceeds_original_payment"):
                ledger.record_confirmed_refund(self._refund_proof(amount=Decimal("31")))
            self.assertEqual(calls, [])
            ledger.close()

    def test_unknown_order_refund_does_not_call_external_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"),
                refund_verifier=lambda evidence: calls.append(evidence) or True)
            with self.assertRaisesRegex(CommercialGateError, "order_not_found"):
                ledger.record_confirmed_refund(self._refund_proof())
            self.assertEqual(calls, [])
            ledger.close()


    def _fulfilled_scope_fixture(self, directory):
        ledger = self._refundable_ledger(directory, refund_verifier=lambda refund: True)
        ledger.advance(order_id="order-52", target=CommercialState.FULFILLMENT_PENDING,
                       event_id="fulfillment-pending-52", payload_digest="a" * 64)
        ledger.advance(order_id="order-52", target=CommercialState.FULFILLED,
                       event_id="fulfilled-52", payload_digest="b" * 64,
                       fulfillment_manifest_sha256="b" * 64)
        return ledger

    def test_revenue_claim_fails_without_customer_accepted_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._fulfilled_scope_fixture(directory)
            ledger._accepted_scope_verifier = None
            with self.assertRaisesRegex(CommercialGateError, "independent_scope_acceptance_required"):
                ledger.advance(order_id="order-52", target=CommercialState.VERIFIED_REVENUE,
                    event_id="revenue-52", payload_digest="c" * 64,
                    payment_evidence=self.payment(), verified_revenue=True)
            self.assertEqual(ledger.snapshot("order-52")["state"], "fulfilled")
            ledger.close()

    def test_revenue_scope_authorization_cannot_be_truthy_string(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._fulfilled_scope_fixture(directory)
            ledger._accepted_scope_verifier = lambda order: "yes"
            with self.assertRaisesRegex(CommercialGateError, "scope_acceptance_unverified"):
                ledger.advance(order_id="order-52", target=CommercialState.VERIFIED_REVENUE,
                    event_id="revenue-52", payload_digest="c" * 64,
                    payment_evidence=self.payment(), verified_revenue=True)
            ledger.close()

    def test_scope_verifier_argument_type_is_validated(self):
        with self.assertRaisesRegex(CommercialGateError, "accepted_scope_verifier_invalid"):
            SQLiteCommercialLedger(":memory:", accepted_scope_verifier="true")


    def test_duplicate_refund_transfer_does_not_call_external_verifier_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            def trusted(proof):
                calls.append(proof)
                return True
            ledger = self._refundable_ledger(directory, refund_verifier=trusted)
            ledger.record_confirmed_refund(self._refund_proof())
            with self.assertRaisesRegex(CommercialGateError, "refund_transfer_already_recorded"):
                ledger.record_confirmed_refund(self._refund_proof())
            self.assertEqual(len(calls), 1)
            ledger.close()

    def test_reused_refund_source_does_not_call_external_verifier_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            def trusted(proof):
                calls.append(proof)
                return True
            ledger = self._refundable_ledger(directory, refund_verifier=trusted)
            ledger.record_confirmed_refund(self._refund_proof(amount=Decimal("10")))
            with self.assertRaisesRegex(CommercialGateError, "refund_source_already_used"):
                ledger.record_confirmed_refund(self._refund_proof(amount=Decimal("11"),
                    refund_transaction_id="c" * 64))
            self.assertEqual(len(calls), 1)
            ledger.close()


    def test_historical_verified_revenue_is_not_claimed_live_after_refund(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._fulfilled_scope_fixture(directory)
            ledger.advance(order_id="order-52", target=CommercialState.VERIFIED_REVENUE,
                event_id="verified-52", payload_digest="c" * 64,
                payment_evidence=self.payment(), verified_revenue=True)
            self.assertEqual(ledger.snapshot("order-52")["effective_revenue_status"],
                             "historical_attestation_only")
            ledger.record_confirmed_refund(self._refund_proof(amount=Decimal("11.5")))
            self.assertEqual(ledger.snapshot("order-52")["state"], "verified_revenue")
            self.assertEqual(ledger.snapshot("order-52")["effective_revenue_status"],
                             "refund_reconciliation_required")
            self.assertEqual(ledger.outstanding_settled_trx("order-52"), Decimal("18.5"))
            ledger.close()

    def test_unpaid_quote_cannot_be_reported_as_verified_revenue(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                amount=Decimal("30"), currency="TRX")
            self.assertEqual(ledger.snapshot("order-52")["effective_revenue_status"],
                             "not_verified")
            ledger.close()


    def test_fractional_sun_cannot_hide_behind_decimal_rounding(self):
        amount = Decimal("1.0000000000000000000000000000000001")
        with localcontext() as context:
            context.prec = 8
            with self.assertRaisesRegex(CommercialGateError, "trx_fractional_sun_forbidden"):
                invoice_commitment(order_id="order-52", invoice_id="invoice-52",
                                   amount=amount, currency="TRX")

    def test_valid_trx_with_superfluous_trailing_zeros_is_not_rejected(self):
        amount = Decimal("2.0000010000000000000000")
        with localcontext() as context:
            context.prec = 8
            self.assertIsInstance(invoice_commitment(order_id="order-52",
                invoice_id="invoice-52", amount=amount, currency="TRX"), str)

    def test_trx_order_cannot_persist_rounded_fractional_sun(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            with localcontext() as context:
                context.prec = 8
                with self.assertRaisesRegex(CommercialGateError, "trx_fractional_sun_forbidden"):
                    ledger.create_order(order_id="order-52", offer_id="moj-s04",
                        amount=Decimal("1.0000000000000000000000000000000001"),
                        currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "order_not_found"):
                ledger.snapshot("order-52")
            ledger.close()


    def test_private_ledger_rejects_group_writable_parent_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            folder = path.parent
            folder.chmod(0o770)
            try:
                with self.assertRaisesRegex(CommercialGateError, "ledger_parent_writable_by_others"):
                    SQLiteCommercialLedger(str(path))
                self.assertFalse(path.exists())
            finally:
                folder.chmod(0o700)


    def test_external_refund_source_whitespace_cannot_bypass_single_use(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda evidence: True)
            ledger.record_confirmed_refund(self._refund_proof(
                amount=Decimal("10"), source_id="ref-one"))
            with self.assertRaisesRegex(CommercialGateError, "refund_source_already_used"):
                ledger.record_confirmed_refund(self._refund_proof(
                    amount=Decimal("10"), source_id=" ref-one ",
                    refund_transaction_id="c" * 64))
            self.assertEqual(ledger.outstanding_settled_trx("order-52"), Decimal("20"))
            ledger.close()

    def test_refund_external_source_is_stored_without_padding(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda evidence: True)
            ledger.record_confirmed_refund(self._refund_proof(source_id=" ref-one "))
            record = ledger.connection.execute(
                "SELECT source_id FROM independently_confirmed_refunds WHERE order_id = ?",
                ("order-52",)).fetchone()
            self.assertEqual(record["source_id"], "ref-one")
            ledger.close()


    def test_refund_exact_single_sun_under_low_decimal_precision(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda evidence: True)
            with localcontext() as context:
                context.prec = 6
                ledger.record_confirmed_refund(self._refund_proof(
                    amount=Decimal("11.000001")))
                self.assertEqual(ledger.outstanding_settled_trx("order-52"),
                                 Decimal("18.999999"))
                db_sun = ledger.connection.execute(
                    "SELECT amount_sun FROM independently_confirmed_refunds WHERE order_id = ?",
                    ("order-52",)).fetchone()["amount_sun"]
                self.assertEqual(db_sun, 11000001)
            ledger.close()

    def test_exact_fractional_refund_is_not_overrounded_above_paid_total(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda proof: True)
            with localcontext() as context:
                context.prec = 6
                ledger.record_confirmed_refund(self._refund_proof(
                    amount=Decimal("29.999999")))
                self.assertEqual(ledger.outstanding_settled_trx("order-52"),
                                 Decimal("0.000001"))
                with self.assertRaisesRegex(CommercialGateError, "refund_exceeds_original_payment"):
                    ledger.record_confirmed_refund(self._refund_proof(
                        amount=Decimal("0.000002"), refund_transaction_id="c" * 64))
            ledger.close()

    def test_refund_net_amount_remains_exact_with_large_trx_values(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda proof: True)
            ledger.record_confirmed_refund(self._refund_proof(
                amount=Decimal("0.000001")))
            with localcontext() as context:
                context.prec = 5
                self.assertEqual(ledger.outstanding_settled_trx("order-52"),
                                 Decimal("29.999999"))
            ledger.close()


    def test_invalid_fulfillment_jump_cannot_call_external_delivery_verifier(self):
        with tempfile.TemporaryDirectory() as directory:
            invoked = []
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"),
                delivery_verifier=lambda order, manifest: invoked.append(order) or True)
            ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                amount=Decimal("30"), currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "invalid_state_transition"):
                ledger.advance(order_id="order-52", target=CommercialState.FULFILLED,
                               event_id="wrong-jump-52", payload_digest="b" * 64,
                               fulfillment_manifest_sha256="b" * 64)
            self.assertEqual(invoked, [])
            self.assertEqual(ledger.snapshot("order-52")["state"], "ordered")
            ledger.close()

    def test_invalid_settlement_jump_cannot_call_external_payment_verifier(self):
        with tempfile.TemporaryDirectory() as directory:
            invoked = []
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"),
                settlement_verifier=lambda ev: invoked.append(ev) or True)
            ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                amount=Decimal("30"), currency="TRX")
            ev = self.payment()
            digest = validate_payment_evidence(ev, expected_order_id="order-52",
                expected_invoice_id="invoice-52", expected_amount=Decimal("30"),
                expected_currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "invalid_state_transition"):
                ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                               event_id="wrong-settle-52", payload_digest=digest,
                               payment_evidence=ev)
            self.assertEqual(invoked, [])
            self.assertEqual(ledger.snapshot("order-52")["state"], "ordered")
            ledger.close()


    def test_private_ledger_nested_ancestor_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            actual = root / "actual"
            (actual / "child").mkdir(parents=True)
            (root / "alias").symlink_to(actual, target_is_directory=True)
            db = root / "alias" / "child" / "ledger.sqlite3"
            with self.assertRaisesRegex(CommercialGateError, "ledger_parent_missing_or_symlink"):
                SQLiteCommercialLedger(str(db))
            self.assertFalse((actual / "child" / "ledger.sqlite3").exists())

    def test_private_ledger_nested_ancestor_symlink_is_denied_on_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            actual = root / "actual"
            (actual / "child").mkdir(parents=True)
            db = actual / "child" / "ledger.sqlite3"
            ledger = SQLiteCommercialLedger(str(db))
            ledger.close()
            (root / "alias").symlink_to(actual, target_is_directory=True)
            with self.assertRaisesRegex(CommercialGateError, "ledger_parent_missing_or_symlink"):
                SQLiteCommercialLedger(str(root / "alias" / "child" / "ledger.sqlite3"))


    def test_only_single_bot_identity_can_dispatch_nonfinancial_service(self):
        approved = self.offer(offer_type=OfferType.SIGNAL,
            active=True, owner_approved=True, legal_reviewed=True,
            kyc_ready=True, rights_cleared=True)
        with self.assertRaisesRegex(CommercialGateError, "single_bot_identity_required"):
            authorize_nonfinancial_signal_dispatch(
                requested_action="research_summary", bot_identity="legacy-worker",
                offer=approved, tenant_registry={"moj_prop": "mojplaywin.com"},
                independent_release_verifier=lambda offer: True)

    def test_draft_signal_offer_cannot_dispatch_even_with_registered_host(self):
        with self.assertRaisesRegex(CommercialGateError, "signal_offer_not_authorized_for_dispatch"):
            authorize_nonfinancial_signal_dispatch(
                requested_action="research_summary", bot_identity="mojtaba-bot-ai",
                offer=self.offer(offer_type=OfferType.SIGNAL),
                tenant_registry={"moj_prop": "mojplaywin.com"},
                independent_release_verifier=lambda offer: True)

    def test_nonfinancial_signal_dispatch_rejects_unapproved_hostname(self):
        approved = self.offer(offer_type=OfferType.SIGNAL,
            active=True, owner_approved=True, legal_reviewed=True,
            kyc_ready=True, rights_cleared=True)
        with self.assertRaisesRegex(CommercialGateError, "tenant_scope_mismatch"):
            authorize_nonfinancial_signal_dispatch(
                requested_action="research_summary", bot_identity="mojtaba-bot-ai",
                offer=approved, tenant_registry={"moj_prop": "other.example"},
                independent_release_verifier=lambda offer: True)

    def test_nonfinancial_signal_dispatch_denies_trading_instruction(self):
        approved = self.offer(offer_type=OfferType.SIGNAL,
            active=True, owner_approved=True, legal_reviewed=True,
            kyc_ready=True, rights_cleared=True)
        with self.assertRaisesRegex(CommercialGateError, "financial_signal_disabled"):
            authorize_nonfinancial_signal_dispatch(
                requested_action="buy_gold_now", bot_identity="mojtaba-bot-ai",
                offer=approved, tenant_registry={"moj_prop": "mojplaywin.com"},
                independent_release_verifier=lambda offer: True)

    def test_nonfinancial_signal_dispatch_requires_independent_release(self):
        approved = self.offer(offer_type=OfferType.SIGNAL,
            active=True, owner_approved=True, legal_reviewed=True,
            kyc_ready=True, rights_cleared=True)
        with self.assertRaisesRegex(CommercialGateError, "independent_release_unverified"):
            authorize_nonfinancial_signal_dispatch(
                requested_action="research_summary", bot_identity="mojtaba-bot-ai",
                offer=approved, tenant_registry={"moj_prop": "mojplaywin.com"},
                independent_release_verifier=lambda offer: False)

    def test_valid_single_bot_signal_dispatch_guard_is_source_only(self):
        approved = self.offer(offer_type=OfferType.SIGNAL,
            active=True, owner_approved=True, legal_reviewed=True,
            kyc_ready=True, rights_cleared=True)
        self.assertIsNone(authorize_nonfinancial_signal_dispatch(
            requested_action="research_summary", bot_identity="mojtaba-bot-ai",
            offer=approved, tenant_registry={"moj_prop": "mojplaywin.com"},
            independent_release_verifier=lambda offer: True))


    def _approved_manual_trx_merchant(self, **changes):
        return self.offer(offer_type=OfferType.TRX_GATEWAY,
            active=True, owner_approved=True, legal_reviewed=True,
            kyc_ready=True, rights_cleared=True, **changes)

    def test_merchant_receipt_must_come_from_trx_merchant_offer(self):
        with self.assertRaisesRegex(CommercialGateError, "trx_merchant_offer_required"):
            validate_merchant_trx_receipt(
                offer=self.offer(), tenant_registry={"moj_prop": "mojplaywin.com"},
                independent_release_verifier=lambda offer: True,
                evidence=self.payment(), expected_order_id="order-52",
                expected_invoice_id="invoice-52")

    def test_draft_trx_gateway_cannot_claim_merchant_settlement(self):
        with self.assertRaisesRegex(CommercialGateError, "trx_merchant_not_authorized"):
            validate_merchant_trx_receipt(
                offer=self.offer(offer_type=OfferType.TRX_GATEWAY),
                tenant_registry={"moj_prop": "mojplaywin.com"},
                independent_release_verifier=lambda offer: True,
                evidence=self.payment(), expected_order_id="order-52",
                expected_invoice_id="invoice-52")

    def test_trx_merchant_receipt_denies_wrong_tenant_host_even_with_valid_tx(self):
        with self.assertRaisesRegex(CommercialGateError, "tenant_scope_mismatch"):
            validate_merchant_trx_receipt(
                offer=self._approved_manual_trx_merchant(),
                tenant_registry={"moj_prop": "other.example"},
                independent_release_verifier=lambda offer: True,
                evidence=self.payment(), expected_order_id="order-52",
                expected_invoice_id="invoice-52")

    def test_trx_merchant_receipt_requires_independent_release_approval(self):
        with self.assertRaisesRegex(CommercialGateError, "independent_release_unverified"):
            validate_merchant_trx_receipt(
                offer=self._approved_manual_trx_merchant(),
                tenant_registry={"moj_prop": "mojplaywin.com"},
                independent_release_verifier=lambda offer: False,
                evidence=self.payment(), expected_order_id="order-52",
                expected_invoice_id="invoice-52")

    def test_trx_merchant_receipt_rejects_wrong_invoice_price(self):
        with self.assertRaisesRegex(CommercialGateError, "payment_amount_mismatch"):
            validate_merchant_trx_receipt(
                offer=self._approved_manual_trx_merchant(),
                tenant_registry={"moj_prop": "mojplaywin.com"},
                independent_release_verifier=lambda offer: True,
                evidence=self.payment(amount=Decimal("29")),
                expected_order_id="order-52", expected_invoice_id="invoice-52")

    def test_trx_merchant_receipt_produces_only_private_digest(self):
        digest = validate_merchant_trx_receipt(
            offer=self._approved_manual_trx_merchant(),
            tenant_registry={"moj_prop": "mojplaywin.com"},
            independent_release_verifier=lambda offer: True,
            evidence=self.payment(), expected_order_id="order-52",
            expected_invoice_id="invoice-52")
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, validate_payment_evidence(
            self.payment(), expected_order_id="order-52",
            expected_invoice_id="invoice-52", expected_amount=Decimal("30"),
            expected_currency="TRX"))


    def _candidate_bot_ai_offer(self, **changes):
        return self.offer(canonical_host="mojtaba.bot.ai", active=True,
                          owner_approved=True, legal_reviewed=True,
                          kyc_ready=True, rights_cleared=True, **changes)

    def test_bot_ai_brand_host_never_counts_as_delegated_domain_without_proof(self):
        with self.assertRaisesRegex(CommercialGateError, "independent_domain_delegation_required"):
            validate_offer(self._candidate_bot_ai_offer(),
                tenant_registry={"moj_prop": "mojtaba.bot.ai"},
                independent_release_verifier=lambda offer: True)

    def test_bot_ai_delegation_false_or_truthy_string_never_releases_host(self):
        for verdict in (False, "true", 1, None):
            with self.subTest(verdict=verdict):
                with self.assertRaisesRegex(CommercialGateError, "domain_delegation_unverified"):
                    validate_offer(self._candidate_bot_ai_offer(),
                        tenant_registry={"moj_prop": "mojtaba.bot.ai"},
                        independent_release_verifier=lambda offer: True,
                        independent_domain_delegation_verifier=lambda host: verdict)

    def test_bot_ai_delegation_adapter_exception_fails_closed(self):
        def unavailable(_):
            raise ConnectionError("registry unavailable")
        with self.assertRaisesRegex(CommercialGateError, "domain_delegation_verifier_failed"):
            validate_offer(self._candidate_bot_ai_offer(),
                tenant_registry={"moj_prop": "mojtaba.bot.ai"},
                independent_release_verifier=lambda offer: True,
                independent_domain_delegation_verifier=unavailable)

    def test_bot_ai_delegation_validator_input_must_be_callable(self):
        with self.assertRaisesRegex(CommercialGateError, "delegation_verifier_invalid"):
            validate_offer(self._candidate_bot_ai_offer(),
                tenant_registry={"moj_prop": "mojtaba.bot.ai"},
                independent_release_verifier=lambda offer: True,
                independent_domain_delegation_verifier="trusted")

    def test_verified_delegation_is_only_source_preflight_not_live_site(self):
        self.assertIsNone(validate_offer(self._candidate_bot_ai_offer(),
            tenant_registry={"moj_prop": "mojtaba.bot.ai"},
            independent_release_verifier=lambda offer: True,
            independent_domain_delegation_verifier=lambda host: host == "mojtaba.bot.ai"))

    def test_single_bot_dispatch_requires_domain_delegation_even_if_release_approved(self):
        offer = self._candidate_bot_ai_offer(offer_type=OfferType.SIGNAL)
        with self.assertRaisesRegex(CommercialGateError, "independent_domain_delegation_required"):
            authorize_nonfinancial_signal_dispatch(
                requested_action="research_summary", bot_identity="mojtaba-bot-ai",
                offer=offer, tenant_registry={"moj_prop": "mojtaba.bot.ai"},
                independent_release_verifier=lambda offer: True)
        self.assertIsNone(authorize_nonfinancial_signal_dispatch(
            requested_action="research_summary", bot_identity="mojtaba-bot-ai",
            offer=offer, tenant_registry={"moj_prop": "mojtaba.bot.ai"},
            independent_release_verifier=lambda offer: True,
            independent_domain_delegation_verifier=lambda host: True))


    def test_refund_provider_reviews_same_normalized_fields_as_persisted_record(self):
        with tempfile.TemporaryDirectory() as directory:
            reviewed = []
            ledger = self._refundable_ledger(directory,
                refund_verifier=lambda proof: reviewed.append(proof) or True)
            ledger.record_confirmed_refund(self._refund_proof(
                source_id=" source-52 ", original_transaction_id="A" * 64,
                refund_transaction_id="B" * 64))
            self.assertEqual(len(reviewed), 1)
            self.assertEqual(reviewed[0].source_id, "source-52")
            self.assertEqual(reviewed[0].original_transaction_id, "a" * 64)
            self.assertEqual(reviewed[0].refund_transaction_id, "b" * 64)
            db = ledger.connection.execute(
                "SELECT refund_tx, source_id FROM independently_confirmed_refunds WHERE order_id = ?",
                ("order-52",)).fetchone()
            self.assertEqual(db["refund_tx"], reviewed[0].refund_transaction_id)
            self.assertEqual(db["source_id"], reviewed[0].source_id)
            ledger.close()


    def test_external_settlement_reviews_canonical_trx_receipt_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            reviewed = []
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"),
                settlement_verifier=lambda proof: reviewed.append(proof) or True)
            self._prepare_private_invoice(ledger, "order-52")
            ev = self.payment(
                provider=" manual-review ", transaction_id="A" * 64,
                amount=Decimal("30.000000"))
            digest = validate_payment_evidence(ev,
                expected_order_id="order-52", expected_invoice_id="invoice-52",
                expected_amount=Decimal("30"), expected_currency="TRX")
            ledger.advance(order_id="order-52", target=CommercialState.SETTLED,
                           event_id="settle-52", payload_digest=digest,
                           payment_evidence=ev)
            self.assertEqual(len(reviewed), 1)
            self.assertEqual(reviewed[0].transaction_id, "a" * 64)
            self.assertEqual(reviewed[0].provider, "manual-review")
            self.assertEqual(reviewed[0].amount.as_tuple().exponent, 0)
            ledger.close()


    def test_trx_reconciliation_totals_exclude_unpaid_orders_and_state_revenue_claims(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                amount=Decimal("30"), currency="TRX")
            totals = ledger.private_trx_reconciliation_totals()
            self.assertEqual(totals["settled_order_count"], 0)
            self.assertEqual(totals["outstanding_sun"], 0)
            self.assertIs(totals["independent_live_revenue_verified"], False)
            ledger.close()

    def test_private_trx_totals_aggregate_valid_settlement_and_refunds_without_rounding(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda ev: True)
            self._prepare_private_invoice(ledger, "order-53")
            ev = self.payment(order_id="order-53", invoice_id="invoice-53",
                              transaction_id="c" * 64)
            digest = validate_payment_evidence(ev,
                expected_order_id="order-53", expected_invoice_id="invoice-53",
                expected_amount=Decimal("30"), expected_currency="TRX")
            ledger.advance(order_id="order-53", target=CommercialState.SETTLED,
                           event_id="settled-order-53", payload_digest=digest, payment_evidence=ev)
            with localcontext() as context:
                context.prec = 6
                ledger.record_confirmed_refund(self._refund_proof(
                    amount=Decimal("11.000001")))
                total = ledger.private_trx_reconciliation_totals()
                self.assertEqual(total["settled_order_count"], 2)
                self.assertEqual(total["original_sun"], 60000000)
                self.assertEqual(total["refunded_sun"], 11000001)
                self.assertEqual(total["outstanding_sun"], 48999999)
                self.assertIs(total["independent_live_revenue_verified"], False)
            ledger.close()


    def _approved_merchant_offer_for_binding(self, **kw):
        return self.offer(active=True, owner_approved=True, legal_reviewed=True,
                          kyc_ready=True, rights_cleared=True, **kw)

    def test_merchant_binding_persists_exact_approved_tenant_and_host(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "ledger.sqlite3")
            ledger = SQLiteCommercialLedger(path)
            ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                amount=Decimal("30"), currency="TRX")
            ledger.bind_approved_merchant_order(
                order_id="order-52", offer=self._approved_merchant_offer_for_binding(),
                tenant_registry={"moj_prop": "mojplaywin.com"},
                independent_release_verifier=lambda offer: True,
                release_evidence_sha256="d" * 64,
                    independent_release_evidence_verifier=lambda offer, digest: True)
            ledger.close()
            restored = SQLiteCommercialLedger(path)
            binding = restored.connection.execute(
                "SELECT * FROM merchant_order_bindings WHERE order_id = ?", ("order-52",)
            ).fetchone()
            self.assertEqual(binding["tenant_id"], "moj_prop")
            self.assertEqual(binding["canonical_host"], "mojplaywin.com")
            self.assertEqual(binding["offer_id"], "moj-s04")
            self.assertEqual(binding["release_evidence_sha256"], "d" * 64)
            restored.close()

    def test_merchant_binding_does_not_accept_wrong_offer_or_price(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                amount=Decimal("30"), currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "merchant_order_offer_mismatch"):
                ledger.bind_approved_merchant_order(
                    order_id="order-52",
                    offer=self._approved_merchant_offer_for_binding(price=Decimal("31")),
                    tenant_registry={"moj_prop": "mojplaywin.com"},
                    independent_release_verifier=lambda offer: True,
                    release_evidence_sha256="d" * 64,
                    independent_release_evidence_verifier=lambda offer, digest: True)
            self.assertIsNone(ledger.connection.execute(
                "SELECT 1 FROM merchant_order_bindings WHERE order_id = ?", ("order-52",)
            ).fetchone())
            ledger.close()

    def test_merchant_binding_requires_independent_release_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                amount=Decimal("30"), currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "independent_release_unverified"):
                ledger.bind_approved_merchant_order(
                    order_id="order-52", offer=self._approved_merchant_offer_for_binding(),
                    tenant_registry={"moj_prop": "mojplaywin.com"},
                    independent_release_verifier=lambda offer: False,
                    release_evidence_sha256="d" * 64,
                    independent_release_evidence_verifier=lambda offer, digest: True)
            ledger.close()

    def test_merchant_binding_is_immutable_and_single_use(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                amount=Decimal("30"), currency="TRX")
            kw = dict(order_id="order-52", offer=self._approved_merchant_offer_for_binding(),
                      tenant_registry={"moj_prop": "mojplaywin.com"},
                      independent_release_verifier=lambda offer: True,
                      release_evidence_sha256="d" * 64,
                    independent_release_evidence_verifier=lambda offer, digest: True)
            ledger.bind_approved_merchant_order(**kw)
            with self.assertRaisesRegex(CommercialGateError, "merchant_order_already_bound"):
                ledger.bind_approved_merchant_order(**kw)
            with self.assertRaisesRegex(sqlite3.DatabaseError, "immutable_merchant_binding"):
                ledger.connection.execute(
                    "UPDATE merchant_order_bindings SET tenant_id = ? WHERE order_id = ?",
                    ("other", "order-52"))
            ledger.connection.rollback()
            ledger.close()

    def test_merchant_binding_cannot_be_added_after_payment_settlement(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self._refundable_ledger(directory, refund_verifier=lambda ev: True)
            with self.assertRaisesRegex(CommercialGateError, "merchant_binding_after_settlement_forbidden"):
                ledger.bind_approved_merchant_order(
                    order_id="order-52", offer=self._approved_merchant_offer_for_binding(),
                    tenant_registry={"moj_prop": "mojplaywin.com"},
                    independent_release_verifier=lambda offer: True,
                    release_evidence_sha256="d" * 64,
                    independent_release_evidence_verifier=lambda offer, digest: True)
            ledger.close()


    def _bound_trx_merchant_ledger(self, directory):
        ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
        self._prepare_private_invoice(ledger, "order-52")
        offer = self._approved_merchant_offer_for_binding(offer_type=OfferType.TRX_GATEWAY)
        ledger.bind_approved_merchant_order(
            order_id="order-52", offer=offer,
            tenant_registry={"moj_prop": "mojplaywin.com"},
            independent_release_verifier=lambda offer: True,
            release_evidence_sha256="d" * 64,
                    independent_release_evidence_verifier=lambda offer, digest: True)
        return ledger, offer

    def test_merchant_trx_review_requires_durable_merchant_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            self._prepare_private_invoice(ledger, "order-52")
            with self.assertRaisesRegex(CommercialGateError, "merchant_order_binding_required"):
                ledger.verify_bound_merchant_receipt(
                    order_id="order-52", offer=self._approved_merchant_offer_for_binding(
                        offer_type=OfferType.TRX_GATEWAY),
                    evidence=self.payment(), invoice_id="invoice-52",
                    tenant_registry={"moj_prop": "mojplaywin.com"},
                    independent_release_verifier=lambda offer: True)
            ledger.close()

    def test_merchant_trx_review_denies_cross_tenant_bound_order(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger, offer = self._bound_trx_merchant_ledger(directory)
            wrong = self._approved_merchant_offer_for_binding(
                offer_type=OfferType.TRX_GATEWAY, canonical_host="another.example")
            with self.assertRaisesRegex(CommercialGateError, "merchant_order_binding_mismatch"):
                ledger.verify_bound_merchant_receipt(
                    order_id="order-52", offer=wrong, evidence=self.payment(),
                    invoice_id="invoice-52",
                    tenant_registry={"moj_prop": "another.example"},
                    independent_release_verifier=lambda offer: True)
            ledger.close()

    def test_merchant_trx_review_rejects_nonissued_invoice_before_external_release(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                amount=Decimal("30"), currency="TRX")
            offer = self._approved_merchant_offer_for_binding(
                offer_type=OfferType.TRX_GATEWAY)
            ledger.bind_approved_merchant_order(
                order_id="order-52", offer=offer,
                tenant_registry={"moj_prop": "mojplaywin.com"},
                independent_release_verifier=lambda offer: True,
                release_evidence_sha256="d" * 64,
                    independent_release_evidence_verifier=lambda offer, digest: True)
            calls = []
            with self.assertRaisesRegex(CommercialGateError, "bound_merchant_invoice_required"):
                ledger.verify_bound_merchant_receipt(
                    order_id="order-52", offer=offer,
                    evidence=self.payment(), invoice_id="invoice-52",
                    tenant_registry={"moj_prop": "mojplaywin.com"},
                    independent_release_verifier=lambda offer: calls.append(offer) or True)
            self.assertEqual(calls, [])
            ledger.close()

    def test_valid_durable_merchant_trx_receipt_preflight_returns_only_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger, offer = self._bound_trx_merchant_ledger(directory)
            digest = ledger.verify_bound_merchant_receipt(
                order_id="order-52", offer=offer,
                evidence=self.payment(), invoice_id="invoice-52",
                tenant_registry={"moj_prop": "mojplaywin.com"},
                independent_release_verifier=lambda offer: True)
            self.assertEqual(len(digest), 64)
            self.assertEqual(ledger.snapshot("order-52")["state"], "payment_pending")
            ledger.close()


    def test_merchant_release_evidence_hash_requires_independent_attestation(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                amount=Decimal("30"), currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "merchant_release_evidence_unverified"):
                ledger.bind_approved_merchant_order(
                    order_id="order-52", offer=self._approved_merchant_offer_for_binding(),
                    tenant_registry={"moj_prop": "mojplaywin.com"},
                    independent_release_verifier=lambda offer: True,
                    release_evidence_sha256="d" * 64,
                    independent_release_evidence_verifier=lambda offer, digest: False)
            self.assertIsNone(ledger.connection.execute(
                "SELECT 1 FROM merchant_order_bindings WHERE order_id = ?", ("order-52",)
            ).fetchone())
            ledger.close()

    def test_merchant_release_evidence_verifier_must_be_callable(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteCommercialLedger(str(Path(directory) / "ledger.sqlite3"))
            ledger.create_order(order_id="order-52", offer_id="moj-s04",
                                amount=Decimal("30"), currency="TRX")
            with self.assertRaisesRegex(CommercialGateError, "merchant_release_evidence_verifier_invalid"):
                ledger.bind_approved_merchant_order(
                    order_id="order-52", offer=self._approved_merchant_offer_for_binding(),
                    tenant_registry={"moj_prop": "mojplaywin.com"},
                    independent_release_verifier=lambda offer: True,
                    release_evidence_sha256="d" * 64,
                    independent_release_evidence_verifier="yes")
            ledger.close()


if __name__ == "__main__":
    unittest.main()

