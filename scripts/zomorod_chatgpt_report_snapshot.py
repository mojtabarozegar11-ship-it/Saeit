#!/usr/bin/env python3
"""Guarded append-only snapshot builder for private PHP ChatGPT action reports.

Reads only the fixed Saeit GitHub issue. No financial SQLite access or web
endpoint installation. Any existing receipt edit/deletion fails closed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from datetime import datetime, timezone

from enterprise_portal.github_chatgpt_reports import extract_receipt
from enterprise_portal.management.commands.sync_chatgpt_action_reports import fetch_issue_comments

SOURCE = "github:mojtabarozegar11-ship-it/Saeit:issue:1725"
FILENAME = "chatgpt_reports_snapshot.json"


def build_snapshot(comments):
    rows = []
    seen = {}
    for comment in comments:
        receipt = extract_receipt(comment)
        if receipt is None:
            continue
        row = {
            "report_code": receipt["report_code"],
            "comment_id": comment["id"],
            "occurred_at": receipt["occurred_at"].isoformat(),
            "body": receipt["body"],
            "evidence_url": receipt["evidence_url"],
        }
        prev = seen.get(row["report_code"])
        if prev is not None:
            if prev != row:
                raise ValueError("CONFLICTING_REPORT_CODE_OR_TEXT")
            continue
        seen[row["report_code"]] = row
        rows.append(row)
    if len(rows) > 100:
        raise ValueError("REPORT_VIEW_CAP_REACHED_NO_TRUNCATION")
    data = {"version": 1, "source": SOURCE, "count": len(rows), "items": rows}
    payload = (json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(payload) > 2_000_000:
        raise ValueError("SNAPSHOT_SIZE_LIMIT")
    return data, payload


def install(snapshot, payload, target):
    if target.name != FILENAME or not target.is_absolute() or target.is_symlink():
        raise ValueError("INVALID_TARGET")
    parent = target.parent
    if not parent.is_dir() or parent.is_symlink() or (parent.stat().st_mode & 0o077):
        raise ValueError("TARGET_DIRECTORY_MUST_BE_PRIVATE")
    if target.exists():
        st = target.lstat()
        if not stat.S_ISREG(st.st_mode) or (st.st_mode & 0o077) or st.st_size > 2_000_000:
            raise ValueError("EXISTING_SNAPSHOT_UNSAFE")
        old = json.loads(target.read_text(encoding="utf-8"))
        if old.get("version") != 1 or old.get("source") != SOURCE or not isinstance(old.get("items"), list):
            raise ValueError("EXISTING_SNAPSHOT_INVALID")
        prior = old["items"]
        updated = snapshot["items"]
        if len(prior) > len(updated) or prior != updated[:len(prior)]:
            raise ValueError("NON_APPEND_ONLY_SNAPSHOT_CHANGE")
        if prior == updated:
            return "UNCHANGED"
    fd, temp_name = tempfile.mkstemp(prefix=".zm-text-", suffix=".tmp", dir=parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        if target.is_symlink():
            raise ValueError("TARGET_CHANGED_TO_SYMLINK")
        if target.exists():
            # Reproducible cache: atomic replacement after strict append-only proof.
            os.replace(temp_name, target)
        else:
            os.link(temp_name, target)
        return "UPDATED" if snapshot["count"] else "INSTALLED_EMPTY"
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, help="Local GitHub comments JSON; offline tests")
    parser.add_argument("--pages", type=int, default=5)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if not (1 <= args.pages <= 10):
            raise ValueError("PAGES_OUT_OF_RANGE")
        if args.install and (
            os.environ.get("ZM_BUSINESS_REPORT_SNAPSHOT_INSTALL") != "1"
            or args.output is None
        ):
            raise ValueError("SNAPSHOT_INSTALL_GATE_BLOCKED")
        if args.fixture:
            if args.fixture.stat().st_size > 2_000_000:
                raise ValueError("FIXTURE_TOO_LARGE")
            comments = json.loads(args.fixture.read_text(encoding="utf-8"))
            if not isinstance(comments, list):
                raise ValueError("FIXTURE_MUST_BE_LIST")
        else:
            comments = list(fetch_issue_comments(pages=args.pages))
        snapshot, payload = build_snapshot(comments)
        result = install(snapshot, payload, args.output) if args.install else "PREVIEW_ONLY"
        print("ZM_CHATGPT_SNAPSHOT=" + result)
        print("VALID_NUMBERED_REPORTS=" + str(snapshot["count"]))
        print("FINANCIAL_DB_TOUCHED=no")
        return 0
    except (ValueError, TypeError, OSError, json.JSONDecodeError) as e:
        # No private report text or filesystem contents in logs.
        print("ZM_CHATGPT_SNAPSHOT=BLOCKED", file=sys.stderr)
        print("ERROR_CLASS=" + type(e).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
