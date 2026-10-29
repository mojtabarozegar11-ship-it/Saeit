#!/usr/bin/env python3
"""Read-only SKU preflight classifier; never equates file presence with paid delivery."""
from __future__ import annotations

import json
import sys

SKU_IDS = (72, 225, 879)
PREFIX_FLAGS = "MPW_PUBLIC_TRX_FLAGS="
PREFIX_SKU = "MPW_PUBLIC_SKU_RIGHTS="


def classify(log: str) -> dict:
    flags = []
    products = {}
    for line in log.splitlines():
        if line.startswith(PREFIX_FLAGS):
            flags.append(json.loads(line[len(PREFIX_FLAGS):]))
        if line.startswith(PREFIX_SKU):
            item = json.loads(line[len(PREFIX_SKU):])
            sku = item.get("id")
            if type(sku) is not int or sku not in SKU_IDS or sku in products:
                raise ValueError("DUPLICATE_OR_UNEXPECTED_SKU")
            products[sku] = item
    if len(flags) != 1 or set(products) != set(SKU_IDS):
        raise ValueError("MISSING_OR_DUPLICATE_GATE_EVIDENCE")
    state = flags[0]
    if type(state) is not dict:
        raise ValueError("INVALID_FLAG_EVIDENCE")
    global_blocks = [
        label for key, label in (
            ("rights_gate_installed", "RIGHTS_GATE_NOT_INSTALLED"),
            ("merchant_canary", "MERCHANT_CANARY_NOT_VERIFIED"),
            ("public_enabled", "PUBLIC_CHECKOUT_DISABLED"),
            ("release_authorized", "PUBLIC_RELEASE_NOT_AUTHORIZED"),
        ) if state.get(key) is not True
    ]
    results = {}
    for sku in SKU_IDS:
        item = products[sku]
        if type(item) is not dict:
            raise ValueError("INVALID_SKU_EVIDENCE")
        blocks = []
        for key, label in (
            ("exists", "SKU_MISSING"),
            ("active", "SKU_INACTIVE"),
            ("eligible", "SKU_INELIGIBLE"),
            ("private_file_ready", "PRIVATE_FILE_NOT_READY"),
            ("stored_rights", "EXPLICIT_RIGHTS_FLAG_MISSING"),
            ("explicit_rights", "RUNTIME_RIGHTS_CHECK_DENIED"),
            ("rights_hash_reference_matches_asset", "RIGHTS_DOCUMENT_HASH_NOT_LINKED"),
        ):
            if item.get(key) is not True:
                blocks.append(label)
        catalog = item.get("existing_catalog_hash_matches_asset")
        if type(catalog) is not list or not catalog or not all(type(x) is str for x in catalog):
            blocks.append("CATALOG_FILE_HASH_MISMATCH")
        approvals = item.get("existing_approval_flags")
        if type(approvals) is not dict or approvals.get("publication_approved") is not True:
            blocks.append("PUBLICATION_APPROVAL_MISSING")
        results[str(sku)] = {
            "preflight": "blocked" if blocks or global_blocks else "passed",
            "blocks": blocks,
            "private_file_presence_is_not_delivery_proof": True,
        }
    ready = not global_blocks and all(not value["blocks"] for value in results.values())
    return {
        "preflight": "passed" if ready else "blocked",
        "global_blocks": global_blocks,
        "products": results,
        "paid_receipt": "not_examined",
        "authenticated_download_e2e": "not_examined",
        "independent_legal_clearance": "not_established_by_metadata",
    }


def main() -> int:
    try:
        result = classify(sys.stdin.read())
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        print("MPW_READINESS_CONTRACT_ERROR=" + type(exc).__name__ + ":" + str(exc))
        return 4
    print("MPW_READINESS_PRECHECK=" + json.dumps(result, sort_keys=True))
    return 0 if result["preflight"] == "passed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
