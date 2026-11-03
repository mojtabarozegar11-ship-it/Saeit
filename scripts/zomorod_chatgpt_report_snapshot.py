#!/usr/bin/env python3
"""Guarded append-only snapshot builder for private PHP ChatGPT action reports.

Reads only the fixed Saeit GitHub issue. No financial SQLite access or web
endpoint installation. Any existing receipt edit/deletion fails closed.
"""
import argparse
import hashlib
import json
import re
import os
import sqlite3
from pathlib import Path
import stat
import sys
import tempfile
from datetime import datetime, timezone, timedelta

from enterprise_portal.github_chatgpt_reports import extract_receipt
from enterprise_portal.github_chatgpt_reports import LEGACY_MANAGEMENT_RECOVERY
from enterprise_portal.github_chatgpt_reports import PUBLIC_ISSUE_API
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError


def fetch_issue_comments(*, pages, since=None, api=PUBLIC_ISSUE_API):
    headers = {"User-Agent": "ZM-Private-ReportSnapshot/1.0", "Accept": "application/vnd.github+json"}
    token = os.environ.get("ZM_GITHUB_REPORTS_READ_TOKEN", "")
    if token:
        headers["Authorization"] = "Bearer " + token
    for page in range(1, pages + 1):
        try:
            query = {"per_page": 100, "page": page}
            if since:
                query["since"] = since
            with urlopen(Request(api + "?" + urlencode(query), headers=headers), timeout=10) as response:
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
PUBLIC_CYCLES_ARCHIVE_NAME = "chatgpt_reports_public_cycles.sqlite3"
PUBLIC_CYCLES_SOURCE = "github:mojtabarozegar11-ship-it/Saeit:issue:1514"
PUBLIC_CYCLES_API = "https://api.github.com/repos/mojtabarozegar11-ship-it/Saeit/issues/1514/comments"
_PERSIAN_NUMERALS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_PUBLIC_TITLE = re.compile(r"(?<![A-Za-z0-9])گزارش[ \t]+(01|02|04)[-–]([0-9]{4,8})(?![0-9])")


def extract_public_cycle_receipt(comment):
    """Accept only owner-published numbered cycle 01/02/04 receipts in issue 1514."""
    if not isinstance(comment, dict) or not isinstance(comment.get("user"), dict):
        return None
    if comment["user"].get("login") != "mojtabarozegar11-ship-it":
        return None
    cid, body = comment.get("id"), comment.get("body")
    if type(cid) is not int or cid <= 0 or not isinstance(body, str) or not 20 <= len(body) <= 8000:
        return None
    heading = body.splitlines()[0].translate(_PERSIAN_NUMERALS)
    matches = list(_PUBLIC_TITLE.finditer(heading[:300]))
    if len(matches) != 1:
        return None
    when = comment.get("created_at")
    if not isinstance(when, str) or len(when) > 40:
        return None
    try:
        date = datetime.fromisoformat(when.replace("Z", "+00:00"))
    except ValueError:
        return None
    if date.tzinfo is None:
        return None
    return {
        "report_code": matches[0].group(1) + "-" + matches[0].group(2),
        "occurred_at": date.astimezone(timezone.utc),
        "body": body,
        "evidence_url": (
            "https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1514"
            f"#issuecomment-{cid}"
        ),
    }


def _normalized_rows(comments, extractor=extract_receipt):
    rows, seen = [], {}
    for comment in comments:
        receipt = extractor(comment)
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
    return rows


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


def _archive_guard(target, *, archive_name=ARCHIVE_NAME):
    if target.name != archive_name or not target.is_absolute() or target.is_symlink():
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


def archive_since(target, *, source=SOURCE, archive_name=ARCHIVE_NAME):
    _archive_guard(target, archive_name=archive_name)
    if not target.exists():
        return None
    with _archive_db(target, True) as db:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        expected_source = source
        source = db.execute("SELECT value FROM metadata WHERE name='source'").fetchone()
        saved = db.execute("SELECT value FROM metadata WHERE name='last_checked_at'").fetchone()
        if version != 1 or source != (expected_source,) or not saved:
            raise ValueError("INVALID_REPORT_ARCHIVE_METADATA")
        last = datetime.fromisoformat(saved[0])
        if last.tzinfo is None or last > datetime.now(timezone.utc) + timedelta(minutes=2):
            raise ValueError("INVALID_REPORT_ARCHIVE_CLOCK")
        return (last - timedelta(days=1)).isoformat().replace("+00:00", "Z")


