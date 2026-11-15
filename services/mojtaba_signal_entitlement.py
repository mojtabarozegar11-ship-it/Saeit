"""Fail-closed educational signal entitlement state machine.

This state machine records required evidence stages but never verifies a chain,
charges a customer, publishes a signal, or sends a message.
"""
import re

class SignalEntitlementError(ValueError):
    pass

_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{5,159}$")
_STATES = frozenset(("requested", "offered", "paid", "delivered", "closed"))

def advance_signal_entitlement(state, event, *, evidence=None):
    if state not in _STATES:
        raise SignalEntitlementError("unknown entitlement state")
    if type(event) is not str or not event:
        raise SignalEntitlementError("event is required")
    evidence = evidence or {}
    if type(evidence) is not dict:
        raise SignalEntitlementError("evidence must be a mapping")
    if state == "requested" and event == "offer_issued":
        return "offered"
    if state == "offered" and event == "payment_verified":
        if evidence.get("verified") is not True or not _REF.fullmatch(str(evidence.get("receipt_id", ""))):
            raise SignalEntitlementError("independent payment receipt evidence required")
        return "paid"
    if state == "paid" and event == "delivery_acknowledged":
        if not _REF.fullmatch(str(evidence.get("delivery_id", ""))):
            raise SignalEntitlementError("delivery acknowledgement required")
        return "delivered"
    if state == "delivered" and event == "close":
        return "closed"
    raise SignalEntitlementError("invalid entitlement transition")

def commercial_flags(state):
    if state not in _STATES:
        raise SignalEntitlementError("unknown entitlement state")
    return {
        "state": state,
        "payment_received": state in ("paid", "delivered", "closed"),
        "delivery_confirmed": state in ("delivered", "closed"),
        "publication_allowed": False,
        "trading_enabled": False,
    }
