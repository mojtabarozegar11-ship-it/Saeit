"""Evidence-backed commercial release manifest for MOJ PROP.

This module validates release evidence only. It does not enable routes, create
invoices, accept funds, settle payments, send messages, or touch a database.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .commercial_readiness_gate import (
    CommercialReadiness,
    CommercialReleaseClosed,
    REQUIRED_GATES,
    evaluate_commercial_readiness,
)


@dataclass(frozen=True)
class GateEvidence:
    status: bool
    reference: str
    reviewed_at: str


@dataclass(frozen=True)
class CommercialReleaseManifest:
    evidence: dict[str, GateEvidence]
    readiness: CommercialReadiness


def build_release_manifest(
    *,
    evidence: Mapping[str, Mapping[str, object]],
    public_route_enabled: bool = False,
    payment_enabled: bool = False,
) -> CommercialReleaseManifest:
    """Validate evidence and return a fail-closed release report."""
    if not isinstance(evidence, Mapping):
        raise CommercialReleaseClosed("evidence mapping is required")

    expected = set(REQUIRED_GATES)
    supplied = set(evidence)
    unknown = supplied - expected
    missing = expected - supplied
    if unknown or missing:
        raise CommercialReleaseClosed("evidence keys must exactly match required gates")

    records: dict[str, GateEvidence] = {}
    statuses: dict[str, bool] = {}
    for name in REQUIRED_GATES:
        item = evidence[name]
        if not isinstance(item, Mapping):
            raise CommercialReleaseClosed("each gate requires an evidence mapping")
        status = item.get("status")
        reference = item.get("reference", "")
        reviewed_at = item.get("reviewed_at", "")
        if type(status) is not bool:
            raise CommercialReleaseClosed("gate status must be a trusted boolean")
        if not isinstance(reference, str) or not isinstance(reviewed_at, str):
            raise CommercialReleaseClosed("evidence metadata must be text")
        if status and (not reference.strip() or not reviewed_at.strip()):
            raise CommercialReleaseClosed("complete gates require reference and review time")
        records[name] = GateEvidence(
            status=status,
            reference=reference.strip(),
            reviewed_at=reviewed_at.strip(),
        )
        statuses[name] = status

    readiness = evaluate_commercial_readiness(
        gates=statuses,
        public_route_enabled=public_route_enabled,
        payment_enabled=payment_enabled,
    )
    return CommercialReleaseManifest(evidence=records, readiness=readiness)
