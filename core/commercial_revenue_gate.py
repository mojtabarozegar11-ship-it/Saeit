"""Fail-closed commercial contract for Mojtaba.bot.ai revenue paths.

This dependency-free module is a governed source artifact, not a payment API.
It records and validates order evidence but never contacts a provider, moves
TRX, places a trade, publishes a signal, or grants a download by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import json
import re
import sqlite3
from typing import Mapping, Optional


class CommercialGateError(ValueError):
    """Raised when a commercial transition cannot be proven safely."""


class OfferType(str, Enum):
    MOJ_PROP = "moj_prop"
    SIGNAL = "signal"
    TRX_GATEWAY = "trx_gateway"
    DIGITAL_PRODUCT = "digital_product"
    GAME = "game"


class CommercialState(str, Enum):
    ORDERED = "ordered"
    QUOTED = "quoted"
    INVOICED = "invoiced"
    PAYMENT_PENDING = "payment_pending"
    SETTLED = "settled"
    FULFILLMENT_PENDING = "fulfillment_pending"
    FULFILLED = "fulfilled"
    VERIFIED_REVENUE = "verified_revenue"


STATE_ORDER = (
    CommercialState.ORDERED,
    CommercialState.QUOTED,
    CommercialState.INVOICED,
    CommercialState.PAYMENT_PENDING,
    CommercialState.SETTLED,
    CommercialState.FULFILLMENT_PENDING,
    CommercialState.FULFILLED,
    CommercialState.VERIFIED_REVENUE,
)

_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
_HOST = re.compile(r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TX = re.compile(r"^[A-Za-z0-9:_-]{8,256}$")
_BLOCKED_SIGNAL_WORDS = frozenset(
    {"buy", "sell", "hold", "long", "short", "entry", "exit", "trade", "order"}
)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CommercialGateError(f"{field}_required")
    return value.strip()


def _slug(value: object, field: str) -> str:
    value = _text(value, field)
    if not _SLUG.fullmatch(value):
        raise CommercialGateError(f"{field}_invalid")
    return value


def _amount(value: object, field: str = "amount") -> Decimal:
    if not isinstance(value, Decimal):
        raise CommercialGateError(f"{field}_must_be_decimal")
    if not value.is_finite() or value <= Decimal("0"):
        raise CommercialGateError(f"{field}_must_be_finite_positive")
    return value


def _currency(value: object) -> str:
    value = _text(value, "currency")
    if value != value.upper() or not re.fullmatch(r"[A-Z0-9]{2,10}", value):
        raise CommercialGateError("currency_must_be_canonical_uppercase")
    return value


def _digest(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class OfferContract:
    offer_id: str
    offer_type: OfferType
    tenant_id: str
    canonical_host: str
    currency: str
    price: Decimal
    owner_approved: bool = False
    legal_reviewed: bool = False
    kyc_ready: bool = False
    rights_cleared: bool = False
    public_wallet_published: bool = False
    automatic_payment_enabled: bool = False
    financial_call_enabled: bool = False
    delivery_manifest_sha256: str = ""
    active: bool = False


def validate_offer(
    offer: OfferContract,
    *,
    tenant_registry: Optional[Mapping[str, str]] = None,
) -> None:
    """Validate an offer without making it public or payable."""
    offer_id = _slug(offer.offer_id, "offer_id")
    tenant_id = _slug(offer.tenant_id, "tenant_id")
    host = _text(offer.canonical_host, "canonical_host").lower()
    if host != offer.canonical_host or "://" in host or "/" in host or not _HOST.fullmatch(host):
        raise CommercialGateError("canonical_host_invalid")
    _currency(offer.currency)
    _amount(offer.price, "price")
    if not isinstance(offer.offer_type, OfferType):
        raise CommercialGateError("offer_type_invalid")
    if tenant_registry is not None and tenant_registry.get(tenant_id) != host:
        raise CommercialGateError("tenant_scope_mismatch")
    if offer.public_wallet_published:
        raise CommercialGateError("public_wallet_prohibited")
    if offer.automatic_payment_enabled:
        raise CommercialGateError("automatic_payment_disabled")
    if offer.offer_type is OfferType.SIGNAL and offer.financial_call_enabled:
        raise CommercialGateError("financial_signal_disabled")
    if offer.offer_type is OfferType.MOJ_PROP and offer.active:
        required = (offer.owner_approved, offer.legal_reviewed, offer.kyc_ready, offer.rights_cleared)
        if not all(required):
            raise CommercialGateError("moj_prop_release_gates_incomplete")
    if offer.active and not offer.owner_approved:
        raise CommercialGateError("owner_approval_required")
    if offer.delivery_manifest_sha256 and not _HEX64.fullmatch(offer.delivery_manifest_sha256):
        raise CommercialGateError("delivery_manifest_hash_invalid")
    if offer_id == "" or tenant_id == "":  # defensive; _slug already rejects these
        raise CommercialGateError("offer_identity_invalid")


def validate_signal_request(*, requested_action: str, financial_authorized: bool = False) -> None:
    """Block investment calls while allowing research/operational services."""
    action = _text(requested_action, "requested_action").lower()
    if action in _BLOCKED_SIGNAL_WORDS or financial_authorized:
        raise CommercialGateError("financial_signal_disabled")


@dataclass(frozen=True)
class PaymentEvidence:
    order_id: str
    invoice_id: str
    provider: str
    network: str
    asset: str
    amount: Decimal
    currency: str
    transaction_id: str
    chain_finalized: bool
    amount_matches: bool
    recipient_matches_private_invoice: bool
    independently_reconciled: bool
    human_reviewed: bool


def validate_payment_evidence(
    evidence: PaymentEvidence,
    *,
    expected_order_id: str,
    expected_invoice_id: str,
    expected_amount: Decimal,
    expected_currency: str,
) -> str:
    """Return a stable digest only for a complete, manually reviewed TRX proof."""
    if evidence.order_id != _text(expected_order_id, "expected_order_id"):
        raise CommercialGateError("payment_order_mismatch")
    if evidence.invoice_id != _text(expected_invoice_id, "expected_invoice_id"):
        raise CommercialGateError("payment_invoice_mismatch")
    if _text(evidence.provider, "provider") == "not_configured":
        raise CommercialGateError("payment_provider_not_configured")
    if evidence.network != "TRON" or evidence.asset != "TRX":
        raise CommercialGateError("payment_chain_asset_mismatch")
    amount = _amount(evidence.amount)
    if amount != _amount(expected_amount, "expected_amount"):
        raise CommercialGateError("payment_amount_mismatch")
    currency = _currency(evidence.currency)
    if currency != _currency(expected_currency):
        raise CommercialGateError("payment_currency_mismatch")
    transaction_id = _text(evidence.transaction_id, "transaction_id")
    if not _TX.fullmatch(transaction_id):
        raise CommercialGateError("transaction_id_invalid")
    if not all((evidence.chain_finalized, evidence.amount_matches,
                evidence.recipient_matches_private_invoice,
                evidence.independently_reconciled, evidence.human_reviewed)):
        raise CommercialGateError("payment_evidence_incomplete")
    return _digest({
        "order_id": evidence.order_id,
        "invoice_id": evidence.invoice_id,
        "provider": evidence.provider.strip(),
        "network": evidence.network,
        "asset": evidence.asset,
        "amount": str(amount),
        "currency": currency,
        "transaction_id": transaction_id,
    })


def transition_state(
    current: CommercialState,
    target: CommercialState,
    *,
    payment_evidence: Optional[PaymentEvidence] = None,
    fulfillment_manifest_sha256: str = "",
    verified_revenue: bool = False,
) -> CommercialState:
    """Allow exactly one governed step; never skip a payment or delivery gate."""
    try:
        expected = STATE_ORDER[STATE_ORDER.index(current) + 1]
    except (ValueError, IndexError):
        raise CommercialGateError("invalid_state_transition") from None
    if target is not expected:
        raise CommercialGateError("invalid_state_transition")
    if target is CommercialState.SETTLED and payment_evidence is None:
        raise CommercialGateError("settlement_evidence_required")
    if target is CommercialState.FULFILLED:
        if not _HEX64.fullmatch(fulfillment_manifest_sha256):
            raise CommercialGateError("fulfillment_manifest_required")
    if target is CommercialState.VERIFIED_REVENUE and not verified_revenue:
        raise CommercialGateError("verified_revenue_attestation_required")
    return target


class SQLiteCommercialLedger:
    """Small durable, append-only order ledger for private governed staging."""

    def __init__(self, path: str):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                offer_id TEXT NOT NULL,
                state TEXT NOT NULL,
                amount TEXT NOT NULL,
                currency TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS order_events (
                event_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL REFERENCES orders(order_id),
                state TEXT NOT NULL,
                payload_digest TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS order_events_order_idx ON order_events(order_id);
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def create_order(self, *, order_id: str, offer_id: str, amount: Decimal, currency: str) -> None:
        order_id = _slug(order_id, "order_id")
        offer_id = _slug(offer_id, "offer_id")
        amount = _amount(amount)
        currency = _currency(currency)
        now = datetime.now(timezone.utc).isoformat()
        digest = _digest({"order_id": order_id, "offer_id": offer_id, "amount": str(amount), "currency": currency})
        try:
            with self.connection:
                self.connection.execute(
                    "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (order_id, offer_id, CommercialState.ORDERED.value, str(amount), currency, now, now),
                )
                self.connection.execute(
                    "INSERT INTO order_events VALUES (?, ?, ?, ?, ?)",
                    (f"create:{order_id}", order_id, CommercialState.ORDERED.value, digest, now),
                )
        except sqlite3.IntegrityError as exc:
            raise CommercialGateError("order_already_exists") from exc

    def advance(
        self,
        *,
        order_id: str,
        target: CommercialState,
        event_id: str,
        payload_digest: str,
        payment_evidence: Optional[PaymentEvidence] = None,
        fulfillment_manifest_sha256: str = "",
        verified_revenue: bool = False,
    ) -> CommercialState:
        order_id = _slug(order_id, "order_id")
        event_id = _text(event_id, "event_id")
        if not _HEX64.fullmatch(payload_digest):
            raise CommercialGateError("payload_digest_invalid")
        with self.connection:
            row = self.connection.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
            if row is None:
                raise CommercialGateError("order_not_found")
            prior = self.connection.execute(
                "SELECT payload_digest, state FROM order_events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if prior is not None:
                if prior["payload_digest"] != payload_digest:
                    raise CommercialGateError("event_replay_mismatch")
                return CommercialState(prior["state"])
            current = CommercialState(row["state"])
            next_value = transition_state(
                current, target, payment_evidence=payment_evidence,
                fulfillment_manifest_sha256=fulfillment_manifest_sha256,
                verified_revenue=verified_revenue,
            )
            now = datetime.now(timezone.utc).isoformat()
            self.connection.execute(
                "INSERT INTO order_events VALUES (?, ?, ?, ?, ?)",
                (event_id, order_id, next_value.value, payload_digest, now),
            )
            self.connection.execute(
                "UPDATE orders SET state = ?, updated_at = ? WHERE order_id = ?",
                (next_value.value, now, order_id),
            )
            return next_value

    def snapshot(self, order_id: str) -> Mapping[str, str]:
        row = self.connection.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if row is None:
            raise CommercialGateError("order_not_found")
        return dict(row)

