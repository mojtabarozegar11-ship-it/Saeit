#!/usr/bin/env python3
"""Fail closed on an Atelier Sites preview metadata-versus-paid-product gap.

This verifies a dated, source-recorded observation, NOT current remote state,
authorship, licensing, paid ZIP bytes, a checkout, or the Sites deployment.
"""

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "catalog/mojplaywin/atelier_demo_identity_snapshot_20261110.json"
SCHEMA = "mojplaywin.atelier-demo-identity-snapshot.v1"
PROJECT = "appgprj_6ad8bc1db4748191af8fb37df7c793aa"
PAID_ZIP_HISTORIC_SHA = "98bffad4ccf36f84c7924ca77e4a8b473b42f33a8fce4d85cefe2367afc097aa"


def audit(snapshot):
    if type(snapshot) is not dict or snapshot.get("schema") != SCHEMA:
        raise ValueError("INVALID_DEMO_PROVENANCE_SCHEMA")
    site = snapshot.get("preview_site")
    evidence = snapshot.get("assessment")
    if type(site) is not dict or type(evidence) is not dict:
        raise ValueError("MISSING_DEMO_PROVENANCE_RECORD")
    if (snapshot.get("product_id") != 879
            or site.get("project_id") != PROJECT
            or site.get("slug") != "atelier-interior-kit-demo"
            or site.get("url") != "https://atelier-interior-kit-demo.mojtaba-rozegar11.chatgpt.site"):
        raise ValueError("DEMO_IDENTITY_PIN_MISMATCH")
    if snapshot.get("commercial_private_zip_historical_sha256") != PAID_ZIP_HISTORIC_SHA:
        raise ValueError("PAID_ZIP_HISTORICAL_HASH_CHANGED")
    for key in ("latest_saved_archive_sha256", "oldest_saved_archive_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(site.get(key, ""))):
            raise ValueError("INVALID_SITES_ARCHIVE_DIGEST")
    if (type(site.get("latest_version_number")) is not int
            or type(site.get("oldest_listed_version_number")) is not int
            or site["latest_version_number"] <= site["oldest_listed_version_number"]):
        raise ValueError("INVALID_SITES_VERSION_RANGE")
    title_matches = site.get("current_metadata_title") == snapshot.get("commercial_product_title")
    if evidence.get("metadata_title_equals_commercial_product_title") is not title_matches:
        raise ValueError("DEMO_TITLE_MATCH_ASSERTION_INCONSISTENT")
    if evidence.get("status") != "requires_manual_source_and_rights_reconciliation":
        raise ValueError("UNSUPPORTED_DEMO_LEGAL_STATUS")
    for key in (
        "sites_archive_proven_equivalent_to_paid_zip",
        "original_svg_authorship_independently_verified",
        "commercial_redistribution_rights_independently_verified",
        "current_live_page_contents_inspected_by_sites_connector",
    ):
        if evidence.get(key) is not False:
            raise ValueError("UNSUPPORTED_UNVERIFIED_CLEARANCE_CLAIM")
    if evidence.get("site_metadata_not_proof_of_copyright") is not True:
        raise ValueError("METADATA_NOT_LEGAL_RIGHTS_PROOF")
    return {
        "product_id": 879,
        "site_project_identified": True,
        "saved_versions_span": [site["oldest_listed_version_number"], site["latest_version_number"]],
        "source_metadata_title_differs_from_offer": not title_matches,
        "commercial_paid_zip_equivalence": "unverified",
        "embedded_asset_rights": "unverified",
        "commercial_legal_clearance_issued": False,
        "live_site_changed": False,
    }


def main():
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    print("ATELIER_DEMO_READONLY=" + json.dumps(audit(snapshot), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
