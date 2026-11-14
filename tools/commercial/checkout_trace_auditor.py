"""Offline structural review of SANITIZED checkout traces.

No gateway verification, live orders, customer data, credential access or payment actions.
Even a clean trace is NOT evidence that funds settled or goods were delivered.
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

ALLOWED_FIELDS = {"event_id", "order_ref", "event", "source", "amount", "currency", "payment_ref"}
EVENTS = {"checkout_created", "payment_confirmed", "payment_failed", "fulfilled", "refund_confirmed"}
HEX = re.compile(r"[0-9a-f]{64}\Z")
ID = re.compile(r"[A-Za-z0-9_.-]{1,64}\Z")
CURRENCY = re.compile(r"[A-Z]{3}\Z")


def audit_checkout_trace(payload):
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "events"} or payload["schema_version"] != 1:
        raise ValueError("invalid checkout trace schema")
    events = payload["events"]
    if not isinstance(events, list) or not (1 <= len(events) <= 2000):
        raise ValueError("events must be a nonempty bounded list")
    states = defaultdict(lambda: {"created": False, "confirmed": False, "refunded": False,
                                   "fulfilled": 0, "payments": set(), "amount": None,
                                   "currency": None, "issues": []})
    seen = {}
    replayed = 0
    for i, e in enumerate(events, 1):
        if not isinstance(e, dict) or set(e) != ALLOWED_FIELDS or any(not isinstance(v, str) for v in e.values()):
            raise ValueError(f"event {i}: unknown fields or invalid types; remove personal/card data")
        if not ID.fullmatch(e["event_id"]) or not HEX.fullmatch(e["order_ref"]):
            raise ValueError(f"event {i}: invalid sanitized identifier")
        if e["event"] not in EVENTS or e["source"] not in {"client", "server", "gateway"}:
            raise ValueError(f"event {i}: unsupported event/source")
        if not CURRENCY.fullmatch(e["currency"]):
            raise ValueError(f"event {i}: invalid currency")
        try:
            amount = Decimal(e["amount"])
        except InvalidOperation as exc:
            raise ValueError(f"event {i}: invalid amount") from exc
        if not amount.is_finite() or amount < 0 or amount.adjusted() > 24:
            raise ValueError(f"event {i}: unsupported amount")
        if e["payment_ref"] and not HEX.fullmatch(e["payment_ref"]):
            raise ValueError(f"event {i}: payment reference must be a sanitized SHA-256 digest")
        event_id = e["event_id"]
        if event_id in seen:
            if seen[event_id] != e:
                states[e["order_ref"]]["issues"].append("EVENT_ID_COLLISION")
            else:
                replayed += 1  # legitimate identical webhook retry: not a second charge/order
            continue
        seen[event_id] = e
        state = states[e["order_ref"]]
        if state["amount"] is None:
            state["amount"],state["currency"] = amount,e["currency"]
        elif state["amount"] != amount or state["currency"] != e["currency"]:
            state["issues"].append("ORDER_AMOUNT_OR_CURRENCY_CHANGED")
        kind=e["event"]
        if kind == "checkout_created":
            if state["created"]: state["issues"].append("MULTIPLE_CHECKOUT_CREATIONS")
            if state["confirmed"] or state["fulfilled"]:
                state["issues"].append("CHECKOUT_CREATION_AFTER_PAYMENT_OR_DELIVERY")
            state["created"]=True
        elif kind == "payment_confirmed":
            if not state["created"]:
                state["issues"].append("PAYMENT_BEFORE_CHECKOUT_CREATION")
            if e["source"] != "gateway" or not e["payment_ref"]:
                state["issues"].append("PAYMENT_NOT_GATEWAY_ATTESTED_IN_TRACE")
            else:
                state["payments"].add(e["payment_ref"])
                state["confirmed"]=True
                if len(state["payments"]) > 1:
                    state["issues"].append("POSSIBLE_MULTIPLE_PAYMENT_REFERENCES")
        elif kind == "payment_failed":
            # No attempt-level reference is supplied by this sanitized format.
            # A failure following a confirmation may be another attempt, so
            # require human review rather than claiming a reversal or success.
            if state["confirmed"]:
                state["issues"].append("FAILURE_AFTER_CONFIRMATION_REQUIRES_REVIEW")
        elif kind == "refund_confirmed":
            if e["source"] != "gateway" or e["payment_ref"] not in state["payments"]:
                state["issues"].append("REFUND_WITHOUT_MATCHED_GATEWAY_PAYMENT")
            else:
                state["refunded"] = True
                if state["fulfilled"]:
                    state["issues"].append("REFUND_AFTER_FULFILLMENT_ACCESS_REVIEW")
        elif kind == "fulfilled":
            state["fulfilled"] += 1
            if not state["confirmed"]:
                state["issues"].append("FULFILLMENT_WITHOUT_TRUSTED_PAYMENT_IN_TRACE")
            if state["refunded"]:
                state["issues"].append("FULFILLMENT_AFTER_REFUND_REQUIRES_REVIEW")
            if state["fulfilled"] > 1:
                state["issues"].append("MULTIPLE_FULFILLMENTS")
    results=[]
    for order_ref,state in sorted(states.items()):
        if not state["created"]: state["issues"].append("MISSING_CHECKOUT_CREATION")
        # A payment-like trace without any delivery event must not be labelled clean.
        # The trace itself cannot establish whether delivery eventually occurred.
        if state["confirmed"] and not state["fulfilled"]:
            state["issues"].append("PAYMENT_WITHOUT_FULFILLMENT_IN_TRACE")
        issues=list(dict.fromkeys(state["issues"]))
        results.append({"order_ref":order_ref,"status":"REVIEW_REQUIRED" if issues else "NO_STRUCTURAL_ISSUES",
                        "issues":issues,"payment_references_seen":len(state["payments"]),
                        "fulfillment_events":state["fulfilled"]})
    return {"schema_version":1,"report_scope":"STRUCTURAL_ONLY_NOT_PAYMENT_OR_DELIVERY_PROOF",
            "orders":results,"replayed_events_ignored":replayed,
            "issues_count":sum(len(x["issues"]) for x in results)}


def main(argv=None):
    parser=argparse.ArgumentParser(description="Audit sanitized checkout lifecycle, offline only")
    parser.add_argument("json_file")
    args=parser.parse_args(argv)
    try:
        payload=json.loads(Path(args.json_file).read_text(encoding="utf-8-sig"))
        report=audit_checkout_trace(payload)
    except (OSError,UnicodeError,ValueError) as exc:
        print(f"Trace rejected: {exc}",file=sys.stderr)
        return 2
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":raise SystemExit(main())
