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


def validate_status_change(
    previous: str, following: str, note: str, previous_note: str = ""
) -> None:
    """Preserve earlier evidence; every later status needs a new evidence line."""
    if previous not in STATUS_TRANSITIONS or following not in STATUS_TRANSITIONS:
        raise ValidationError("Unknown Moj Prop commercial status")
    if following != previous and following not in STATUS_TRANSITIONS[previous]:
        raise ValidationError(
            f"Transition {previous!r} to {following!r} is not permitted"
        )
    if not isinstance(note, str) or not isinstance(previous_note, str):
        raise ValidationError("Internal evidence must be text")
    history = previous_note.strip()
    proposed = note.strip()
    if history and proposed != history and not proposed.startswith(history + "\n"):
        raise ValidationError("Prior customer offer/delivery evidence must be preserved")
    if history and proposed == history and following in EVIDENCE_PREFIX and following != previous:
        raise ValidationError("A new state requires new documentary evidence")
    new_text = proposed[len(history):].strip() if history else proposed
    if following != previous and following in EVIDENCE_PREFIX:
        prefix = EVIDENCE_PREFIX[following]
        if not new_text.upper().startswith(prefix) or len(new_text) < len(prefix) + 12:
            raise ValidationError(
                f"Append {prefix} and the written evidence reference on a new line"
            )
