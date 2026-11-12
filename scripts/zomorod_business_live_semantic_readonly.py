#!/usr/bin/env python3
"""Fail-closed, non-mutating cPanel source compatibility and SQLite metadata audit.

Read only from production private files. Never print PHP source, credentials,
user records, accounting amounts or project titles.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
from urllib.parse import quote

ROOT = Path("/home/zomorod2/.private/zomorod-business")
SOURCE = ROOT / "app.php"
DOSSIER = ROOT / "genetics-center.php"
DATABASE = ROOT / "management.sqlite3"
PROJECT_KEY = "ZM-AGRC-GEN-1405-001"

def stop(label: str, code: int = 3) -> None:
    print("LIVE_SEMANTIC_AUDIT=" + label)
    raise SystemExit(code)

if len(sys.argv) != 2 or not re.fullmatch(r"[0-9a-f]{64}", sys.argv[1]):
    stop("BAD_EXPECTED_HASH", 2)
if os.geteuid() == 0 or os.geteuid() != ROOT.stat().st_uid:
    stop("INCORRECT_PRIVILEGE")
for candidate in (ROOT, SOURCE, DATABASE):
    if candidate.is_symlink() or not candidate.exists():
        stop("MISSING_OR_SYMLINK")
if not ROOT.is_dir():
    stop("PRIVATE_DIRECTORY_INVALID")
for candidate in (SOURCE, DATABASE):
    meta = candidate.stat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid():
        stop("UNTRUSTED_FILE")
source_bytes = SOURCE.read_bytes()
if len(source_bytes) > 1_000_000:
    stop("APP_SOURCE_TOO_LARGE")
digest = hashlib.sha256(source_bytes).hexdigest()
print("LIVE_SEMANTIC_APP_SHA256=" + digest)
if digest != sys.argv[1]:
    stop("SOURCE_CHANGED_SINCE_BASELINE", 4)
try:
    source = source_bytes.decode("utf-8")
except UnicodeDecodeError:
    stop("APP_NON_UTF8", 4)

# Restrict outputs to fixed marker names and integer counts, never PHP snippets.
anchors = {
    "NAV_PROJECTS": "'projects'=>'پروژه‌ها','mojplaywin'",
    "POST_PROJECT": "} elseif($action==='project'){",
    "GET_PROJECTS": "} elseif($page==='projects'){",
    "DASHBOARD_BOUNDARY": "} elseif($page==='mojplaywin'){",
    "PROJECT_INSERT": "INSERT INTO projects(title,owner,state,budget) VALUES(?,?,?,?)",
    "CSRF": "function verifyCsrf():",
    "ROLE": "function role():",
    "AUDIT_EVENT": "function audit(PDO $db,",
}
counts = {key: source.count(fragment) for key, fragment in anchors.items()}
for key, count in counts.items():
    print("LIVE_ANCHOR_" + key + "_COUNT=" + str(count))
print("LIVE_EXISTING_GENETICS_ROUTE=" + str("$page==='genetics_center'" in source).lower())
print("LIVE_EXISTING_GENETICS_POST=" + str("$action==='genetics_project_register'" in source).lower())
print("LIVE_EXISTING_GENETICS_NAV=" + str("'genetics_center'=>'" in source).lower())
print("LIVE_SEMANTIC_ANCHORS_UNIQUE=" + str(all(v == 1 for v in counts.values())).lower())
print("LIVE_DOSSIER_PRESENT=" + str(DOSSIER.is_file() and not DOSSIER.is_symlink()).lower())

# Query immutable read-only SQLite metadata; no account data, no write transaction.
try:
    db_uri = "file:" + quote(str(DATABASE), safe="/") + "?mode=ro&immutable=1"
    connection = sqlite3.connect(db_uri, uri=True, timeout=4)
    connection.execute("PRAGMA query_only=ON")
    quick = connection.execute("PRAGMA quick_check(1)").fetchone()
    print("LIVE_SQLITE_IMMUTABLE_QUICK_CHECK=" + ("ok" if quick and quick[0] == "ok" else "not_ok"))
    tables = {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    print("LIVE_PROJECTS_TABLE_PRESENT=" + str("projects" in tables).lower())
    if "projects" in tables:
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(projects)")}
        required = {"id", "title", "owner", "state", "budget"}
        compatible = required <= columns
        print("LIVE_PROJECTS_SCHEMA_COMPATIBLE=" + str(compatible).lower())
        if compatible:
            count = connection.execute(
                "SELECT COUNT(*) FROM projects WHERE trim(title) LIKE ?",
                (PROJECT_KEY + "%",),
            ).fetchone()[0]
            print("LIVE_GENETICS_ID_MATCH_COUNT=" + str(min(int(count), 2)) + ("_OR_MORE" if count > 2 else ""))
    connection.close()
except sqlite3.Error as exc:
    print("LIVE_SQLITE_METADATA_READ_ERROR=" + type(exc).__name__)
    stop("DB_READ_FAILED", 6)

wal = DATABASE.with_name(DATABASE.name + "-wal")
print("LIVE_SQLITE_WAL_PRESENT=" + str(wal.exists() or wal.is_symlink()).lower())
print("LIVE_DB_READ_MODE=IMMUTABLE_NO_WRITES")
print("LIVE_METADATA_FRESHNESS_REQUIRES_WAL_RECONCILIATION=" + str(wal.exists() or wal.is_symlink()).lower())
print("LIVE_APP_PRIVATE_SOURCE_EXPORTED=no")
print("LIVE_FINANCIAL_RECORDS_EXPORTED=no")
print("LIVE_SOURCE_OR_DATABASE_MODIFIED=no")
print("LIVE_SEMANTIC_AUDIT=PASS_READ_ONLY")
