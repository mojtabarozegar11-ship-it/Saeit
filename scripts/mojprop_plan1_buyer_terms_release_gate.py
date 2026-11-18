#!/usr/bin/env python3
"""Fail-closed buyer-terms byte/version parity for NONPAYABLE Plan1 sidecar.

This checks source representation, NOT legal permission, broker proof, funding,
customer consent, an offsite restore, or a release authorization. No network,
filesystem write, database, deployment, or personal data access is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

MINIMUM_PROSPECTIVE_REVISION = (1, 4, 1)
VERSION_RE = re.compile(r"^v([1-9]\d*)\.([0-9]+)(?:\.([0-9]+))?$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
UNRESOLVED_TEXT = (
    "social-post conditions are under contract review",
    "no social post is requested while paid enrollment is closed",
)
REQUIRED_NONPAYABLE_EN = "Not open for paid enrollment"
REQUIRED_NONPAYABLE_FA = "فروش و پرداخت فعال نیست"
REQUIRED_NONPAYABLE_FA_EXPANDED = "فروش، ثبت‌نام، ثبت رضایت و پرداخت فعال نیست"
FA_SECTION = re.compile(r'<section\b[^>]*\bid=["\x27]fa["\x27]', re.I)
DANGEROUS_HTML = (
    re.compile(r"<form\b", re.I),
    re.compile(r"<script\b(?![^>]*type=['\"]application/ld\+json['\"])", re.I),
    re.compile(r"<a\b[^>]*href=['\"][^'\"]*(?:/checkout/|/moj-prop-interest/form/)", re.I),
)


def revision(value: str) -> tuple[int, int, int] | None:
    if not isinstance(value, str):
        return None
    match = VERSION_RE.fullmatch(value)
    if not match:
        return None
    return tuple(int(part or "0") for part in match.groups())


def evaluate(page: bytes, approved_version: str, approved_sha256: str) -> dict:
    """Report pure source parity; even PASS does not establish legal permission."""
    failures: list[str] = []
    actual_sha256 = hashlib.sha256(page).hexdigest()
    ver = revision(approved_version)
    if ver is None or ver < MINIMUM_PROSPECTIVE_REVISION:
        failures.append("unapproved_or_obsolete_revision")
    if not isinstance(approved_sha256, str) or not SHA256_RE.fullmatch(approved_sha256):
        failures.append("missing_exact_approved_copy_sha256")
    elif approved_sha256 != actual_sha256:
        failures.append("reviewed_copy_byte_mismatch")
    try:
        text = page.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        text = ""
        failures.append("source_not_utf8")
    if len(page) == 0 or len(page) > 131072:
        failures.append("untrusted_source_size")
    marker = FA_SECTION.search(text)
    if marker is None:
        failures.append("missing_persian_section")
    elif not isinstance(approved_version, str) or (
        approved_version not in text[:marker.start()]
        or approved_version not in text[marker.start():]
    ):
        failures.append("english_persian_revision_mismatch")
    if (REQUIRED_NONPAYABLE_EN not in text or not any(
        phrase in text for phrase in (REQUIRED_NONPAYABLE_FA, REQUIRED_NONPAYABLE_FA_EXPANDED)
    )):
        failures.append("nonpayable_disclosure_missing")
    low = text.lower()
    if any(fragment in low for fragment in UNRESOLVED_TEXT):
        failures.append("unresolved_buyer_terms")
    if any(regex.search(text) for regex in DANGEROUS_HTML):
        failures.append("interactive_form_script_or_checkout")
    return {
        "schema": "mojprop.plan1.buyer_terms.release_parity.v1",
        "source_sha256": actual_sha256,
        "approved_version": approved_version,
        "copy_parity_passed": not failures,
        "reasons": sorted(set(failures)),
        "independent_legal_approval_proven_by_this_tool": False,
        "independent_restore_proven_by_this_tool": False,
        "payment_enabled": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", type=Path, required=True)
    parser.add_argument("--approved-version", required=True)
    parser.add_argument("--approved-sha256", required=True)
    args = parser.parse_args()
    try:
        path = args.page
        if path.is_symlink() or not path.is_file():
            raise OSError("nonregular_or_symlink_source")
        page = path.read_bytes()
        result = evaluate(page, args.approved_version, args.approved_sha256)
    except OSError:
        result = {
            "schema": "mojprop.plan1.buyer_terms.release_parity.v1",
            "copy_parity_passed": False,
            "reasons": ["unreadable_or_nonregular_source"],
            "independent_legal_approval_proven_by_this_tool": False,
            "independent_restore_proven_by_this_tool": False,
            "payment_enabled": False,
        }
    print("MOJPROP_PLAN1_BUYER_TERMS_PARITY=" + json.dumps(result, sort_keys=True))
    return 0 if result["copy_parity_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
