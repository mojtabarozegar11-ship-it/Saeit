"""Privacy-preserving operational queue for Moj Prop commercial leads.

The queue exposes only identifiers, routing metadata and readiness flags. It
does not expose names, email addresses or customer notes, and it never sends a
message, changes a lead, creates a payment, or executes a trade.
"""
from __future__ import annotations

from collections import Counter

from django.core.exceptions import ValidationError
from django.core.validators import validate_email


QUEUE_STATUSES = ("new", "reviewing", "offer_sent", "approved")


def _iso(value: object) -> str:
    if value is None:
        return ""
    method = getattr(value, "isoformat", None)
    return str(method()) if callable(method) else str(value)


def _valid_contact_for_draft(lead: object) -> bool:
    """Never turn None, malformed addresses, or forged headers into buyer contacts."""
    name = getattr(lead, "name", None)
    email = getattr(lead, "email", None)
    if type(name) is not str or type(email) is not str:
        return False
    if not 2 <= len(name.strip()) <= 200 or not 3 <= len(email) <= 254:
        return False
    if email != email.strip() or any(
        ord(ch) < 32 or ord(ch) == 127 or 0xD800 <= ord(ch) <= 0xDFFF
        for ch in name + email
    ):
        return False
    try:
        validate_email(email)
    except ValidationError:
        return False
    domain = email.rsplit("@", 1)[-1].lower().rstrip(".")
    return domain not in {"localhost", "example.invalid"} and not domain.endswith(
        (".invalid", ".localhost", ".local", ".test")
    )


def offer_draft_eligible(lead: object) -> bool:
    """Only reviewed, consented leads with valid contact and bounded scope qualify."""
    notes = getattr(lead, "notes", None)
    return bool(
        getattr(lead, "pk", None)
        and getattr(lead, "status", None) == "reviewing"
        and getattr(lead, "consent", None) is True
        and str(getattr(lead, "request_id", "")).startswith("MOJPROP-")
        and _valid_contact_for_draft(lead)
        and type(notes) is str
        and 20 <= len(notes.strip()) <= 5000
    )


def queue_row(lead: object) -> dict[str, object]:
    """Create a safe row with no customer PII or free-form text."""
    status = str(getattr(lead, "status", "unknown"))
    return {
        "request_id": str(getattr(lead, "request_id", "")),
        "status": status,
        "route": str(getattr(lead, "route", "")),
        "horizon": str(getattr(lead, "horizon", "")),
        "created_at": _iso(getattr(lead, "created_at", None)),
        "offer_draft_eligible": offer_draft_eligible(lead),
    }


def summarise_queue(leads: list[object]) -> dict[str, object]:
    """Return bounded, non-PII sales-queue telemetry for the owner."""
    rows = [queue_row(lead) for lead in leads]
    counts = Counter(row["status"] for row in rows)
    by_status = {status: counts.get(status, 0) for status in QUEUE_STATUSES}
    for status, count in counts.items():
        if status not in by_status:
            by_status[status] = count
    return {
        "schema": "mojprop.sales-queue.v1",
        "total": len(rows),
        "by_status": by_status,
        "offer_draft_eligible": sum(
            1 for row in rows if row["offer_draft_eligible"]
        ),
        "rows": rows,
        "side_effects": {
            "email_sent": False,
            "payment_created": False,
            "lead_mutated": False,
            "trade_executed": False,
        },
    }
