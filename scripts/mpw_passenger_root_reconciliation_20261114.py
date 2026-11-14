#!/usr/bin/env python3
"""Bounded, redacted reconciliation of existing cPanel Passenger UAPI evidence.

Consumes only the JSON emitted by mojplaywin_cpanel_readonly_inventory.py.
Never imports Django, connects to cPanel, reads credentials or changes data.
A matching fingerprint is source-registration evidence ONLY, never proof
of which worker actually renders /store/ or a completed customer purchase.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA = "mojtaba.bot.ai.mpw-passenger-root-reconciliation.v1"
MAX_INPUT_BYTES = 65536
EXPECTED_ROOTS = {
    "stage": "/home/zomorod2/Saeit-staging",
    "public": "/home/zomorod2/mojplaywin.com",
}
DOMAINS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))
HEX16 = re.compile(r"[0-9a-f]{16}\Z")
REDACTED_URI = re.compile(r"\(unlisted-path-[0-9a-f]{12}\)\Z")


def _unique_object(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def load_sanitized(stream):
    """Reject raw UAPI and oversized/ambiguous reports without echoing data."""
    raw = stream.read(MAX_INPUT_BYTES + 1)
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_INPUT_BYTES:
        raise ValueError("sanitized report missing or oversized")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                           parse_constant=lambda _value: (_ for _ in ()).throw(
                               ValueError("nonfinite JSON")))
    except (ValueError, UnicodeError, TypeError, RecursionError):
        raise ValueError("invalid sanitized JSON") from None
    if type(value) is not dict or value.get("classification") != "READ_ONLY_PASSENGER_INVENTORY":
        raise ValueError("not a sanitized passenger inventory")
    return value


def _root_fingerprints():
    return {label: hashlib.sha256(root.encode("utf-8")).hexdigest()[:16]
            for label, root in EXPECTED_ROOTS.items()}


def inspect(report):
    """Return only fixed classifications, counts and Boolean evidence."""
    if type(report) is not dict or report.get("classification") != "READ_ONLY_PASSENGER_INVENTORY":
        raise ValueError("unexpected report category")
    if report.get("release_permitted") is not False:
        raise ValueError("unsafe or missing release permission field")
    if report.get("production_isolation_proven") is not False:
        raise ValueError("unsupported isolation assertion")
    if report.get("recoverable_backups_verified") is not False:
        raise ValueError("unsupported backup assertion")
    if report.get("secrets_or_full_app_root_paths_printed") is not False:
        raise ValueError("non-redacted inventory")
    records = report.get("uapi_records_discovered")
    if type(records) is not int or not 0 <= records <= 256:
        raise ValueError("invalid record count")
    mappings = report.get("mojplaywin_passenger_mappings")
    if type(mappings) is not list or len(mappings) > 32:
        raise ValueError("invalid mappings")
    roots = _root_fingerprints()
    classified = []
    identities = set()
    for app in mappings:
        if type(app) is not dict:
            raise ValueError("malformed mapping")
        domain, uri, fingerprint = (app.get("domain"), app.get("base_uri"),
                                    app.get("app_root_fingerprint"))
        if domain not in DOMAINS or not isinstance(domain, str):
            raise ValueError("unrecognized domain")
        if type(uri) is not str or not (
                uri == "/" or uri.startswith("/mojtaba.roozegar/")
                or uri.startswith("/picm/") or uri.startswith("/studio.Roham/")
                or uri.startswith("/saman/") or uri.startswith("/zahra$$/")
                or uri.startswith("/farnaz/") or uri.startswith("/taniya/")
                or REDACTED_URI.fullmatch(uri)):
            raise ValueError("untrusted mapping path")
        if type(fingerprint) is not str or not HEX16.fullmatch(fingerprint):
            raise ValueError("invalid root fingerprint")
        if type(app.get("references_shared_saeit_staging")) is not bool:
            raise ValueError("staging marker not boolean")
        identity = (domain, uri, fingerprint)
        if identity in identities:
            raise ValueError("duplicate mapping")
        identities.add(identity)
        kind = ("stage" if fingerprint == roots["stage"]
                else "public" if fingerprint == roots["public"]
                else "other_or_unrecognized")
        classified.append((kind, uri == "/", app["references_shared_saeit_staging"]))
    if records < len(mappings):
        raise ValueError("mapping count exceeds record count")
    unique_main = len(classified) == 1
    same_stage = unique_main and classified[0][0] == "stage"
    same_public = unique_main and classified[0][0] == "public"
    explicit_root = unique_main and classified[0][1]
    return {
        "schema": SCHEMA,
        "canonical_bot": "mojtaba.bot.ai",
        "uapi_records": records,
        "mpw_mappings": len(classified),
        "single_mpw_mapping": unique_main,
        "source_root_matches_staging_candidate": bool(same_stage),
        "source_root_matches_public_candidate": bool(same_public),
        "source_root_matches_either_candidate": bool(same_stage or same_public),
        "base_uri_explicit_slash": bool(explicit_root),
        "unlisted_base_uri": bool(unique_main and not explicit_root
                                  and str(mappings[0]["base_uri"]).startswith("(unlisted-path-")),
        "root_registration_mismatch": bool(unique_main and not (same_stage or same_public)),
        "candidate_staging_marker_present": bool(unique_main and classified[0][2]),
        "source_candidate_attestation": (
            "source_staging_match_only" if same_stage else
            "public_document_root_match_only" if same_public else
            "unknown_or_mismatched_root"
        ),
        "effective_wsgi_worker_attested": False,
        "effective_django_template_attested": False,
        "migration_applied_attested": False,
        "checkout_email_post_attested": False,
        "correct_public_csp_attested": False,
        "dynamic_store_attested": False,
        "paid_settlement_attested": False,
        "customer_entitlement_attested": False,
        "actual_collected_revenue": None,
        "release_permitted": False,
        "external_network_access": False,
        "customer_data_read": False,
        "files_modified": False,
        "sensitive_paths_emitted": False,
    }


def main():
    try:
        report = inspect(load_sanitized(sys.stdin.buffer))
    except (ValueError, TypeError, KeyError, AttributeError):
        print("MPW_PASSENGER_RECONCILIATION=INVALID_SANITIZED_EVIDENCE")
        return 2
    print("MPW_PASSENGER_RECONCILIATION=" +
          json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
