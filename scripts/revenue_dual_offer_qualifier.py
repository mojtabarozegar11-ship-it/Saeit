#!/usr/bin/env python3
"""Offline, PII-minimizing qualification of two existing service offers.

One intake -> one deterministic non-binding decision. Never sends email,
generates invoices, executes payment, or marks an order paid/delivered.
No third-party dependencies or network access.
"""
import argparse
import json
from pathlib import Path
try:
    from scripts.revenue_intake_io import read_strict_json, write_new_anonymized_json
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    from revenue_intake_io import read_strict_json, write_new_anonymized_json

OFFERS = {
    "website_checkout_repair": {
        "market": "international",
        "service": "Website Sales & Checkout Repair",
        "packages": {
            "diagnosis": {"currency": "USD", "indicative_min": 29, "indicative_max": 49},
            "bounded_repair": {"currency": "USD", "indicative_min": 79, "indicative_max": 149},
        },
    },
    "farm_break_even": {
        "market": "iran",
        "service": "Farm break-even and sensitivity analysis",
        "packages": {"analysis": None},  # Price unapproved; do not invent one.
    },
}
ALLOWED_KEYS = frozenset({
    "offer", "package", "scope_items", "evidence_items", "consent_to_contact",
    "inputs_available", "synthetic_example",
})


def is_int(value):
    return type(value) is int  # Reject booleans as item counts.


def qualify(data):
    """Return an anonymized internal triage result. No client text is echoed."""
    if not isinstance(data, dict):
        raise ValueError("input must be one JSON object")
    unexpected = set(data) - ALLOWED_KEYS
    if unexpected:
        raise ValueError("unexpected fields rejected; do not include customer PII")
    offer = data.get("offer")
    if not isinstance(offer, str) or offer not in OFFERS:
        raise ValueError("unsupported offer")
    package = data.get("package")
    record = OFFERS[offer]
    if not isinstance(package, str) or package not in record["packages"]:
        raise ValueError("unsupported package for selected offer")
    scope = data.get("scope_items")
    evidence = data.get("evidence_items")
    if not is_int(scope) or not (1 <= scope <= 20):
        raise ValueError("scope_items must be integer 1..20")
    if not is_int(evidence) or not (0 <= evidence <= 20):
        raise ValueError("evidence_items must be integer 0..20")
    for key in ("consent_to_contact", "inputs_available", "synthetic_example"):
        if type(data.get(key)) is not bool:
            raise ValueError(key + " must be boolean")
    blockers = []
    if not data["consent_to_contact"]:
        blockers.append("contact_consent_missing")
    if not data["inputs_available"]:
        blockers.append("minimum_inputs_missing")
    if evidence == 0:
        blockers.append("no_supporting_evidence")
    if scope > 3:
        blockers.append("scope_exceeds_bounded_offer")
    price_band = record["packages"][package]
    if price_band is None:
        blockers.append("local_price_not_approved")
    # Every inquiry requires an individual scope/terms/payment-route approval.
    return {
        "schema": "mojtaba.bot.ai.service-intake.v1",
        "canonical_bot": "mojtaba.bot.ai",
        "offer": offer,
        "package": package,
        "market": record["market"],
        "synthetic_example": data["synthetic_example"],
        "qualification": "needs_more_information" if blockers else "manual_quote_review",
        "blockers": blockers,
        "price_band_non_binding": price_band,
        "payment_state": "not_requested",
        "order_state": "inquiry_only",
        "delivery_state": "not_delivered",
        "next_gate": "owner_scope_pricing_collection_approval",
        "auto_send_enabled": False,
        "personal_data_exported": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_file", help="LOCAL JSON file only; do not put customer PII in it")
    parser.add_argument("--output", help="LOCAL anonymized result JSON path")
    args = parser.parse_args(argv)
    try:
        obj = read_strict_json(args.input_file)
        result = qualify(obj)
    except (ValueError, UnicodeError) as exc:
        parser.error(str(exc))
    serialized = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        try:
            write_new_anonymized_json(args.output, serialized)
        except ValueError as exc:
            parser.error(str(exc))
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
