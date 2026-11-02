#!/usr/bin/env python3
"""Guarded append-only snapshot builder for private PHP ChatGPT action reports.

Reads only the fixed Saeit GitHub issue. No financial SQLite access or web
endpoint installation. Any existing receipt edit/deletion fails closed.
"""
import argparse
import hashlib
import json
import os
import sqlite3
from pathlib import Path
import stat
import sys
import tempfile
from datetime import datetime, timezone, timedelta

from enterprise_portal.github_chatgpt_reports import extract_receipt
from enterprise_portal.github_chatgpt_reports import PUBLIC_ISSUE_API
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError


def fetch_issue_comments(*, pages, since=None):
    headers = {"User-Agent": "ZM-Private-ReportSnapshot/1.0", "Accept": "application/vnd.github+json"}
    token = os.environ.get("ZM_GITHUB_REPORTS_READ_TOKEN", "")
    if token:
        headers["Authorization"] = "Bearer " + token
    for page in range(1, pages + 1):
        try:
            query = {"per_page": 100, "page": page}
            if since:
                query["since"] = since
            with urlopen(Request(PUBLIC_ISSUE_API + "?" + urlencode(query), headers=headers), timeout=10) as response:
                data = response.read(2_000_001)
        except (HTTPError, URLError, TimeoutError, OSError) as e:
            raise ValueError("GITHUB_REPORT_SOURCE_UNAVAILABLE") from e
        if len(data) > 2_000_000:
            raise ValueError("SOURCE_PAGE_TOO_LARGE")
        items = json.loads(data)
        if not isinstance(items, list) or len(items) > 100:
            raise ValueError("SOURCE_PAGE_INVALID")
        yield from items
        if len(items) < 100:
            return
    raise ValueError("SOURCE_PAGINATION_UNFINISHED")

SOURCE = "github:mojtabarozegar11-ship-it/Saeit:issue:1725"
FILENAME = "chatgpt_reports_snapshot.json"
ARCHIVE_NAME = "chatgpt_reports_archive.sqlite3"


def _normalized_rows(comments):
    rows, seen = [], {}
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
        prior = seen.get(row["report_code"])
        if prior is not None:
            if prior != row:
                raise ValueError("CONFLICTING_REPORT_CODE_OR_TEXT")
            continue
        seen[row["report_code"]] = row
        rows.append(row)
    return sorted(rows, key=lambda x: x["comment_id"])


