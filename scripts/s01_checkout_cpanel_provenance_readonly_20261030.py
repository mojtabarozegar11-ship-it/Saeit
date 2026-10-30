#!/usr/bin/env python3
"""S-01 bounded read-only cPanel checkout provenance. No source text in output."""
import ast
import hashlib
import json
import os
import re
import stat
from pathlib import Path

PIN = "f33d80b7e843a66c9a55d8a8da46d5fb6049fb4c487f8f559c3471cfd42cdf74"
MAX_BYTES = 100_000


def regular_bytes(path, owner_uid, *, private=False):
    """Reject links, wrong owner, oversized, unsafe backup and concurrent changes."""
    path = Path(path)
    if path.parent.is_symlink():
        return None
    try:
        meta = path.lstat()
        if (not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1 or
                meta.st_uid != owner_uid or not (0 < meta.st_size <= MAX_BYTES)):
            return None
        if private and stat.S_IMODE(meta.st_mode) != 0o600:
            return None
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        try:
            opened = os.fstat(fd)
            if opened.st_ino != meta.st_ino or opened.st_dev != meta.st_dev:
                return None
            with os.fdopen(fd, "rb", closefd=False) as stream:
                data = stream.read(MAX_BYTES + 1)
        finally:
            os.close(fd)
        after = path.lstat()
        if (len(data) != meta.st_size or after.st_ino != meta.st_ino or
                after.st_size != meta.st_size or after.st_mtime_ns != meta.st_mtime_ns):
            return None
        return data
    except (OSError, ValueError):
        return None


def ast_fingerprint(data):
    try:
        tree = ast.parse(data)
        return hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()
    except (SyntaxError, UnicodeError, ValueError, TypeError):
        return None


def probe(home, *, expected=PIN, owner_uid=None):
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("invalid SHA256 pin")
    home = Path(home)
    uid = os.getuid() if owner_uid is None else owner_uid
    source = home / "Saeit-staging/mpw_commerce/product_checkout_page.py"
    production = home / "Saeit/mpw_commerce/product_checkout_page.py"
    private_dir = home / ".private_mojplaywin_main_agents"
    private_file = private_dir / ("mpw-checkout-csp-preimage-" + expected[:16] + ".bak")
    report = {
        "scope": "S01_CPANEL_CHECKOUT_PROVENANCE_READONLY",
        "source_status": "UNAVAILABLE_OR_UNSAFE",
        "source_matches_pin": False,
        "candidate_states": {},
        "approved_reference_found": False,
        "classification": "BLOCKED",
        "cpanel_writes": False,
        "factory_writes": False,
        "release_permitted": False,
        "passenger_db_authority_verified": False,
        "off_vps_restore_verified": False,
    }
    current = regular_bytes(source, uid)
    if current is None:
        return report
    digest = hashlib.sha256(current).hexdigest()
    report["source_status"] = "READABLE"
    report["source_sha256"] = digest
    report["source_bytes"] = len(current)
    report["source_syntax_valid"] = ast_fingerprint(current) is not None
    report["source_matches_pin"] = digest == expected
    candidates = [("production_tree", production, False), ("private_preimage", private_file, True)]
    approved = None
    for label, path, private in candidates:
        try:
            safe_dir = (not private or (private_dir.is_dir() and not private_dir.is_symlink()
                and private_dir.stat().st_uid == uid
                and stat.S_IMODE(private_dir.stat().st_mode) == 0o700))
        except OSError:
            safe_dir = False
        data = regular_bytes(path, uid, private=private) if safe_dir else None
        state = ("UNAVAILABLE_OR_UNSAFE" if data is None else
                 "PIN_MATCH" if hashlib.sha256(data).hexdigest() == expected else "OTHER_SHA")
        report["candidate_states"][label] = state
        if state == "PIN_MATCH" and approved is None:
            approved = data
            report["approved_reference_label"] = label
    report["approved_reference_found"] = approved is not None
    if digest == expected:
        report["classification"] = "SOURCE_PIN_MATCH_RELEASE_STILL_BLOCKED"
    elif approved is None:
        report["classification"] = "SOURCE_SHA_DRIFT_NO_APPROVED_COPY"
    else:
        ref_ast = ast_fingerprint(approved)
        now_ast = ast_fingerprint(current)
        report["ast_equivalent"] = (ref_ast == now_ast if ref_ast and now_ast else None)
        report["first_difference_offset"] = next(
            (i for i, (a, b) in enumerate(zip(approved, current)) if a != b),
            min(len(approved), len(current)))
        report["classification"] = ("SOURCE_SHA_DRIFT_AST_EQUIVALENT" if report["ast_equivalent"]
            else "SOURCE_SHA_DRIFT_SEMANTIC_OR_SYNTAX_DIFFERENCE")
    return report


if __name__ == "__main__":
    try:
        print("S01_PROVENANCE=" + json.dumps(probe("/home/zomorod2"), sort_keys=True))
    except (OSError, ValueError, RuntimeError):
        print("S01_PROVENANCE=" + json.dumps({
            "classification": "BLOCKED", "cpanel_writes": False,
            "factory_writes": False, "release_permitted": False
        }))
        raise SystemExit(3)
