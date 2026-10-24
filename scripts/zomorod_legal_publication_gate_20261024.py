#!/usr/bin/env python3
"""Offline intake gate for Zomorod Melal company-registration evidence.

A valid shape is NOT a live registry lookup or an authenticity certificate.
Inputs may contain private documents: do not commit them or publish the output
without a separate human review. This program never accesses the network.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
NATIONAL_ID = re.compile(r"^\d{11}$")
REQUIRED = {
    "national_identity": {"ilenc.ssaa.ir", "my.ssaa.ir"},
    "incorporation_notice": {"rrk.ir", "www.rrk.ir"},
    "latest_changes": {"rrk.ir", "www.rrk.ir"},
}
MAX_BYTES = 256 * 1024


def _date(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return parsed <= datetime.now(timezone.utc).date()


def _official_url(value, allowed_hosts):
    if not isinstance(value, str) or len(value) > 2048:
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "https"
            and (parsed.hostname or "").lower().rstrip(".") in allowed_hosts
            and not parsed.username and not parsed.password
            and parsed.port in (None, 443)
            and not parsed.fragment
        )
    except ValueError:
        return False


def assess(package):
    """Check evidence format; NEVER claim official verification or authorize publishing."""
    gaps = []
    if not isinstance(package, dict):
        return {"status": "BLOCKED", "gaps": ["input:not_object"],
                "publication_allowed": False, "official_verification_granted": False}
    identity = package.get("identity")
    if not isinstance(identity, dict):
        identity = {}
    if not isinstance(identity.get("legal_name"), str) or len(identity["legal_name"].strip()) < 5:
        gaps.append("identity:legal_name_missing")
    national_id = identity.get("national_id")
    if not isinstance(national_id, str) or not NATIONAL_ID.fullmatch(national_id):
        gaps.append("identity:national_id_format")
    evidence = package.get("evidence")
    if not isinstance(evidence, dict):
        evidence = {}
    # A format-valid record is only a request for *human* source comparison.
    # A checksum establishes file identity, not the document's legal authenticity.
    for kind, hosts in REQUIRED.items():
        item = evidence.get(kind)
        if not isinstance(item, dict):
            gaps.append(kind + ":missing")
            continue
        if not _official_url(item.get("source_url"), hosts):
            gaps.append(kind + ":official_source_url")
        if not isinstance(item.get("record_number"), str) or not 1 <= len(item["record_number"].strip()) <= 100:
            gaps.append(kind + ":record_number")
        if not _date(item.get("issued_at")):
            gaps.append(kind + ":issue_date")
        digest = item.get("sha256")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            gaps.append(kind + ":digest")
        if not _date(item.get("checked_at")):
            gaps.append(kind + ":lookup_date")
        # Verified-by and true flags are intentionally NOT accepted as proof.
    # Later amendments can supersede original powers of representation.
    signing = package.get("signing_authority_review")
    if not isinstance(signing, dict) or signing.get("matched_to_latest_changes") is not True:
        gaps.append("signing_authority:current_powers_not_matched")
    if not isinstance(signing, dict) or not _date(signing.get("reviewed_at")):
        gaps.append("signing_authority:review_date")
    if not isinstance(package.get("public_disclosure_approval"), dict) or (
        package["public_disclosure_approval"].get("approved") is not True
    ):
        gaps.append("privacy:publication_approval_missing")
    return {
        "schema": "zomorod.legal-evidence-intake.v1",
        "status": "REVIEW_CANDIDATE" if not gaps else "BLOCKED",
        "gaps": sorted(set(gaps)),
        "publication_allowed": False,
        "official_verification_granted": False,
        "next_action": "Compare primary records, verify signatories and privacy approval independently before publication",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Private JSON evidence metadata; never commit")
    args = parser.parse_args()
    if not args.input:
        parser.error("--input is required")
    source = Path(args.input)
    if source.stat().st_size > MAX_BYTES:
        parser.error("input exceeds 256 KiB safety limit")
    output = assess(json.loads(source.read_text(encoding="utf-8")))
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
