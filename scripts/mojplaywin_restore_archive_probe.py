#!/usr/bin/env python3
"""Privacy-safe, read-only examination of existing encrypted backup tar stream.

Input: plaintext tar followed by a fixed completion footer, on stdin (over a
private VPS-only pipe). No archive/files/dump are written or printed here.
Reports bounded counts and the FIRST sanitized rejection reason only.
This is NOT a successful restore certification and never authorizes release.
"""
from __future__ import annotations
import json
import posixpath
import sys
import tarfile
from pathlib import PurePosixPath

ROOTS = {"Saeit-staging", "mojplaywin.com"}
MARKER = b"\n-- MJWP-RECOVERY-20261017-COMPLETE-F91D7C40 --\n"
MAX_ENTRIES = 500_000
MAX_BYTES = 12 * 1024**3
ALLOWED_LINK_ROOTS = ROOTS

def classify(name: str, kind: str = "path") -> str | None:
    if not isinstance(name, str) or not name:
        return kind + "_empty"
    if name.startswith("/"):
        return kind + "_absolute"
    if name.startswith("./"):
        return kind + "_dot_prefix"
    p = PurePosixPath(name)
    if ".." in p.parts:
        return kind + "_traversal"
    if not p.parts or p.parts[0] not in ROOTS:
        return kind + "_outside_fixed_roots"
    return None

def link_kind(name: str, target: str, symlink: bool) -> str:
    if not isinstance(target, str) or not target:
        return "link_empty"
    if target.startswith("/"):
        return "link_absolute"
    if symlink:
        full = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
    else:
        full = posixpath.normpath(target)
    return classify(full, "link") or "link_internal"

def probe(stream) -> dict:
    counts = dict(regular=0, directories=0, symlinks=0, hardlinks=0,
                  specials=0, external_links=0, unsafe_names=0, duplicates=0)
    seen = set()
    roots = set()
    first_issue = None
    issue_counts: dict[str, int] = {}
    total = 0

    def issue(reason: str) -> None:
        nonlocal first_issue
        if first_issue is None:
            first_issue = reason
        issue_counts[reason] = issue_counts.get(reason, 0) + 1

    with tarfile.open(fileobj=stream, mode="r|") as tar:
        for member in tar:
            total += 1
            if total > MAX_ENTRIES:
                issue("too_many_members")
                break
            name = member.name
            why = classify(name)
            if why:
                counts["unsafe_names"] += 1
                issue(why)
            else:
                normal = str(PurePosixPath(name))
                roots.add(PurePosixPath(name).parts[0])
                if normal in seen:
                    counts["duplicates"] += 1
                    issue("duplicate_member")
                seen.add(normal)
            if member.isdir():
                counts["directories"] += 1
            elif member.isfile():
                counts["regular"] += 1
                if member.size < 0 or member.size > MAX_BYTES:
                    issue("invalid_member_size")
            elif member.issym():
                counts["symlinks"] += 1
                kind = link_kind(name, member.linkname, True)
                if kind != "link_internal":
                    counts["external_links"] += 1
                    issue(kind)
            elif member.islnk():
                counts["hardlinks"] += 1
                kind = link_kind(name, member.linkname, False)
                if kind != "link_internal":
                    counts["external_links"] += 1
                    issue(kind)
            else:
                counts["specials"] += 1
                issue("special_member")
    # Intentionally no names, targets or content even on error.
    return {
        "classification": "READ_ONLY_ARCHIVE_STRUCTURE_DIAGNOSTIC",
        "entry_count": total,
        "roots_present": sorted(roots),
        "counts": counts,
        "first_issue": first_issue or "none_detected",
        "issue_counts": dict(sorted(issue_counts.items())),
        "source_integrity_verified_by_probe": False,
        "isolated_restore_completed": False,
        "release_permitted": False,
        "production_modified": False,
    }

if __name__ == "__main__":
    try:
        result = probe(sys.stdin.buffer)
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        # Class only, no exception message: exceptions may contain private member names.
        print(json.dumps({"classification": "READ_ONLY_ARCHIVE_STRUCTURE_DIAGNOSTIC",
                          "scan_error_type": type(error).__name__,
                          "isolated_restore_completed": False, "release_permitted": False,
                          "production_modified": False}, sort_keys=True))
        raise SystemExit(1)