def _snapshot_from_rows(rows):
    if len(rows) > 100:
        raise ValueError("REPORT_VIEW_CAP_REACHED_NO_TRUNCATION")
    data = {"version": 1, "source": SOURCE, "count": len(rows), "items": rows}
    payload = (json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(payload) > 2_000_000:
        raise ValueError("SNAPSHOT_SIZE_LIMIT")
    return data, payload


def build_snapshot(comments):
    return _snapshot_from_rows(_normalized_rows(comments))


def _archive_guard(target):
    if target.name != ARCHIVE_NAME or not target.is_absolute() or target.is_symlink():
        raise ValueError("INVALID_REPORT_ARCHIVE_TARGET")
    parent = target.parent
    if not parent.is_dir() or parent.is_symlink() or (parent.stat().st_mode & 0o077):
        raise ValueError("REPORT_ARCHIVE_DIRECTORY_MUST_BE_PRIVATE")
    if target.exists():
        meta = target.lstat()
        if not stat.S_ISREG(meta.st_mode) or (meta.st_mode & 0o077) or meta.st_size > 500_000_000:
            raise ValueError("EXISTING_REPORT_ARCHIVE_UNSAFE")


def _archive_db(target, readonly):
    return sqlite3.connect(target.as_uri() + ("?mode=ro" if readonly else "?mode=rw"),
                           uri=True, timeout=12)


def archive_since(target):
    _archive_guard(target)
    if not target.exists():
        return None
    with _archive_db(target, True) as db:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        source = db.execute("SELECT value FROM metadata WHERE name='source'").fetchone()
        saved = db.execute("SELECT value FROM metadata WHERE name='last_checked_at'").fetchone()
        if version != 1 or source != (SOURCE,) or not saved:
            raise ValueError("INVALID_REPORT_ARCHIVE_METADATA")
        last = datetime.fromisoformat(saved[0])
        if last.tzinfo is None or last > datetime.now(timezone.utc) + timedelta(minutes=2):
            raise ValueError("INVALID_REPORT_ARCHIVE_CLOCK")
        return (last - timedelta(days=1)).isoformat().replace("+00:00", "Z")


def archive_sync(comments, target, *, now=None):
    """Append to a private non-financial SQLite archive; reject edits to old receipts.

    GitHub 'since' checks newly created and recently edited comments. Existing
    deleted comments stay historical; no claim of independent action verification.
    """
    _archive_guard(target)
    rows = _normalized_rows(comments)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("ARCHIVE_TIMEZONE_REQUIRED")
    is_new = not target.exists()
    temp = None
    if is_new:
        fd, filename = tempfile.mkstemp(prefix=".zm-reports-", dir=target.parent)
        os.close(fd)
        temp = Path(filename)
        db = sqlite3.connect(str(temp), timeout=12)
    else:
        db = _archive_db(target, False)
    try:
        db.execute("PRAGMA busy_timeout=12000")
        db.execute("BEGIN IMMEDIATE")
        if is_new:
            db.execute("CREATE TABLE reports (seq INTEGER PRIMARY KEY, report_code TEXT NOT NULL UNIQUE, comment_id INTEGER NOT NULL UNIQUE, occurred_at TEXT NOT NULL, body TEXT NOT NULL, evidence_url TEXT NOT NULL)")
            db.execute("CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("PRAGMA user_version=1")
            db.execute("INSERT INTO metadata VALUES ('source',?)", (SOURCE,))
        elif (db.execute("PRAGMA user_version").fetchone()[0] != 1 or
              db.execute("SELECT value FROM metadata WHERE name='source'").fetchone() != (SOURCE,)):
            raise ValueError("INVALID_REPORT_ARCHIVE_SOURCE")
        old = db.execute("SELECT report_code,comment_id,occurred_at,body,evidence_url FROM reports ORDER BY seq").fetchall()
        by_code = {r[0]: r for r in old}
        last_id = max((r[1] for r in old), default=0)
        added = 0
        for item in rows:
            record = tuple(item[k] for k in ("report_code","comment_id","occurred_at","body","evidence_url"))
            prior = by_code.get(item["report_code"])
            if prior is not None:
                if prior != record:
                    raise ValueError("IMMUTABLE_REPORT_ARCHIVE_CONFLICT")
                continue
            if item["comment_id"] <= last_id:
                raise ValueError("REPORT_ARCHIVE_HISTORICAL_INSERT_REJECTED")
            db.execute("INSERT INTO reports(report_code,comment_id,occurred_at,body,evidence_url) VALUES (?,?,?,?,?)", record)
            by_code[item["report_code"]] = record
            last_id = item["comment_id"]
            added += 1
        if db.execute("SELECT COUNT(*) FROM reports").fetchone()[0] > 100000:
            raise ValueError("REPORT_ARCHIVE_MAX_RECORDS")
        db.execute("INSERT OR REPLACE INTO metadata VALUES ('last_checked_at',?)", (now.isoformat(),))
        db.commit()
        first = db.execute("SELECT report_code,comment_id,occurred_at,body,evidence_url FROM reports ORDER BY seq LIMIT 100").fetchall()
        total = db.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    except BaseException:
        db.rollback()
        if temp is not None:
            temp.unlink(missing_ok=True)
        raise
    finally:
        db.close()
    if temp is not None:
        try:
            os.link(temp, target, follow_symlinks=False)
        finally:
            temp.unlink(missing_ok=True)
    fields = ("report_code","comment_id","occurred_at","body","evidence_url")
    return total, added, [dict(zip(fields, r)) for r in first]


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
        if len(prior) > len(updated):
            raise ValueError("NON_APPEND_ONLY_SNAPSHOT_CHANGE")
        if prior != updated[:len(prior)]:
            # Only historical recovery permitted: the precise real 05-0010
            # comment was previously excluded by an over-strict title parser.
            # A later 05-0011 may already be in the live snapshot, so a strict
            # prefix check alone would reject recovery. No older row may change.
            recovered = [
                row for row in updated
                if row.get("report_code") == "05-0010"
                and row.get("comment_id") == 6566708686
                and row.get("evidence_url") ==
                "https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1725#issuecomment-6566708686"
            ]
            remaining = [row for row in updated if row not in recovered]
            if (len(recovered) != 1
                    or any(row.get("report_code") == "05-0010" for row in prior)
                    or prior != remaining[:len(prior)]):
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
        since = None
        archive_target = args.output.with_name(ARCHIVE_NAME) if args.install else None
        if args.install and not args.fixture:
            since = archive_since(archive_target)
        if args.fixture:
            if args.fixture.stat().st_size > 2_000_000:
                raise ValueError("FIXTURE_TOO_LARGE")
            comments = json.loads(args.fixture.read_text(encoding="utf-8"))
            if not isinstance(comments, list):
                raise ValueError("FIXTURE_MUST_BE_LIST")
        else:
            comments = list(fetch_issue_comments(pages=args.pages, since=since))
        if args.install:
            total, added, first_hundred = archive_sync(comments, archive_target)
            snapshot, payload = _snapshot_from_rows(first_hundred)
            result = install(snapshot, payload, args.output)
        else:
            snapshot, payload = build_snapshot(comments)
            total, added = snapshot["count"], 0
            result = "PREVIEW_ONLY"
        print("ZM_CHATGPT_SNAPSHOT=" + result)
        print("VALID_NUMBERED_REPORTS=" + str(total))
        print("IMMUTABLE_ARCHIVE_NEW_ROWS=" + str(added))
        print("FINANCIAL_DB_TOUCHED=no")
        return 0
    except (ValueError, TypeError, OSError, sqlite3.Error, json.JSONDecodeError) as e:
        # No private report text or filesystem contents in logs.
        print("ZM_CHATGPT_SNAPSHOT=BLOCKED", file=sys.stderr)
        print("ERROR_CLASS=" + type(e).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
