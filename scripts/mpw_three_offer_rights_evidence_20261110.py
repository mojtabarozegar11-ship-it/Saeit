#!/usr/bin/env python3
"""Audit a three-offer documentary rights register, with no host or network writes.

This is a DOCUMENTARY preflight only; it must never mint rights, sign documents,
change checkout flags or equate a SHA-256 digest with permission to sell.
"""

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "catalog/mojplaywin/three_offer_rights_register_20261110.json"
KNOWN = {
    72: "3837fc3cb21ed1a2e7c33e0db8f8e10d158583309b02b97d4d674d25a147207a",
    225: "2f6dace4e5bc09ffe5f8d7a677ddff4980fe00de94b7c2ea5b286d1303901d48",
    879: "98bffad4ccf36f84c7924ca77e4a8b473b42f33a8fce4d85cefe2367afc097aa",
}
SCHEMA = "mojplaywin.three-offer-rights-register.v1"
COMMON = {
    "author_identity_and_alias_document",
    "author_to_seller_distribution_authority",
    "independent_signed_rights_review",
}
REQUIRED_EVIDENCE = {
    72: COMMON | {
        "original_editable_work_and_creation_history",
        "cover_and_third_party_assets_commercial_licenses",
    },
    225: COMMON | {
        "original_editable_work_and_creation_history",
        "illustrations_and_third_party_assets_commercial_licenses",
    },
    879: COMMON | {
        "original_source_and_creation_history",
        "all_svg_fonts_images_scripts_dependency_rights",
        "one_site_client_resale_license_authority",
    },
}


def audit(document):
    if type(document) is not dict or document.get("schema") != SCHEMA:
        raise ValueError("UNSUPPORTED_RIGHTS_REGISTER")
    products = document.get("products")
    if type(products) is not list or len(products) != len(KNOWN):
        raise ValueError("RIGHTS_REGISTER_MUST_HAVE_THREE_PRODUCTS")
    seen = set()
    results = {}
    for item in products:
        if type(item) is not dict:
            raise ValueError("INVALID_PRODUCT_RECORD")
        sku = item.get("sku")
        if type(sku) is not int or sku not in KNOWN or sku in seen:
            raise ValueError("DUPLICATE_OR_UNKNOWN_SKU")
        seen.add(sku)
        digest = item.get("historical_expected_sha256")
        if type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("INVALID_REFERENCE_DIGEST")
        if digest != KNOWN[sku]:
            raise ValueError("HISTORICAL_REFERENCE_DIGEST_CHANGED")
        evidence = item.get("evidence")
        if type(evidence) is not dict or not evidence:
            raise ValueError("MISSING_EVIDENCE_CHECKLIST")
        if set(evidence) != REQUIRED_EVIDENCE[sku]:
            raise ValueError("INCOMPLETE_OR_UNRECOGNIZED_EVIDENCE_SCHEMA")
        if any(type(value) is not str or not value.strip()
               for value in evidence.values() if value is not None):
            raise ValueError("INVALID_UNVERIFIED_EVIDENCE_REFERENCE")
        missing = sorted(key for key, value in evidence.items() if value is None)
        invalid = sorted(key for key, value in evidence.items() if value is not None)
        # Future references must undergo separate verification of source, signature
        # and license scope. A filled string/boolean is not such a verification.
        if item.get("status") not in ("evidence_incomplete", "pending_independent_review"):
            raise ValueError("UNSUPPORTED_LEGAL_STATUS_ASSERTION")
        results[str(sku)] = {
            "documentary_status": "evidence_incomplete" if missing else "references_require_independent_verification",
            "missing_evidence_keys": missing,
            "unverified_submitted_reference_keys": invalid,
            "historical_hash_not_live_integrity_proof": True,
            "metadata_flags_not_copyright_proof": True,
            "commercial_sale_legally_cleared_by_this_script": False,
        }
    if seen != set(KNOWN):
        raise ValueError("MISSING_SKU")
    return {
        "schema": SCHEMA,
        "records_checked": len(results),
        "documentary_clearances_issued": 0,
        "current_private_files_examined": 0,
        "legal_certificate_issued": False,
        "products": results,
    }


def main():
    document = json.loads(REGISTER.read_text(encoding="utf-8"))
    print("MPW_RIGHTS_EVIDENCE_READONLY=" + json.dumps(audit(document), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
