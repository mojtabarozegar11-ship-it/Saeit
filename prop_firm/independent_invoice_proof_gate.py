"""Pure fail-closed agreement gate for independently fetched TRON transfer proofs.

No RPC calls, payment, invoice mutation or entitlement grant. The caller must
obtain finalized proof from independently operated providers and separately
enforce a database UNIQUE txid claim in the isolated MOJPROP transaction.
This module is intentionally not wired to production.
"""
from dataclasses import dataclass
from .invoice_price_snapshot_guard import InvoicePriceSnapshot, require_supported_snapshot


class SettlementProofRejected(ValueError):
    """Invoice and independent finalized chain evidence do not agree."""


@dataclass(frozen=True)
class FinalizedTransferProof:
    provider_id: str
    operator_id: str
    txid: str
    network: str
    sender_hex41: str
    recipient_hex41: str
    amount_sun: int
    solidified: bool
    successful: bool


def require_matching_finalized_proofs(
    *, snapshot: InvoicePriceSnapshot, expected_txid: str,
    expected_recipient_hex41: str, expected_sender_hex41: str,
    first: FinalizedTransferProof, second: FinalizedTransferProof,
) -> str:
    """Return normalized txid only when both independently sourced proofs agree.

    Inputs must be populated by trusted RPC adapters and persisted server-side
    invoice fields, never untrusted checkout JSON. Returning a txid is NOT a
    settlement authorization; the caller must enforce expiry, unique txid,
    invoice state and redemption claim atomically before any fulfillment.
    """
    try:
        amount = require_supported_snapshot(snapshot)
    except (ValueError, TypeError) as exc:
        raise SettlementProofRejected("unsupported immutable invoice") from exc
    if any(type(v) is not str or not v.strip() for v in (
        expected_txid, expected_recipient_hex41, expected_sender_hex41
    )):
        raise SettlementProofRejected("trusted invoice payment binding required")
    txid = expected_txid.lower()
    if len(txid) != 64 or any(ch not in "0123456789abcdef" for ch in txid):
        raise SettlementProofRejected("invalid txid")
    def normalized_address(value):
        if type(value) is not str or len(value) != 42 or not value.startswith("41"):
            raise SettlementProofRejected("invalid TRON hex41 address")
        if any(ch not in "0123456789abcdef" for ch in value.lower()):
            raise SettlementProofRejected("invalid TRON hex41 address")
        return value.lower()
    recipient = normalized_address(expected_recipient_hex41)
    sender = normalized_address(expected_sender_hex41)
    if recipient == sender:
        raise SettlementProofRejected("sender and recipient cannot match")
    if type(first) is not FinalizedTransferProof or type(second) is not FinalizedTransferProof:
        raise SettlementProofRejected("two structured proofs required")
    if (not first.provider_id or not second.provider_id
            or not first.operator_id or not second.operator_id
            or first.provider_id == second.provider_id
            or first.operator_id == second.operator_id):
        raise SettlementProofRejected("independent providers and operators required")
    for proof in (first, second):
        if proof.solidified is not True or proof.successful is not True:
            raise SettlementProofRejected("transfer not final and successful")
        if type(proof.amount_sun) is not int or proof.amount_sun != amount:
            raise SettlementProofRejected("transfer amount differs from invoice")
        if proof.network != snapshot.network or proof.txid.lower() != txid:
            raise SettlementProofRejected("network or txid mismatch")
        if normalized_address(proof.sender_hex41) != sender:
            raise SettlementProofRejected("sender mismatch")
        if normalized_address(proof.recipient_hex41) != recipient:
            raise SettlementProofRejected("recipient mismatch")
    return txid
