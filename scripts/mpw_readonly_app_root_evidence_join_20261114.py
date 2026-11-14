#!/usr/bin/env python3
"""Join only two separately SANITIZED cPanel reports, without remote access.

An equal 16-character digest may corroborate a *directory candidate*, not
identify a loaded WSGI worker, verify a Django template or authorize release.
"""
from __future__ import annotations

import json
import re
import sys

SCHEMA = "mojtaba.bot.ai.mpw-root-evidence-join.v1"
MAX_INPUT = 131072
DIGEST = re.compile(r"[0-9a-f]{16}\Z")
MARKERS = frozenset({
    "wsgi_marker_only",
    "wsgi_and_mpw_checkout_markers",
    "mpw_checkout_source_markers",
})


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def read_bounded(stream):
    raw = stream.read(MAX_INPUT + 1)
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_INPUT:
        raise ValueError("invalid report size")
    try:
        r = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(
                           ValueError("invalid number")))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ValueError("invalid report JSON") from None
    if type(r) is not dict or set(r) != {"uapi", "source"}:
        raise ValueError("expected two sanitized reports")
    return r


def compare(uapi, source):
    if type(uapi) is not dict or type(source) is not dict:
        raise ValueError("malformed inputs")
    if uapi.get("classification") != "READ_ONLY_PASSENGER_INVENTORY":
        raise ValueError("raw or inappropriate UAPI evidence")
    if uapi.get("secrets_or_full_app_root_paths_printed") is not False:
        raise ValueError("unredacted UAPI")
    if uapi.get("release_permitted") is not False:
        raise ValueError("unapproved UAPI release")
    if source.get("schema") != "mpw.cpanel.source_provenance.readonly.v1":
        raise ValueError("unverified on-disk report schema")
    for field in ("customer_data_read", "database_accessed", "files_modified",
                  "production_release_permitted_by_this_report"):
        if source.get(field) is not False:
            raise ValueError("untrusted source claim")
    mapping = uapi.get("mojplaywin_passenger_mappings")
    if type(mapping) is not list or len(mapping) > 8:
        raise ValueError("unsafe UAPI mapping count")
    roots = source.get("neighbor_root_fingerprints")
    if type(roots) is not dict:
        raise ValueError("missing bounded source inventory")
    if roots.get("release_permitted") is not False:
        raise ValueError("source inventory claims authority")
    if roots.get("effective_passenger_worker_attested") is not False:
        raise ValueError("effective worker not verifiable")
    status = roots.get("status")
    if status not in {
        "bounded_immediate_home_scan", "home_unavailable_or_unsafe",
        "entry_budget_exceeded", "candidate_budget_exceeded",
        "fingerprint_collision_unverified",
    }:
        raise ValueError("unknown scan category")
    candidates = roots.get("candidates")
    count = roots.get("candidate_count")
    if (type(candidates) is not list or len(candidates) > 16
            or type(count) is not int or count != len(candidates)):
        raise ValueError("source candidate count conflict")
    if status != "bounded_immediate_home_scan" and candidates:
        raise ValueError("failed scan cannot assert candidates")
    markers = set()
    for candidate in candidates:
        if type(candidate) is not dict:
            raise ValueError("invalid candidate")
        fp = candidate.get("root_sha256_prefix")
        if type(fp) is not str or not DIGEST.fullmatch(fp) or fp in markers:
            raise ValueError("invalid or duplicate candidate fingerprint")
        markers.add(fp)
        if candidate.get("marker_class") not in MARKERS:
            raise ValueError("unapproved marker classification")
        if candidate.get("registered_root_verified") is not False:
            raise ValueError("registered root not independently proven")
        if candidate.get("effective_checkout_verified") is not False:
            raise ValueError("checkout not independently proven")
    fingerprints = []
    for entry in mapping:
        if type(entry) is not dict or entry.get("domain") not in (
                "mojplaywin.com", "www.mojplaywin.com"):
            raise ValueError("unexpected Passenger mapping domain")
        fp = entry.get("app_root_fingerprint")
        if type(fp) is not str or not DIGEST.fullmatch(fp):
            raise ValueError("malformed UAPI root fingerprint")
        fingerprints.append(fp)
    if len(fingerprints) != len(set(fingerprints)):
        raise ValueError("ambiguous duplicate UAPI roots")
    if len(fingerprints) != 1:
        status_join = "missing_or_multiple_uapi_roots"
    elif status != "bounded_immediate_home_scan":
        status_join = "bounded_source_scan_incomplete"
    elif fingerprints[0] in markers:
        status_join = "one_immediate_root_fingerprint_corresponds"
    else:
        status_join = "no_immediate_root_fingerprint_corresponds"
    return {
        "schema": SCHEMA,
        "canonical_bot": "mojtaba.bot.ai",
        "classification": status_join,
        "sanitized_uapi_roots_count": len(fingerprints),
        "bounded_source_root_candidates_count": len(markers),
        "root_registration_source_correspondence_only":
            status_join == "one_immediate_root_fingerprint_corresponds",
        "effective_passenger_worker_verified": False,
        "effective_checkout_template_verified": False,
        "dynamic_catalog_verified": False,
        "production_csp_verified": False,
        "payment_finality_verified": False,
        "paid_delivery_verified": False,
        "actual_collected_revenue": None,
        "release_permitted": False,
        "network_access": False,
        "disk_writes": False,
        "customer_data_read": False,
        "full_paths_emitted": False,
    }


def main():
    try:
        inputs = read_bounded(sys.stdin.buffer)
        answer = compare(inputs["uapi"], inputs["source"])
    except (ValueError, TypeError, KeyError, AttributeError, OSError):
        print("MPW_ROOT_EVIDENCE_JOIN=INVALID_SANITIZED_INPUT")
        return 2
    print("MPW_ROOT_EVIDENCE_JOIN=" +
          json.dumps(answer, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
