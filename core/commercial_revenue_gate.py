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
import os
from pathlib import Path
import re
import sqlite3
import stat
from typing import Callable, Mapping, Optional


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
_TRON_TX = re.compile(r"^[0-9a-fA-F]{64}$")
# Only canonical non-financial deliverables may be requested. A blacklist
# can be bypassed with concatenation, other scripts, or mixed-language prompts.
_ALLOWED_NONFINANCIAL_SIGNAL_ACTIONS = frozenset({
    "research_summary",
    "operational_alert",
    "agricultural_cost_report",
    "service_quality_report",
})


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
    # Bounded staged monetary values prevent accidental allocation / reporting overflow.
    if value > Decimal("1000000000000000"):
        raise CommercialGateError(f"{field}_exceeds_safety_cap")
    return value


def _currency(value: object) -> str:
    value = _text(value, "currency")
    if value != value.upper() or not re.fullmatch(r"[A-Z0-9]{2,10}", value):
        raise CommercialGateError("currency_must_be_canonical_uppercase")
    return value


def _validate_trx_sun_precision(value: Decimal, currency: str) -> None:
    """TRON native TRX settles in integer SUN, never fractional SUN."""
    if currency == "TRX":
        sun = value * Decimal("1000000")
        if sun != sun.to_integral_value():
            raise CommercialGateError("trx_fractional_sun_forbidden")


