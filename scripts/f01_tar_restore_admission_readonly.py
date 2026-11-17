#!/usr/bin/env python3
"""Fail-closed admission check for a pinned, offline F01 tar metadata audit.

No archive reads, decryption, extraction, DB operations or writes. The audit
itself is observational metadata, not a digital signature or restore proof.
The caller must pin its SHA-256 independently (e.g. a private operator ledger).
Even the best result is only CANDIDATE_FOR_ISOLATED_REVIEW, never permission to
restore a production instance or to extract an archive unattended.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import stat
import sys

SCHEMA = "moj.f01.tar-gzip-readonly-audit.v1"
OUT_SCHEMA = "moj.f01.tar.restore-admission.readonly.v2"
MAX_JSON_BYTES = 1_048_576
HEX_256 = re.compile(r"[0-9a-f]{64}\Z")
HAZARD_LINK_FIELDS = (
    "absolute_symlink_targets", "traversing_symlink_targets", "empty_symlink_targets",
    "absolute_hardlink_targets", "traversing_hardlink_targets", "empty_hardlink_targets",
)
SAFE_LINK_FIELDS = ("non_escalating_relative_symlink_targets", "non_escalating_hardlink_targets")
ARCHIVE_FLAGS = ("archive_sha256_matches", "archive_bytes_match", "gzip_crc_and_trailer_verified")


def _hold(reason: str, *, unsafe_count: int | None = None) -> dict:
    result = {
        "schema": OUT_SCHEMA,
        "decision": "HOLD",
        "reasons": [reason],
        "archive_extracted": False,
        "decrypt_performed": False,
        "live_restore_authorized": False,
        "isolated_extraction_authorized": False,
        "destructive_cleanup_authorized": False,
    }
    if unsafe_count is not None:
        result["unsafe_link_count"] = unsafe_count
    return result


def _int(obj: dict, key: str) -> int:
    val = obj.get(key)
    if type(val) is not int or val < 0:
        raise ValueError("MISSING_OR_INVALID_NUMERIC_FIELD")
    return val


def _optional_int(obj: dict, key: str) -> int:
    """The original audit emits only nonzero link counters; missing means zero.

    To avoid trusting absent counters as zero without evidence, reconcile all
    counters with total symlink and hardlink counts AND independent unsafe
    summary counters. The audit must also be SHA-pinned by its caller.
    """
    if key not in obj:
        return 0
    return _int(obj, key)


def evaluate(doc: object, *, expected_archive_sha256: str) -> dict:
    """Evaluate metadata only; no result authorizes extraction or live restore."""
    try:
        if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
            return _hold("UNKNOWN_AUDIT_SCHEMA")
        if not isinstance(expected_archive_sha256, str) or not HEX_256.fullmatch(expected_archive_sha256):
            return _hold("UNPINNED_ARCHIVE_DIGEST")
        verified, inv, links = doc.get("verified"), doc.get("tar_inventory"), doc.get("link_target_checks")
        if not all(isinstance(v, dict) for v in (verified, inv, links)):
            return _hold("MISSING_AUDIT_GROUP")
        if any(verified.get(k) is not True for k in ARCHIVE_FLAGS):
            return _hold("ARCHIVE_INTEGRITY_UNPROVEN")
        if _int(verified, "gcm_parts_authenticated") != 3:
            return _hold("AUTHENTICATED_PARTS_INCOMPLETE")
        if verified.get("plain_archive_sha256") != expected_archive_sha256:
            return _hold("ARCHIVE_DIGEST_NOT_PINNED_MATCH")
        if verified.get("decrypted_data_written_to_disk") is not False or verified.get("extraction_performed") is not False:
            return _hold("MISSING_NONDESTRUCTIVE_PROVENANCE")
        if verified.get("full_application_restore_performed") is not False:
            return _hold("REPORTED_RESTORE_SCOPE_UNTRUSTED")
        if _int(verified, "plain_archive_bytes") <= 0:
            return _hold("EMPTY_ARCHIVE")

        regular = _int(inv, "regular_files")
        directories = _int(inv, "directories")
        symlinks = _int(inv, "symlinks")
        hardlinks = _int(inv, "hardlinks")
        other = _int(inv, "other_members")
        if regular + directories == 0 or other != symlinks + hardlinks:
            return _hold("UNCLASSIFIED_ARCHIVE_MEMBERS")
        if any(_int(inv, k) > 0 for k in ("absolute_paths", "parent_traversal_names", "device_nodes")):
            return _hold("UNSAFE_MEMBER_PATH_OR_TYPE")
        if _int(inv, "top_level_item_categories") != 1 or inv.get("top_level_roots") != ["factory-runtime"]:
            return _hold("UNEXPECTED_ARCHIVE_ROOTS")
        if not isinstance(doc.get("special_mode_counts"), dict) or doc["special_mode_counts"]:
            return _hold("UNEXPECTED_SPECIAL_FILE_MODES")

        counters = {k: _optional_int(links, k) for k in HAZARD_LINK_FIELDS + SAFE_LINK_FIELDS}
        sym_count = sum(counters[k] for k in HAZARD_LINK_FIELDS[:3]) + counters["non_escalating_relative_symlink_targets"]
        hard_count = sum(counters[k] for k in HAZARD_LINK_FIELDS[3:]) + counters["non_escalating_hardlink_targets"]
        unsafe_sym = sum(counters[k] for k in HAZARD_LINK_FIELDS[:3])
        unsafe_hard = sum(counters[k] for k in HAZARD_LINK_FIELDS[3:])
        if sym_count != symlinks or hard_count != hardlinks:
            return _hold("LINK_COUNTERS_INCOMPLETE_OR_INCONSISTENT")
        if _int(doc, "unsafe_symlink_targets") != unsafe_sym or _int(doc, "unsafe_hardlink_targets") != unsafe_hard:
            return _hold("LINK_HAZARD_SUMMARY_MISMATCH")
        hazards = unsafe_sym + unsafe_hard
        if hazards:
            return _hold("UNSAFE_LINK_TARGETS", unsafe_count=hazards)
        # NOT an extraction authorization, even if all metadata is clean.
        out = _hold("ISOLATION_AND_CONTENT_RESTORE_NOT_PROVEN", unsafe_count=0)
        out["decision"] = "CANDIDATE_FOR_SEPARATE_ISOLATED_REVIEW_ONLY"
        return out
    except (ValueError, TypeError, OverflowError):
        return _hold("INVALID_AUDIT_COUNTER_OR_TYPE")


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("DUPLICATE_JSON_KEY")
        data[key] = value
    return data


def evaluate_file(path: pathlib.Path, *, expected_audit_sha256: str, expected_archive_sha256: str) -> dict:
    """Only an independently pinned local, regular non-symlink audit is accepted."""
    if not isinstance(expected_audit_sha256, str) or not HEX_256.fullmatch(expected_audit_sha256):
        return _hold("AUDIT_HASH_NOT_PINNED")
    try:
        # Pin the object itself: O_NOFOLLOW and fstat on the open descriptor
        # avoid a symlink-swap between an earlier stat and the actual read.
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            s = os.fstat(fd)
            if not stat.S_ISREG(s.st_mode) or not 1 <= s.st_size <= MAX_JSON_BYTES:
                return _hold("UNSAFE_AUDIT_FILE")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                raw = stream.read(MAX_JSON_BYTES + 1)
            if len(raw) != s.st_size or hashlib.sha256(raw).hexdigest() != expected_audit_sha256:
                return _hold("AUDIT_SHA256_MISMATCH")
        finally:
            os.close(fd)
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_keys)
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
        return _hold("INVALID_AUDIT_FILE")
    return evaluate(doc, expected_archive_sha256=expected_archive_sha256)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audit-json", type=pathlib.Path, required=True)
    ap.add_argument("--expected-audit-sha256", required=True)
    ap.add_argument("--expected-archive-sha256", required=True)
    args = ap.parse_args(argv)
    result = evaluate_file(args.audit_json, expected_audit_sha256=args.expected_audit_sha256,
                           expected_archive_sha256=args.expected_archive_sha256)
    print(json.dumps(result, sort_keys=True))
    # This policy gate never authorizes extraction; 0 only means metadata candidate.
    return 0 if result["decision"] == "CANDIDATE_FOR_SEPARATE_ISOLATED_REVIEW_ONLY" else 2


if __name__ == "__main__":
    sys.exit(main())
