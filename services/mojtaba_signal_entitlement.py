"""Fail-closed educational signal entitlement transitions for mojtaba.bot.ai.

An HTTP buyer, webhook, raw chain JSON or caller-provided verified=True must
never be able to transition to paid or delivered. Both side effects need a
server-side trusted verifier reading persistent invoice/delivery evidence.
This module itself does not collect money, access a chain, send signals or
issue entitlement access.
"""
import re

class SignalEntitlementError(ValueError):
    pass

_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{5,159}\Z")
_STATES = frozenset(("requested", "offered", "paid", "delivered", "closed"))


def _valid_ref(value):
    return type(value) is str and _REF.fullmatch(value) is not None


def _trusted_gate(callback, evidence):
    """A trusted internal adapter must explicitly approve persisted evidence.

    A plain verified=True field is only a claim, never independent verification.
    Catch integration errors and fail closed, never leak adapter exceptions.
    """
    if not callable(callback):
        raise SignalEntitlementError("trusted server-side verification adapter required")
    try:
        verdict = callback(dict(evidence))
    except Exception as exc:
        raise SignalEntitlementError("independent verification could not complete") from exc
    if verdict is not True or type(verdict) is not bool:
        raise SignalEntitlementError("independent verification rejected evidence")


def advance_signal_entitlement(
    state, event, *, evidence=None, payment_verifier=None, delivery_verifier=None
):
    if type(state) is not str or state not in _STATES:
        raise SignalEntitlementError("unknown entitlement state")
    if type(event) is not str or not event:
        raise SignalEntitlementError("event is required")
    if evidence is None:
        evidence = {}
    if type(evidence) is not dict:
        raise SignalEntitlementError("evidence must be a mapping")
    if state == "requested" and event == "offer_issued":
        return "offered"
    if state == "offered" and event == "payment_verified":
        receipt_id = evidence.get("receipt_id")
        if (evidence.get("verified") is not True or
                not _valid_ref(receipt_id)):
            raise SignalEntitlementError("independent payment receipt evidence required")
        _trusted_gate(payment_verifier, evidence)
        return "paid"
    if state == "paid" and event == "delivery_acknowledged":
        delivery_id = evidence.get("delivery_id")
        if not _valid_ref(delivery_id):
            raise SignalEntitlementError("delivery acknowledgement required")
        _trusted_gate(delivery_verifier, evidence)
        return "delivered"
    if state == "delivered" and event == "close":
        return "closed"
    raise SignalEntitlementError("invalid entitlement transition")


def commercial_flags(state):
    if type(state) is not str or state not in _STATES:
        raise SignalEntitlementError("unknown entitlement state")
    return {
        "state": state,
        "payment_received": state in ("paid", "delivered", "closed"),
        "delivery_confirmed": state in ("delivered", "closed"),
        "publication_allowed": False,
        "trading_enabled": False,
    }
