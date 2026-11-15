"""Fail-closed manual TRX receipt reconciliation boundary.

A receipt candidate is an observed fact for review, not proof of settlement.
This module never calls a chain node, creates an invoice, grants entitlement,
moves TRX or marks customer revenue as collected.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re

_NETWORK = "tron-mainnet"
_ASSET = "TRX"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")
_HOST = re.compile(r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


class TronReconciliationError(ValueError):
    pass


@dataclass(frozen=True)
class TrxReceiptCandidate:
    receipt_id: str
    tenant_id: str
    host: str
    brand: str
    invoice_id: str
    tx_id: str
    network: str
    asset: str
    amount_sun: int
    confirmations: int
    required_confirmations: int
    observed_at: str
    to_address_digest: str
    provider_reference_digest: str


def _identifier(value, field):
    if type(value) is not str or not _ID.fullmatch(value):
        raise TronReconciliationError(f"{field}_invalid")
    return value


def _host(value):
    if type(value) is not str or value != value.lower() or not _HOST.fullmatch(value):
        raise TronReconciliationError("host_invalid")
    return value


def _digest(value, field):
    if type(value) is not str or not _DIGEST.fullmatch(value):
        raise TronReconciliationError(f"{field}_invalid")
    return value


def _timestamp(value):
    if type(value) is not str or not value.endswith("Z"):
        raise TronReconciliationError("observed_at_invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise TronReconciliationError("observed_at_invalid") from exc
    if parsed.utcoffset() != timedelta(0):
        raise TronReconciliationError("observed_at_invalid")
    return parsed


def validate_receipt_candidate(
    candidate: TrxReceiptCandidate,
    expected_scope: dict,
    *,
    now=None,
) -> None:
    if not isinstance(candidate, TrxReceiptCandidate):
        raise TronReconciliationError("receipt_candidate_required")
    if type(expected_scope) is not dict or set(expected_scope) != {
        "tenant_id", "host", "brand"
    }:
        raise TronReconciliationError("exact_tenant_scope_required")
    _identifier(candidate.receipt_id, "receipt_id")
    _identifier(candidate.tenant_id, "tenant_id")
    _host(candidate.host)
    _identifier(candidate.brand or "main", "brand")
    _identifier(candidate.invoice_id, "invoice_id")
    _identifier(candidate.tx_id, "tx_id")
    if candidate.network != _NETWORK or candidate.asset != _ASSET:
        raise TronReconciliationError("canonical_tron_asset_required")
    if type(candidate.amount_sun) is not int or isinstance(candidate.amount_sun, bool) or candidate.amount_sun <= 0:
        raise TronReconciliationError("amount_sun_must_be_positive_integer")
    if type(candidate.confirmations) is not int or isinstance(candidate.confirmations, bool) or candidate.confirmations < 0:
        raise TronReconciliationError("confirmations_invalid")
    if type(candidate.required_confirmations) is not int or isinstance(candidate.required_confirmations, bool) or candidate.required_confirmations < 1:
        raise TronReconciliationError("required_confirmations_invalid")
    _timestamp(candidate.observed_at)
    _digest(candidate.to_address_digest, "to_address_digest")
    _digest(candidate.provider_reference_digest, "provider_reference_digest")
    for key in ("tenant_id", "host", "brand"):
        expected = expected_scope[key]
        if key == "host":
            expected = _host(expected)
        elif key == "brand" and expected == "":
            expected = ""
        else:
            expected = _identifier(expected, key)
        if getattr(candidate, key) != expected:
            raise TronReconciliationError("receipt_scope_mismatch")
    if now is not None:
        if now.tzinfo is None:
            raise TronReconciliationError("reconciliation_clock_must_be_timezone_aware")
        observed = _timestamp(candidate.observed_at)
        if observed > now + timedelta(seconds=30):
            raise TronReconciliationError("receipt_observed_in_future")


def build_review_record(
    candidate: TrxReceiptCandidate,
    expected_scope: dict,
    *,
    now=None,
) -> dict:
    """Build a review-only record with no settlement or delivery side effect."""
    validate_receipt_candidate(candidate, expected_scope, now=now)
    enough_confirmations = candidate.confirmations >= candidate.required_confirmations
    return {
        "receipt_id": candidate.receipt_id,
        "tenant_id": candidate.tenant_id,
        "host": candidate.host,
        "brand": candidate.brand,
        "invoice_id": candidate.invoice_id,
        "tx_id": candidate.tx_id,
        "network": candidate.network,
        "asset": candidate.asset,
        "amount_sun": candidate.amount_sun,
        "confirmations": candidate.confirmations,
        "required_confirmations": candidate.required_confirmations,
        "reviewable": enough_confirmations,
        "state": "observed_pending_independent_settlement",
        "independent_settlement_required": True,
        "settled": False,
        "entitlement_granted": False,
        "revenue_collected": False,
    }


def validate_receipt_batch(candidates) -> tuple[TrxReceiptCandidate, ...]:
    if not isinstance(candidates, (list, tuple)):
        raise TronReconciliationError("receipt_batch_required")
    receipt_ids = set()
    tx_ids = set()
    for candidate in candidates:
        _identifier(candidate.receipt_id, "receipt_id")
        _identifier(candidate.tx_id, "tx_id")
        if candidate.receipt_id in receipt_ids:
            raise TronReconciliationError("duplicate_receipt_id")
        if candidate.tx_id in tx_ids:
            raise TronReconciliationError("duplicate_transaction_id")
        receipt_ids.add(candidate.receipt_id)
        tx_ids.add(candidate.tx_id)
    return tuple(candidates)
