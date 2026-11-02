#!/usr/bin/env python3
"""Read-only evidence check for ZM action-index scheduled output.

Never writes to the SQLite database or crontab. A matching timestamp
establishes a schedule-aligned build, not the identity of its executor.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo


def check_build_time(built: datetime, modified: datetime) -> None:
    if built.tzinfo is None or modified.tzinfo is None:
        raise ValueError("TIMESTAMP_MUST_HAVE_TIMEZONE")
    local = built.astimezone(ZoneInfo("Asia/Tehran"))
    if local.minute != 55 or local.second > 20:
        raise ValueError("BUILD_NOT_ALIGNED_WITH_SCHEDULE")
    if abs((modified - built).total_seconds()) > 15:
        raise ValueError("FILE_MTIME_NOT_ALIGNED")
    threshold = datetime(2026, 11, 2, 9, 25, tzinfo=timezone.utc)
    if built < threshold:
        raise ValueError("BUILD_BEFORE_FIRST_EXPECTED_TICK")


def self_test() -> None:
    b = datetime(2026, 11, 2, 22, 25, 2, tzinfo=timezone.utc)
    check_build_time(b, b)
    for bad in (b.replace(minute=26), b.replace(year=2025)):
        try:
            check_build_time(bad, bad)
        except ValueError:
            pass
        else:
            raise AssertionError("Bad schedule accepted")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    args = parser.parse_args()
    self_test()
    p = args.index
    if not p.is_file() or p.is_symlink():
        raise SystemExit("UNSAFE_INDEX_FILE")
    st = p.stat()
    modified = datetime.fromtimestamp(st.st_mtime, timezone.utc)
    db = sqlite3.connect("file:" + str(p) + "?mode=ro", uri=True)
    try:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise SystemExit("INDEX_INTEGRITY_FAILED")
        meta = dict(db.execute("SELECT name,value FROM metadata"))
        if meta.get("source") != "github:mojtabarozegar11-ship-it/Saeit:issue:1725":
            raise SystemExit("INDEX_SOURCE_MISMATCH")
        built = datetime.fromisoformat(meta["built_at"])
        check_build_time(built, modified)
        actions = db.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
        reports = int(meta["report_count"])
    finally:
        db.close()
    print("INDEX_QUICK_CHECK=OK")
    print("SCHEDULE_ALIGNED_INDEX_BUILD=YES")
    print("BUILD_UTC=" + built.astimezone(timezone.utc).isoformat())
    print("REPORTS_INDEXED=" + str(reports))
    print("ACTIONS_INDEXED=" + str(actions))
    print("FIRST_TICK_PROVEN=NO")
    print("EXECUTOR_IDENTITY_PROVEN=NO")
    print("DATABASE_WRITES=NONE")


if __name__ == "__main__":
    main()
