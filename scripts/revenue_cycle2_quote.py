#!/usr/bin/env python3
"""Private offline quote-review packet for the EXISTING mojtaba.bot.ai revenue catalog.

This is not a quote, invoice, customer database, payment API, or second agent.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import sys

from mojtaba_revenue_portfolio import CANONICAL_BOT, OFFERS, evaluate

PACKAGES = {
    "farm_economics": ("economic_analysis",),
    "website_diagnosis": ("single_fault_diagnosis",),
    "website_bounded_repair": ("one_defect_repair",),
    "cafe_b2b": ("capacity_and_supply_inquiry",),
    "company_catalog": ("product_availability_inquiry",),
    "industrial_feasibility": ("pre_feasibility_scoping",),
    "research_contract": ("research_protocol_scoping",),
    "digital_publication": ("rights_and_delivery_review",),
    "game_license": ("license_and_delivery_review",),
    "trading_education": ("risk_education_only",),
}
NON_BINDING_RANGES = {
    "website_diagnosis": {"currency": "USD", "minimum": 29, "maximum": 49},
    "website_bounded_repair": {"currency": "USD", "minimum": 79, "maximum": 149},
}
REQUIRED = frozenset({
    "canonical_bot", "offer_id", "scope_items", "evidence_items", "consent",
    "rights_documents", "inventory_documents", "delivery_documents",
    "synthetic_example", "work_package",
})


def generate(data):
    """No identifying fields or free-form customer text accepted or echoed."""
    if type(data) is not dict or set(data) != REQUIRED:
        raise ValueError("INVALID_PRIVATE_QUOTE_METADATA_SCHEMA")
    pkg = data.get("work_package")
    code = data.get("offer_id")
    if type(pkg) is not str or type(code) is not str:
        raise ValueError("INVALID_WORK_PACKAGE")
    if code not in PACKAGES or pkg not in PACKAGES[code]:
        raise ValueError("UNSUPPORTED_OFFER_PACKAGE")
    finding = evaluate({k: v for k, v in data.items() if k != "work_package"})
    offer = OFFERS[code]
    return {
        "schema": "mojtaba.bot.ai.manual-quote-packet.v1",
        "canonical_bot": CANONICAL_BOT,
        "offer_id": code,
        "market": offer.domain,
        "source_path": offer.source,
        "work_package": pkg,
        "decision": finding["decision"],
        "review_blockers": finding["blockers"],
        "evidence_count_is_unverified": True,
        "indicative_non_binding_range": NON_BINDING_RANGES.get(code),
        "price_approved": False,
        "terms_approved": False,
        "quote_sent": False,
        "invoice_authorized": False,
        "payment_verified": False,
        "delivery_verified": False,
        "collected_revenue": None,
        "next_required_gate": "independent_owner_scope_legal_collection_review",
        "synthetic_example": data["synthetic_example"],
        "no_external_message": True,
    }


def bounded_read(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("INPUT_NOT_REGULAR")
    size = path.stat().st_size
    if not 0 < size <= 16384:
        raise ValueError("INPUT_SIZE_INVALID")
    payload = path.read_bytes()
    if len(payload) != size:
        raise ValueError("INPUT_CHANGED")
    return json.loads(payload.decode("utf-8"))


def private_create(path, source, result):
    if path.is_symlink() or path.resolve() == source.resolve():
        raise ValueError("OUTPUT_PATH_REJECTED")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ValueError("OUTPUT_PARENT_REJECTED")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("--output", type=Path, help="exclusively create a local 0600 JSON")
    args = parser.parse_args(argv)
    try:
        result = generate(bounded_read(args.metadata))
        if args.output:
            private_create(args.output, args.metadata, result)
        else:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
        print("QUOTE_REVIEW_PACKET=BLOCKED", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
