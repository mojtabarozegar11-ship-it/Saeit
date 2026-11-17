"""Source-only fixed-digest public MOJ-PROP-01 static-release integrity evidence.

Compares ONLY public GET bytes to an independently recorded last trusted cPanel
fingerprint, and the repo candidate to the pinned GitHub-hosted SHA-256. Never
uploads, writes production, checks customer private data, or approves release.

The old public HTML was independently fingerprinted via authenticated pinned
SSH from an owner-controlled factory VPS to cPanel; this module does not claim
the external public GET is *itself* proof of the effective Apache/Passenger map.
"""
from __future__ import annotations

from hashlib import sha256

OLD_SHA = "76918c5129ff669ef02f82435a68f61a32d70141800712100d4a7fe9e8554895"
OLD_SIZE = 23869
NEW_SHA = "13bd45c1d6b62f03058428b3086e71b17de4f2776238e8ab85a49d648fce49b0"
NEW_SIZE = 46455
MAX_HTML_BYTES = 256 * 1024
PUBLIC = "https://mojplaywin.com/moj-prop/"


class StaticSourceIdentityRejected(ValueError):
    """Never overwrite an unknown or changed cPanel source."""


def _validated_bytes(raw, expected_sha: str, expected_size: int, *, name: str) -> None:
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_HTML_BYTES:
        raise StaticSourceIdentityRejected(name + ": unbounded or non-byte payload")
    if len(raw) != expected_size or sha256(raw).hexdigest() != expected_sha:
        raise StaticSourceIdentityRejected(name + ": size or sha256 mismatch")


def classify(live_public_html: bytes, proposed_repo_html: bytes,
             *, old_sha=OLD_SHA, old_size=OLD_SIZE,
             new_sha=NEW_SHA, new_size=NEW_SIZE) -> dict:
    """Pure fail-closed candidate inspection, *not* an authorized deploy."""
    _validated_bytes(live_public_html, old_sha, old_size, name="prior live")
    _validated_bytes(proposed_repo_html, new_sha, new_size, name="proposed")
    if not live_public_html.startswith(b"<!-- MOJ_PROP_CATALOG_RELEASE_V4 -->"):
        raise StaticSourceIdentityRejected("unexpected public HTML family")
    if b'<select id="horizon">' not in live_public_html:
        raise StaticSourceIdentityRejected("previous live intake form missing")
    if b'MOJ-PROP-01' not in proposed_repo_html:
        raise StaticSourceIdentityRejected("candidate does not identify the genuine challenge")
    if b'Contact MOJ PROP about Plan 1 (free)' not in proposed_repo_html:
        raise StaticSourceIdentityRejected("candidate lacks legal prelaunch contact")
    if b'do not send the bearer token by email' not in proposed_repo_html:
        raise StaticSourceIdentityRejected("candidate lacks receipt privacy guard")
    if b'Do not send money today.' not in proposed_repo_html:
        raise StaticSourceIdentityRejected("candidate lacks explicit anti-payment warning")
    if b'href="/moj-prop-interest/form/' in proposed_repo_html:
        raise StaticSourceIdentityRejected("candidate invites known production-404 form")
    return {
        "classification": "MOJPROP_PUBLIC_STATIC_EXACT_PRESENCE_GUARD",
        "sku": "MOJ-PROP-01",
        "public_url": PUBLIC,
        "old_public_html_verified_sha256": old_sha,
        "old_public_html_verified_bytes": old_size,
        "new_repo_candidate_verified_sha256": new_sha,
        "new_repo_candidate_bytes": new_size,
        "candidate_source_matches_documented_code": True,
        "public_get_header_and_tls_verified_by_this_pure_function": False,
        "cPanel_live_passenger_backend_proven": False,
        "fresh_restorable_offsite_backup_proven": False,
        "owner_case_specific_deploy_approval_obtained": False,
        "production_change_made": False,
        "production_database_modified": False,
        "private_customer_data_read": False,
        "payment_opened": False,
        "lead_created": False,
        "release_allowed": False,
    }