def archive_sync(comments, target, *, now=None, source=SOURCE, archive_name=ARCHIVE_NAME, extractor=extract_receipt):
    """Append to a private non-financial SQLite archive; reject edits to old receipts.

    GitHub 'since' checks newly created and recently edited comments. Existing
    deleted comments stay historical; no claim of independent action verification.
    """
    _archive_guard(target, archive_name=archive_name)
    rows = sorted(_normalized_rows(comments, extractor), key=lambda row: row["comment_id"])
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
            db.execute("INSERT INTO metadata VALUES ('source',?)", (source,))
        elif (db.execute("PRAGMA user_version").fetchone()[0] != 1 or
              db.execute("SELECT value FROM metadata WHERE name='source'").fetchone() != (source,)):
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
                # Only four exact owner-authored receipts may be recovered out
                # of chronological order. Existing report fields remain immutable.
                expected = LEGACY_MANAGEMENT_RECOVERY.get(item["report_code"])
                if (source != SOURCE or archive_name != ARCHIVE_NAME
                        or expected is None or expected[0] != item["comment_id"]):
                    raise ValueError("REPORT_ARCHIVE_HISTORICAL_INSERT_REJECTED")
                position = 1 + db.execute(
                    "SELECT COUNT(*) FROM reports WHERE comment_id < ?",
                    (item["comment_id"],)
                ).fetchone()[0]
                # Shift ordering keys only, in reverse to avoid collisions.
                # Do not edit existing report text, dates, IDs, or evidence.
                for (seq,) in db.execute(
                    "SELECT seq FROM reports WHERE seq >= ? ORDER BY seq DESC",
                    (position,)
                ).fetchall():
                    db.execute("UPDATE reports SET seq=? WHERE seq=?", (seq + 1, seq))
                db.execute(
                    "INSERT INTO reports(seq,report_code,comment_id,occurred_at,body,evidence_url) VALUES (?,?,?,?,?,?)",
                    (position,) + record
                )
            else:
                db.execute("INSERT INTO reports(report_code,comment_id,occurred_at,body,evidence_url) VALUES (?,?,?,?,?)", record)
            by_code[item["report_code"]] = record
            last_id = max(last_id, item["comment_id"])
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
            # Recover only pinned real receipts excluded by an old title
            # parser. Existing rows must match exactly and in original order.
            allowed = {"05-0010": 6566708686}
            allowed.update({code: spec[0] for code, spec in LEGACY_MANAGEMENT_RECOVERY.items()})
            prior_codes = {row.get("report_code") for row in prior}
            recovered = [
                row for row in updated
                if row.get("report_code") not in prior_codes
                and row.get("comment_id") == allowed.get(row.get("report_code"))
                and row.get("evidence_url") ==
                "https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1725"
                + "#issuecomment-" + str(row.get("comment_id"))
            ]
            remaining = [row for row in updated if row not in recovered]
            if not recovered or prior != remaining[:len(prior)]:
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
            public_archive = args.output.with_name(PUBLIC_CYCLES_ARCHIVE_NAME)
            public_since = archive_since(
                public_archive, source=PUBLIC_CYCLES_SOURCE,
                archive_name=PUBLIC_CYCLES_ARCHIVE_NAME
            )
            # This established public GitHub issue contains >600 comments, so
            # the initial import needs seven pages; incremental runs use 'since'.
            public_comments = list(fetch_issue_comments(
                pages=max(args.pages, 10) if public_since is None else args.pages,
                since=public_since, api=PUBLIC_CYCLES_API
            ))
            public_total, public_added, _ = archive_sync(
                public_comments, public_archive, source=PUBLIC_CYCLES_SOURCE,
                archive_name=PUBLIC_CYCLES_ARCHIVE_NAME,
                extractor=extract_public_cycle_receipt
            )
        else:
            snapshot, payload = build_snapshot(comments)
            total, added = snapshot["count"], 0
            public_total, public_added = 0, 0
            result = "PREVIEW_ONLY"
        print("ZM_CHATGPT_SNAPSHOT=" + result)
        print("VALID_NUMBERED_REPORTS=" + str(total))
        print("IMMUTABLE_ARCHIVE_NEW_ROWS=" + str(added))
        print("PUBLIC_CYCLES_ARCHIVE_REPORTS=" + str(public_total))
        print("PUBLIC_CYCLES_ARCHIVE_NEW_ROWS=" + str(public_added))
        print("FINANCIAL_DB_TOUCHED=no")
        return 0
    except (ValueError, TypeError, OSError, sqlite3.Error, json.JSONDecodeError) as e:
        # No private report text or filesystem contents in logs.
        print("ZM_CHATGPT_SNAPSHOT=BLOCKED", file=sys.stderr)
        print("ERROR_CLASS=" + type(e).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