def _digest(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def invoice_commitment(*, order_id: str, invoice_id: str, amount: Decimal, currency: str) -> str:
    """Bind an issued invoice reference to immutable amount and denomination."""
    return _digest({
        "order_id": _slug(order_id, "order_id"),
        "invoice_id": _slug(invoice_id, "invoice_id"),
        "amount": str(_amount(amount)),
        "currency": _currency(currency),
    })


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
    if not isinstance(offer, OfferContract):
        raise CommercialGateError("offer_contract_required")
    offer_id = _slug(offer.offer_id, "offer_id")
    tenant_id = _slug(offer.tenant_id, "tenant_id")
    host = _text(offer.canonical_host, "canonical_host").lower()
    # Host isolation must use a real canonical DNS hostname, not a string
    # such as "shop..example" that loosely matches a broad character regex.
    parts = host.split(".")
    valid_host = (
        host == offer.canonical_host
        and 4 <= len(host) <= 253
        and len(parts) >= 2
        and all(1 <= len(part) <= 63 and
                re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", part)
                for part in parts)
        and host != "dr.mojtaba.rozegar"
        and not host.endswith(".dr.mojtaba.rozegar")
    )
    if not valid_host:
        raise CommercialGateError("canonical_host_invalid")
    _currency(offer.currency)
    _amount(offer.price, "price")
    _validate_trx_sun_precision(offer.price, offer.currency)
    if offer.offer_type is OfferType.TRX_GATEWAY and offer.currency != "TRX":
        raise CommercialGateError("native_trx_gateway_currency_required")
    if not isinstance(offer.offer_type, OfferType):
        raise CommercialGateError("offer_type_invalid")
    if tenant_registry is not None and tenant_registry.get(tenant_id) != host:
        raise CommercialGateError("tenant_scope_mismatch")
    gates = (offer.owner_approved, offer.legal_reviewed, offer.kyc_ready,
             offer.rights_cleared, offer.public_wallet_published,
             offer.automatic_payment_enabled, offer.financial_call_enabled, offer.active)
    if any(type(flag) is not bool for flag in gates):
        raise CommercialGateError("offer_gates_must_be_boolean")
    if offer.public_wallet_published:
        raise CommercialGateError("public_wallet_prohibited")
    if offer.automatic_payment_enabled:
        raise CommercialGateError("automatic_payment_disabled")
    if offer.offer_type is OfferType.SIGNAL and offer.financial_call_enabled:
        raise CommercialGateError("financial_signal_disabled")
    if offer.active:
        # Source-only readiness must never accept typed truthy strings, nor
        # let non-Prop paid offers bypass legal/KYC/rights release checks.
        required = (offer.owner_approved, offer.legal_reviewed,
                    offer.kyc_ready, offer.rights_cleared)
        if not all(required):
            raise CommercialGateError(
                "moj_prop_release_gates_incomplete" if offer.offer_type is OfferType.MOJ_PROP
                else "offer_release_gates_incomplete"
            )
        # Draft offers may be inspected offline; active offers require a
        # separately supplied tenant-to-domain ownership registry.
        if tenant_registry is None:
            raise CommercialGateError("tenant_registry_required_for_activation")
        if tenant_registry.get(tenant_id) != host:
            raise CommercialGateError("tenant_scope_mismatch")
    if not isinstance(offer.delivery_manifest_sha256, str) or (
        offer.delivery_manifest_sha256 and not _HEX64.fullmatch(offer.delivery_manifest_sha256)
    ):
        raise CommercialGateError("delivery_manifest_hash_invalid")
    if offer.active and offer.offer_type in (OfferType.DIGITAL_PRODUCT, OfferType.GAME):
        # Customer-facing digital items must resolve to an immutable,
        # rights-reviewed deliverable before an offer may be active.
        if not _HEX64.fullmatch(offer.delivery_manifest_sha256):
            raise CommercialGateError("active_digital_delivery_manifest_required")
    if offer_id == "" or tenant_id == "":  # defensive; _slug already rejects these
        raise CommercialGateError("offer_identity_invalid")


def validate_signal_request(*, requested_action: str, financial_authorized: bool = False) -> None:
    """Require an exact non-financial service code; no free-text execution."""
    action = _text(requested_action, "requested_action")
    if type(financial_authorized) is not bool or financial_authorized:
        raise CommercialGateError("financial_signal_disabled")
    if action not in _ALLOWED_NONFINANCIAL_SIGNAL_ACTIONS:
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
    if not isinstance(evidence, PaymentEvidence):
        raise CommercialGateError("payment_evidence_invalid")
    expected_order_id = _slug(expected_order_id, "expected_order_id")
    expected_invoice_id = _slug(expected_invoice_id, "expected_invoice_id")
    if evidence.order_id != expected_order_id:
        raise CommercialGateError("payment_order_mismatch")
    if evidence.invoice_id != expected_invoice_id:
        raise CommercialGateError("payment_invoice_mismatch")
    provider = _slug(evidence.provider, "provider")
    if provider in {"not_configured", "none", "unknown", "test", "mock"}:
        raise CommercialGateError("payment_provider_not_configured")
    if evidence.network != "TRON" or evidence.asset != "TRX":
        raise CommercialGateError("payment_chain_asset_mismatch")
    amount = _amount(evidence.amount)
    if amount != _amount(expected_amount, "expected_amount"):
        raise CommercialGateError("payment_amount_mismatch")
    currency = _currency(evidence.currency)
    if currency != _currency(expected_currency):
        raise CommercialGateError("payment_currency_mismatch")
    if currency != "TRX":
        raise CommercialGateError("native_trx_currency_required")
    _validate_trx_sun_precision(amount, currency)
    _validate_trx_sun_precision(expected_amount, currency)
    transaction_id = _text(evidence.transaction_id, "transaction_id")
    if not _TRON_TX.fullmatch(transaction_id) or set(transaction_id) == {"0"}:
        raise CommercialGateError("transaction_id_invalid")
    transaction_id = transaction_id.lower()
    flags = (
        evidence.chain_finalized,
        evidence.amount_matches,
        evidence.recipient_matches_private_invoice,
        evidence.independently_reconciled,
        evidence.human_reviewed,
    )
    if not all(type(flag) is bool and flag for flag in flags):
        raise CommercialGateError("payment_evidence_incomplete")
    return _digest({
        "order_id": evidence.order_id,
        "invoice_id": evidence.invoice_id,
        "provider": provider,
        "network": evidence.network,
        "asset": evidence.asset,
        "amount": str(amount),
        "currency": currency,
        "transaction_id": transaction_id,
    })


def _validated_evidence_digest(
    evidence: PaymentEvidence,
    *,
    expected_order_id: str,
    expected_amount: Decimal,
    expected_currency: str,
) -> str:
    """Validate evidence against the order facts before any state transition."""
    return validate_payment_evidence(
        evidence,
        expected_order_id=expected_order_id,
        expected_invoice_id=evidence.invoice_id,
        expected_amount=expected_amount,
        expected_currency=expected_currency,
    )


def transition_state(
    current: CommercialState,
    target: CommercialState,
    *,
    payment_evidence: Optional[PaymentEvidence] = None,
    fulfillment_manifest_sha256: str = "",
    verified_revenue: bool = False,
) -> CommercialState:
    """Allow exactly one governed step; never skip a payment or delivery gate."""
    if not isinstance(current, CommercialState) or not isinstance(target, CommercialState):
        raise CommercialGateError("invalid_state_transition")
    try:
        expected = STATE_ORDER[STATE_ORDER.index(current) + 1]
    except (ValueError, IndexError):
        raise CommercialGateError("invalid_state_transition") from None
    if target is not expected:
        raise CommercialGateError("invalid_state_transition")
    if target in (CommercialState.SETTLED, CommercialState.VERIFIED_REVENUE):
        if not isinstance(payment_evidence, PaymentEvidence):
            raise CommercialGateError("settlement_evidence_required")
        _validated_evidence_digest(
            payment_evidence,
            expected_order_id=payment_evidence.order_id,
            expected_amount=payment_evidence.amount,
            expected_currency=payment_evidence.currency,
        )
    if target is CommercialState.FULFILLED:
        if not isinstance(fulfillment_manifest_sha256, str) or not _HEX64.fullmatch(fulfillment_manifest_sha256):
            raise CommercialGateError("fulfillment_manifest_required")
    if target is CommercialState.VERIFIED_REVENUE and verified_revenue is not True:
        raise CommercialGateError("verified_revenue_attestation_required")
    return target


class SQLiteCommercialLedger:
    """Small durable, append-only order ledger for private governed staging."""

    def __init__(self, path: str, *,
                 settlement_verifier: Optional[Callable[[PaymentEvidence], bool]] = None,
                 delivery_verifier: Optional[Callable[[str, str], bool]] = None):
        # No independent verification adapter means no financial completion.
        if settlement_verifier is not None and not callable(settlement_verifier):
            raise CommercialGateError("settlement_verifier_invalid")
        if delivery_verifier is not None and not callable(delivery_verifier):
            raise CommercialGateError("delivery_verifier_invalid")
        self._settlement_verifier = settlement_verifier
        self._delivery_verifier = delivery_verifier
        # This ledger contains private customer/order references and MUST NOT
        # silently become a world-readable file or follow a symlink.
        if not isinstance(path, str) or not path:
            raise CommercialGateError("ledger_path_invalid")
        memory = path == ":memory:"
        target = None if memory else Path(path)
        if target is not None:
            if target.is_symlink():
                raise CommercialGateError("ledger_symlink_prohibited")
            if not target.parent.is_dir() or target.parent.is_symlink():
                raise CommercialGateError("ledger_parent_missing_or_symlink")
            if target.parent.stat().st_mode & 0o002:
                raise CommercialGateError("ledger_parent_world_writable")
            if target.exists():
                metadata = target.stat()
                if (not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077
                        or metadata.st_nlink != 1
                        or (hasattr(os, "getuid") and metadata.st_uid != os.getuid())):
                    raise CommercialGateError("ledger_file_permissions_unsafe")
            else:
                # sqlite3.connect normally creates the file before chmod,
                # exposing private order identifiers while umask is permissive.
                if not hasattr(os, "O_NOFOLLOW"):
                    raise CommercialGateError("ledger_secure_open_unavailable")
                try:
                    fd = os.open(
                        str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                    )
                except FileExistsError:
                    raise CommercialGateError("ledger_creation_race") from None
                else:
                    os.close(fd)
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
            CREATE TABLE IF NOT EXISTS issued_invoices (
                order_id TEXT PRIMARY KEY REFERENCES orders(order_id),
                invoice_id TEXT NOT NULL UNIQUE,
                payload_digest TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settled_transactions (
                network TEXT NOT NULL,
                transaction_id TEXT NOT NULL,
                order_id TEXT NOT NULL REFERENCES orders(order_id),
                PRIMARY KEY (network, transaction_id)
            );
            -- This is append-only at the API/SQL connection layer. It does
            -- not claim cryptographic protection from database administrators.
            CREATE TRIGGER IF NOT EXISTS no_order_event_update BEFORE UPDATE ON order_events
                BEGIN SELECT RAISE(ABORT, 'immutable_order_event'); END;
            CREATE TRIGGER IF NOT EXISTS no_order_event_delete BEFORE DELETE ON order_events
                BEGIN SELECT RAISE(ABORT, 'immutable_order_event'); END;
            CREATE TRIGGER IF NOT EXISTS no_invoice_update BEFORE UPDATE ON issued_invoices
                BEGIN SELECT RAISE(ABORT, 'immutable_invoice'); END;
            CREATE TRIGGER IF NOT EXISTS no_invoice_delete BEFORE DELETE ON issued_invoices
                BEGIN SELECT RAISE(ABORT, 'immutable_invoice'); END;
            CREATE TRIGGER IF NOT EXISTS no_settlement_update BEFORE UPDATE ON settled_transactions
                BEGIN SELECT RAISE(ABORT, 'immutable_settlement'); END;
            CREATE TRIGGER IF NOT EXISTS no_settlement_delete BEFORE DELETE ON settled_transactions
                BEGIN SELECT RAISE(ABORT, 'immutable_settlement'); END;
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
        _validate_trx_sun_precision(amount, currency)
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

    def bind_issued_invoice(self, *, order_id: str, invoice_id: str,
                            payload_digest: str) -> None:
        """Commit to an invoice that was previously recorded in the order history.

        This is private staging only; it does not send an invoice or confirm
        independent provider approval. Rebinding or cross-order reuse fails.
        """
        order_id = _slug(order_id, "order_id")
        invoice_id = _slug(invoice_id, "invoice_id")
        if not isinstance(payload_digest, str) or not _HEX64.fullmatch(payload_digest):
            raise CommercialGateError("invoice_digest_invalid")
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            order = self.connection.execute(
                "SELECT state, amount, currency FROM orders WHERE order_id = ?", (order_id,),
            ).fetchone()
            if order is None:
                raise CommercialGateError("order_not_found")
            if order["state"] not in (CommercialState.INVOICED.value, CommercialState.PAYMENT_PENDING.value):
                raise CommercialGateError("invoice_bind_state_invalid")
            expected = invoice_commitment(
                order_id=order_id, invoice_id=invoice_id,
                amount=Decimal(order["amount"]), currency=order["currency"],
            )
            if expected != payload_digest:
                raise CommercialGateError("invoice_commitment_mismatch")
            issued = self.connection.execute(
                "SELECT payload_digest FROM order_events WHERE order_id = ? AND state = ?",
                (order_id, CommercialState.INVOICED.value),
            ).fetchone()
            if issued is None or issued["payload_digest"] != expected:
                raise CommercialGateError("invoice_issuance_event_missing")
            try:
                self.connection.execute(
                    "INSERT INTO issued_invoices VALUES (?, ?, ?, ?)",
                    (order_id, invoice_id, expected, datetime.now(timezone.utc).isoformat()),
                )
            except sqlite3.IntegrityError:
                raise CommercialGateError("invoice_already_registered") from None

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
        if len(event_id) > 128 or any(ord(char) < 33 or ord(char) > 126 for char in event_id):
            raise CommercialGateError("event_id_invalid")
        if not isinstance(target, CommercialState):
            raise CommercialGateError("invalid_state_transition")
        if not isinstance(payload_digest, str) or not _HEX64.fullmatch(payload_digest):
            raise CommercialGateError("payload_digest_invalid")
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            row = self.connection.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
            if row is None:
                raise CommercialGateError("order_not_found")
            prior = self.connection.execute(
                "SELECT order_id, payload_digest, state FROM order_events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if prior is not None:
                if prior["order_id"] != order_id:
                    raise CommercialGateError("event_replay_order_mismatch")
                if prior["payload_digest"] != payload_digest:
                    raise CommercialGateError("event_replay_mismatch")
                if prior["state"] != row["state"] or prior["state"] != target.value:
                    raise CommercialGateError("stale_event_replay")
                # An idempotent replay is not an authorization bypass: proof
                # is required again for paid, delivered and revenue states.
                if target in (CommercialState.SETTLED, CommercialState.VERIFIED_REVENUE):
                    if not isinstance(payment_evidence, PaymentEvidence):
                        raise CommercialGateError("settlement_evidence_required")
                    replay_digest = _validated_evidence_digest(
                        payment_evidence, expected_order_id=order_id,
                        expected_amount=Decimal(row["amount"]), expected_currency=row["currency"],
                    )
                    if target is CommercialState.SETTLED and replay_digest != payload_digest:
                        raise CommercialGateError("event_replay_mismatch")
                    issued = self.connection.execute(
                        "SELECT invoice_id FROM issued_invoices WHERE order_id = ?", (order_id,),
                    ).fetchone()
                    if issued is None or issued["invoice_id"] != payment_evidence.invoice_id:
                        raise CommercialGateError("settlement_invoice_mismatch")
                    settled = self.connection.execute(
                        "SELECT transaction_id FROM settled_transactions WHERE network = ? AND order_id = ?",
                        (payment_evidence.network, order_id),
                    ).fetchone()
                    if settled is None or settled["transaction_id"] != payment_evidence.transaction_id.lower():
                        raise CommercialGateError("verified_revenue_settlement_mismatch")
                    if self._settlement_verifier is None:
                        raise CommercialGateError("independent_settlement_verifier_required")
                    try:
                        payment_confirmed = self._settlement_verifier(payment_evidence)
                    except Exception:
                        raise CommercialGateError("independent_settlement_verifier_failed") from None
                    if payment_confirmed is not True:
                        raise CommercialGateError("independent_settlement_unverified")
                    if target is CommercialState.VERIFIED_REVENUE and verified_revenue is not True:
                        raise CommercialGateError("verified_revenue_attestation_required")
                if target in (CommercialState.FULFILLED, CommercialState.VERIFIED_REVENUE):
                    manifest = fulfillment_manifest_sha256
                    if target is CommercialState.VERIFIED_REVENUE:
                        delivered = self.connection.execute(
                            "SELECT payload_digest FROM order_events WHERE order_id = ? AND state = ?",
                            (order_id, CommercialState.FULFILLED.value),
                        ).fetchone()
                        if delivered is None:
                            raise CommercialGateError("fulfillment_evidence_missing")
                        manifest = delivered["payload_digest"]
                    elif manifest != payload_digest:
                        raise CommercialGateError("fulfillment_payload_mismatch")
                    if self._delivery_verifier is None:
                        raise CommercialGateError("independent_delivery_verifier_required")
                    try:
                        delivered_confirmed = self._delivery_verifier(order_id, manifest)
                    except Exception:
                        raise CommercialGateError("independent_delivery_verifier_failed") from None
                    if delivered_confirmed is not True:
                        raise CommercialGateError("independent_delivery_unverified")
                return CommercialState(prior["state"])
            current = CommercialState(row["state"])
            if target is CommercialState.FULFILLED and payload_digest != fulfillment_manifest_sha256:
                raise CommercialGateError("fulfillment_payload_mismatch")
            if target in (CommercialState.FULFILLED, CommercialState.VERIFIED_REVENUE):
                if self._delivery_verifier is None:
                    raise CommercialGateError("independent_delivery_verifier_required")
                manifest = fulfillment_manifest_sha256
                if target is CommercialState.VERIFIED_REVENUE:
                    delivered = self.connection.execute(
                        "SELECT payload_digest FROM order_events WHERE order_id = ? AND state = ?",
                        (order_id, CommercialState.FULFILLED.value),
                    ).fetchone()
                    if delivered is None:
                        raise CommercialGateError("fulfillment_evidence_missing")
                    manifest = delivered["payload_digest"]
                try:
                    confirmed = self._delivery_verifier(order_id, manifest)
                except Exception:
                    raise CommercialGateError("independent_delivery_verifier_failed") from None
                if confirmed is not True:
                    raise CommercialGateError("independent_delivery_unverified")
            evidence_digest = None
            if target in (CommercialState.SETTLED, CommercialState.VERIFIED_REVENUE):
                if not isinstance(payment_evidence, PaymentEvidence):
                    raise CommercialGateError("settlement_evidence_required")
                evidence_digest = _validated_evidence_digest(
                    payment_evidence,
                    expected_order_id=order_id,
                    expected_amount=Decimal(row["amount"]),
                    expected_currency=row["currency"],
                )
                if target is CommercialState.SETTLED and payload_digest != evidence_digest:
                    raise CommercialGateError("settlement_payload_mismatch")
                if self._settlement_verifier is None:
                    raise CommercialGateError("independent_settlement_verifier_required")
                try:
                    confirmed = self._settlement_verifier(payment_evidence)
                except Exception:
                    raise CommercialGateError("independent_settlement_verifier_failed") from None
                if confirmed is not True:
                    raise CommercialGateError("independent_settlement_unverified")
                issued = self.connection.execute(
                    "SELECT invoice_id, payload_digest FROM issued_invoices WHERE order_id = ?", (order_id,),
                ).fetchone()
                if issued is None:
                    raise CommercialGateError("registered_invoice_required")
                if issued["invoice_id"] != payment_evidence.invoice_id or (
                    issued["payload_digest"] != invoice_commitment(
                        order_id=order_id, invoice_id=issued["invoice_id"],
                        amount=Decimal(row["amount"]), currency=row["currency"],
                    )
                ):
                    raise CommercialGateError("settlement_invoice_mismatch")
                if target is CommercialState.VERIFIED_REVENUE:
                    settled = self.connection.execute(
                        "SELECT transaction_id FROM settled_transactions WHERE network = ? AND order_id = ?",
                        (payment_evidence.network, order_id),
                    ).fetchone()
                    if settled is None or settled["transaction_id"] != payment_evidence.transaction_id.lower():
                        raise CommercialGateError("verified_revenue_settlement_mismatch")
            # Chain transfers are single-use across orders; uniqueness is durable.
            if target is CommercialState.SETTLED:
                try:
                    self.connection.execute(
                        "INSERT INTO settled_transactions (network, transaction_id, order_id) VALUES (?, ?, ?)",
                        (payment_evidence.network, payment_evidence.transaction_id.lower(), order_id),
                    )
                except sqlite3.IntegrityError as exc:
                    raise CommercialGateError("transaction_already_settled") from exc
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
        order_id = _slug(order_id, "order_id")
        row = self.connection.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if row is None:
            raise CommercialGateError("order_not_found")
        return dict(row)


