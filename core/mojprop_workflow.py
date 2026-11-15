"""Manual, auditable commercial-offer workflow for Moj Prop leads.

Do not infer a sale from a lead or let an operator skip written acceptance.
This contains no payment processing, trading execution or automatic messages.
"""
from django.core.exceptions import ValidationError

STATUS_TRANSITIONS = {
    "new": frozenset(("reviewing", "closed", "spam")),
    "reviewing": frozenset(("offer_sent", "closed", "spam")),
    "offer_sent": frozenset(("approved", "closed", "reviewing")),
    "approved": frozenset(("delivered", "closed")),
    "delivered": frozenset(("closed",)),
    "closed": frozenset(),
    "spam": frozenset(),
}

EVIDENCE_PREFIX = {
    "offer_sent": "OFFER:",
    "approved": "ACCEPTANCE:",
    "delivered": "DELIVERY:",
}


def validate_status_change(previous: str, following: str, note: str) -> None:
    """Validate an operator's change without modifying models or writing data."""
    if previous not in STATUS_TRANSITIONS or following not in STATUS_TRANSITIONS:
        raise ValidationError("Unknown Moj Prop commercial status")
    if following != previous and following not in STATUS_TRANSITIONS[previous]:
        raise ValidationError(
            f"Transition {previous!r} to {following!r} is not permitted"
        )
    if following != previous and following in EVIDENCE_PREFIX:
        prefix = EVIDENCE_PREFIX[following]
        if not isinstance(note, str) or not note.strip().upper().startswith(prefix):
            raise ValidationError(
                f"Add {prefix} followed by the written evidence reference"
            )
        if len(note.strip()) < len(prefix) + 12:
            raise ValidationError("Document the written evidence reference in full")
