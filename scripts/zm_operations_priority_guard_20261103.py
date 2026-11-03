#!/usr/bin/env python3
"""Read-only verification for the live ZM operations priority-order correction.

No deployment, database mutation, or network requests. The live release is
separately guarded by a private backup, PHP lint and anonymous HTTP 403 check.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sqlite3

OLD = "ORDER BY id DESC LIMIT 7"
NEW = (
    "ORDER BY CASE priority "
    "WHEN 'critical' THEN 0 WHEN 'high' THEN 1 "
    "WHEN 'normal' THEN 2 ELSE 3 END, id DESC LIMIT 7"
)


def patch(source: str) -> str:
    if source.count(OLD) != 1 or NEW in source:
        raise ValueError("LIVE_PRIORITY_ANCHOR_MISSING_OR_ALREADY_PATCHED")
    return source.replace(OLD, NEW, 1)


def self_test() -> None:
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE tasks(id INTEGER, priority TEXT, state TEXT)")
    db.executemany(
        "INSERT INTO tasks VALUES(?,?,?)",
        [(1, "normal", "queued"), (2, "critical", "queued"),
         (3, "high", "queued"), (4, "normal", "queued"),
         (5, "critical", "queued"), (6, "critical", "closed")],
    )
    query = (
        "SELECT id FROM tasks WHERE state NOT IN "
        "('done','closed','cancelled') " + NEW
    )
    assert [r[0] for r in db.execute(query)] == [5, 2, 3, 4, 1]
    sample = "SELECT title FROM tasks " + OLD
    assert patch(sample) == "SELECT title FROM tasks " + NEW
    for unsafe in ("", "SELECT title FROM tasks", sample + " " + OLD):
        try:
            patch(unsafe)
        except ValueError:
            pass
        else:
            raise AssertionError("Fail-closed anchor validation failed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    self_test()
    print("PRIORITY_SQL_SYNTHETIC=PASS")
    print("PATCH_FAIL_CLOSED=PASS")
    if args.source:
        path = args.source
        if path.is_symlink() or not path.is_file():
            raise SystemExit("INVALID_SOURCE")
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if args.expected_sha256 and sha != args.expected_sha256:
            raise SystemExit("SOURCE_FINGERPRINT_MISMATCH")
        source = data.decode("utf-8")
        if source.count(NEW) != 1 or OLD in source:
            raise SystemExit("LIVE_PRIORITY_PATCH_NOT_VERIFIED")
        print("LIVE_SOURCE_READONLY=VERIFIED")
        print("LIVE_SOURCE_SHA256=" + sha)


if __name__ == "__main__":
    main()
