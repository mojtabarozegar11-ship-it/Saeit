"""Pure read-only cross-provider native-TRX credit reconciliation.

No customer identifiers, raw transaction hashes, network calls or writes are
emitted. A clean scan is NOT a production settlement or ownership proof.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import re

_TXID = re.compile(r"[0-9a-f]{64}\Z", re.IGNORECASE)
_REFERENCES = ("tron-mainnet:", "walletless:tron-mainnet:")


def canonical_txid(value):
    if type(value) is not str or _TXID.fullmatch(value) is None:
        return None
    return value.lower()


def ledger_txid(reference):
    if type(reference) is not str:
        return None
    for prefix in _REFERENCES:
        if reference.lower().startswith(prefix):
            return canonical_txid(reference[len(prefix):])
    return None


def summarize_tron_conflicts(events, credits, *, complete):
    """Summarize SQL-bounded persisted event/credit snapshots, fail-closed.

    Each event/credit is a dict from Django values(); query ordering must be
    stable and supplied separately. Incomplete snapshots cannot prove safety.
    """
    if type(complete) is not bool:
        raise ValueError("Completeness must be a boolean")
    grouped = defaultdict(lambda: {"events": [], "credits": []})
    invalid_events = invalid_credits = 0
    scanned_events = scanned_credits = 0
    for row in events:
        scanned_events += 1
        txid = canonical_txid(row.get("event_id")) if type(row) is dict else None
        if txid is None:
            invalid_events += 1
        else:
            grouped[txid]["events"].append(row)
    for row in credits:
        scanned_credits += 1
        txid = ledger_txid(row.get("reference")) if type(row) is dict else None
        if txid is None:
            invalid_credits += 1
        else:
            grouped[txid]["credits"].append(row)
    findings = []
    for txid, claims in sorted(grouped.items()):
        evs, crs = claims["events"], claims["credits"]
        flags = []
        if len(evs) > 1:
            flags.append("multiple_finalized_events")
        if len(crs) > 1:
            flags.append("multiple_ledger_credits")
        if evs and not crs:
            flags.append("event_without_credit")
        if crs and not evs:
            flags.append("credit_without_event")
        if any(e.get("status") != "processed" for e in evs):
            flags.append("unprocessed_event")
        if len({e.get("provider") for e in evs}) > 1:
            flags.append("cross_provider_event")
        if flags:
            findings.append({
                "fingerprint": hashlib.sha256(("tron-audit-v1|" + txid).encode("ascii")).hexdigest()[:16],
                "flags": flags, "events": len(evs), "credits": len(crs),
            })
    clean = bool(complete and not findings and not invalid_events and not invalid_credits)
    return {
        "complete": complete,
        "scanned_events": scanned_events,
        "scanned_credits": scanned_credits,
        "distinct_txids": len(grouped),
        "invalid_event_txids": invalid_events,
        "invalid_credit_refs": invalid_credits,
        "finding_count": len(findings),
        "findings": findings,
        "no_conflicts_in_bounded_snapshot": clean,
        "production_payment_safe": False,
    }
