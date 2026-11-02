#!/usr/bin/env python3
"""Private, rebuildable action index for ChatGPT cycle 05.

The immutable GitHub report archive remains authoritative for provenance.
This script never opens or changes financial SQLite. The action index contains
claims only; no action is marked independently verified by this importer.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile

SOURCE = "github:mojtabarozegar11-ship-it/Saeit:issue:1725"
ARCHIVE_NAME = "chatgpt_reports_archive.sqlite3"
INDEX_NAME = "chatgpt_actions_index.sqlite3"
BLOCK = re.compile(r"(?:^|\n)ZM_ACTIONS_V1_START\r?\n([^\x00]{1,7800}?)\r?\nZM_ACTIONS_V1_END(?=\r?\n|$)")
ACTION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{7,79}\Z")
REPORT = re.compile(r"05-[0-9]{4,8}\Z")
EVIDENCE = re.compile(
    r"https://github\.com/mojtabarozegar11-ship-it/Saeit/"
    r"(?:commit/[a-f0-9]{40}|actions/runs/[1-9][0-9]*|pull/[1-9][0-9]*"
    r"|issues/[1-9][0-9]*(?:#issuecomment-[1-9][0-9]*)?)\Z"
)
STATUSES = {"completed", "partial", "blocked", "not_started"}
CREATE_SQL = """
CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE actions (
    seq INTEGER PRIMARY KEY,
    action_id TEXT NOT NULL UNIQUE,
    report_code TEXT NOT NULL,
    comment_id INTEGER NOT NULL,
    occurred_at TEXT NOT NULL,
    title_fa TEXT NOT NULL,
    action_status TEXT NOT NULL,
    impact_fa TEXT NOT NULL,
    evidence_url TEXT NOT NULL,
    receipt_sha256 TEXT NOT NULL
);
CREATE INDEX action_by_report ON actions(report_code,seq);
CREATE TABLE rejected (
    report_code TEXT PRIMARY KEY,
    reason TEXT NOT NULL
);
PRAGMA user_version=1;
"""


def guard_private(path: Path, basename: str, *, must_exist=False):
    if not path.is_absolute() or path.name != basename or path.is_symlink():
        raise ValueError("UNSAFE_ACTION_PATH")
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink() or parent.stat().st_mode & 0o077:
        raise ValueError("ACTION_PARENT_NOT_PRIVATE")
    if must_exist and not path.exists():
        raise ValueError("MISSING_ACTION_SOURCE")
    if path.exists():
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
                or not 0 < info.st_size <= 500_000_000):
            raise ValueError("UNSAFE_ACTION_FILE")


def _unique_json_object(pairs):
    """Reject ambiguous repeated JSON keys, including nested action fields."""
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("DUPLICATE_ACTION_JSON_KEY")
        obj[key] = value
    return obj


def parse_block(body: str, report_code: str):
    """Return (status, rows), never interpret natural-language prose as actions."""
    if "ZM_ACTIONS_V1_START" not in body:
        return "missing", []
    # An extra unbalanced marker must not be silently ignored.
    if body.count("ZM_ACTIONS_V1_START") != 1 or body.count("ZM_ACTIONS_V1_END") != 1:
        return "invalid_contract", []
    matches = BLOCK.findall(body)
    if len(matches) != 1:
        return "invalid_contract", []
    try:
        data = json.loads(matches[0], object_pairs_hook=_unique_json_object)
    except (ValueError, TypeError):
        return "invalid_contract", []
    if (not isinstance(data, dict) or type(data.get("version")) is not int
            or data["version"] != 1 or data.get("report_code") != report_code
            or not isinstance(data.get("actions"), list) or len(data["actions"]) > 20):
        return "invalid_contract", []
    actions, seen = [], set()
    for item in data["actions"]:
        if not isinstance(item, dict):
            return "invalid_contract", []
        aid, title = item.get("id"), item.get("title_fa")
        state, evidence = item.get("status"), item.get("evidence_url")
        impact = item.get("impact_fa", "")
        # Historical receipts remain immutable. For reports 05-0018 onward,
        # the action ID must belong to this exact numbered report, not a date.
        # Do not reclassify old, already indexed receipts during this upgrade.
        numbered_id = (int(report_code.split("-")[1]) < 18 or (
            isinstance(aid, str) and re.fullmatch(
                re.escape("ZM" + report_code) + r"-A(?:0[1-9]|1[0-9]|20)", aid
            ) is not None
        ))
        if (not isinstance(aid, str) or ACTION_ID.fullmatch(aid) is None or not numbered_id or aid in seen
                or not isinstance(title, str) or not 8 <= len(title.encode("utf-8")) <= 350
                or re.search(r"[\u0600-\u06ff]", title) is None
                or not isinstance(impact, str) or not 1 <= len(impact.encode("utf-8")) <= 500
                or re.search(r"[\u0600-\u06ff]", impact) is None
                or not isinstance(state, str) or state not in STATUSES
                or not isinstance(evidence, str)
                or len(evidence.encode("utf-8")) > 350
                or (evidence and EVIDENCE.fullmatch(evidence) is None)
                or (state == "completed" and not evidence)
                or (state != "completed" and evidence != "")):
            return "invalid_contract", []
        seen.add(aid)
        actions.append((aid, title, state, impact, evidence))
    return "valid", actions


def read_archive(source: Path):
    guard_private(source, ARCHIVE_NAME, must_exist=True)
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=5) as db:
        if (db.execute("PRAGMA user_version").fetchone()[0] != 1
                or db.execute("SELECT value FROM metadata WHERE name='source'").fetchone() != (SOURCE,)):
            raise ValueError("SOURCE_IDENTITY_MISMATCH")
        rows = db.execute(
            "SELECT report_code,comment_id,occurred_at,body,evidence_url "
            "FROM reports WHERE substr(report_code,1,2)='05' ORDER BY seq"
        ).fetchall()
    return rows


def compile_index(rows):
    """Fail closed on source corruption; quarantine malformed/replayed blocks."""
    actions, rejected, seen = [], [], set()
    for code, cid, when, body, report_url in rows:
        if (not isinstance(code, str) or REPORT.fullmatch(code) is None
                or type(cid) is not int or cid < 1
                or not isinstance(body, str) or not 20 <= len(body.encode("utf-8")) <= 32000
                or report_url !=
                f"https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1725#issuecomment-{cid}"):
            raise ValueError("INVALID_SOURCE_REPORT")
        result, entries = parse_block(body, code)
        if result == "missing":
            continue
        if result != "valid":
            rejected.append((code, result))
            continue
        if any(item[0] in seen for item in entries):
            # A report with any reused action identifier is rejected as a unit.
            rejected.append((code, "replayed_action_id"))
            continue
        fingerprint = hashlib.sha256(body.encode("utf-8")).hexdigest()
        for action_id, title, state, impact, url in entries:
            seen.add(action_id)
            actions.append((len(actions) + 1, action_id, code, cid, when,
                            title, state, impact, url, fingerprint))
    return actions, rejected


def archive_fingerprint(rows):
    """Bind every archived report, including reports with no structured actions."""
    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def verify_old_index(target: Path, new_actions, new_rejected, rows):
    if not target.exists():
        return
    guard_private(target, INDEX_NAME, must_exist=True)
    with sqlite3.connect(target.as_uri() + "?mode=ro", uri=True) as db:
        if (db.execute("PRAGMA user_version").fetchone()[0] != 1
                or db.execute("SELECT value FROM metadata WHERE name='source'").fetchone() != (SOURCE,)):
            raise ValueError("OLD_INDEX_IDENTITY_MISMATCH")
        old_actions = db.execute("SELECT seq,action_id,report_code,comment_id,"
                                 "occurred_at,title_fa,action_status,impact_fa,evidence_url,"
                                 "receipt_sha256 FROM actions ORDER BY seq").fetchall()
        old_rejected = db.execute("SELECT report_code,reason FROM rejected ORDER BY report_code").fetchall()
        previous = dict(db.execute("SELECT name,value FROM metadata").fetchall())
    # Older indexes did not record the complete report fingerprint. Keep their
    # action/rejection immutability checks and establish the new baseline once.
    try:
        old_count = int(previous["report_count"])
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError("OLD_INDEX_REPORT_COUNT_INVALID") from exc
    if old_count < 0 or old_count > len(rows):
        raise ValueError("IMMUTABLE_REPORT_HISTORY_CHANGED")
    old_fingerprint = previous.get("archive_prefix_sha256")
    if old_fingerprint is not None and (
            not re.fullmatch(r"[a-f0-9]{64}", old_fingerprint)
            or archive_fingerprint(rows[:old_count]) != old_fingerprint):
        raise ValueError("IMMUTABLE_REPORT_HISTORY_CHANGED")
    if new_actions[:len(old_actions)] != old_actions:
        raise ValueError("IMMUTABLE_ACTION_HISTORY_CHANGED")
    if not set(old_rejected).issubset(set(new_rejected)):
        raise ValueError("IMMUTABLE_REJECTIONS_CHANGED")


def rebuild(source: Path, target: Path, *, now=None):
    guard_private(source, ARCHIVE_NAME, must_exist=True)
    guard_private(target, INDEX_NAME)
    if source.parent != target.parent or source == target:
        raise ValueError("INDEX_SOURCE_DIRECTORY_MISMATCH")
    lock = source.parent / ".chatgpt-actions-index.lock"
    if lock.is_symlink():
        raise ValueError("UNSAFE_ACTION_LOCK")
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        if os.fstat(fd).st_mode & 0o077:
            raise ValueError("ACTION_LOCK_PERMISSIONS")
        fcntl.flock(fd, fcntl.LOCK_EX)
        rows = read_archive(source)
        actions, rejected = compile_index(rows)
        verify_old_index(target, actions, rejected, rows)
        timestamp = now or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            raise ValueError("NAIVE_INDEX_TIMESTAMP")
        tmp_fd, tmp_name = tempfile.mkstemp(prefix=".zm-actions-", dir=source.parent)
        os.close(tmp_fd)
        tmp_path = Path(tmp_name)
        try:
            with sqlite3.connect(tmp_path) as db:
                db.executescript(CREATE_SQL)
                db.executemany("INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?,?)", actions)
                db.executemany("INSERT INTO rejected VALUES (?,?)", rejected)
                db.executemany("INSERT INTO metadata VALUES (?,?)", [
                    ("source", SOURCE), ("built_at", timestamp.isoformat()),
                    ("report_count", str(len(rows))),
                    ("archive_prefix_sha256", archive_fingerprint(rows)),
                    ("verification", "not_checked"),
                ])
                db.commit()
                if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise ValueError("INDEX_INTEGRITY_FAILURE")
            os.chmod(tmp_path, 0o600)
            guard_private(tmp_path, tmp_path.name, must_exist=True)
            os.replace(tmp_path, target)
        finally:
            tmp_path.unlink(missing_ok=True)
        return len(actions), len(rejected), len(rows)
    finally:
        os.close(fd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    count, rejected, reports = rebuild(args.source, args.output)
    print("ACTION_INDEX=updated")
    print(f"NUMBERED_REPORTS={reports}")
    print(f"UNIQUE_REPORTED_ACTIONS={count}")
    print(f"INVALID_OR_REPLAYED_REPORTS={rejected}")
    print("INDEPENDENTLY_VERIFIED_ACTIONS=0")
    print("FINANCIAL_DB_TOUCHED=no")


if __name__ == "__main__":
    main()
