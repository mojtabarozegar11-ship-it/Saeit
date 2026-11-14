#!/usr/bin/env python3
"""C17: bounded live PHP storage provenance with zero customer-data access.

Only first-party owned PHP sources (direct children of ask-master) and SQLite
metadata in owner-controlled directories are read. Never print source, paths,
secrets, filenames, table names, customer identifiers or field values. Never
execute PHP, change permissions, create SQLite WAL, or send web POST requests.
"""
from __future__ import annotations
from pathlib import Path
from urllib.parse import quote
import os
import pwd
import re
import sqlite3
import stat

HOME = Path.home()
FORM = HOME / "public_html" / "ask-master"
PRIVATE_ROOTS = (
    HOME / ".private", HOME / "private", HOME / "data",
    HOME / "storage", HOME / "app_data", FORM,
)
SAFE_DIR_NAMES = frozenset({
    "ask-master", "forms", "company", "crm", "db", "database",
    "storage", "data", "private", "inquiries", "leads",
})
SUFFIXES = frozenset({".sqlite", ".sqlite3", ".db"})
MAX_SOURCE_FILES = 16
MAX_SOURCE_BYTES = 400_000
MAX_DIR_CHILDREN = 256
MAX_DIRS = 70
MAX_FILES = 65
MAX_DB_SIZE = 150_000_000
SQL_NAMES = re.compile(
    rb"\b(?:CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?|"
    rb"INSERT\s+INTO\s+|UPDATE\s+|FROM\s+|JOIN\s+)"
    rb"[\"\x60]?([A-Za-z_][A-Za-z0-9_]{0,79})[\"\x60]?",
    re.I,
)
SCHEMA_EMAIL = {"email", "email_address", "phone", "mobile"}
SCHEMA_CONTENT = {"message", "body", "content", "subject", "question", "details"}

def print_field(field: str, value: object) -> None:
    assert re.fullmatch("[A-Z0-9_]+", field)
    print("ZM_C17_ORIGIN_"+field+"="+str(value).lower())

def owner_regular(p: Path, max_size: int) -> bool:
    try:
        m = p.lstat()
        return stat.S_ISREG(m.st_mode) and m.st_uid == os.getuid() and 0 < m.st_size <= max_size
    except OSError:
        return False

def owner_dir(p: Path) -> bool:
    try:
        m=p.lstat()
        return stat.S_ISDIR(m.st_mode) and m.st_uid == os.getuid()
    except OSError:
        return False

def php_inventory():
    if not owner_dir(FORM):
        return None
    files=sorted(FORM.glob("*.php"))
    if not 1 <= len(files) <= MAX_SOURCE_FILES:
        return None
    if any(not owner_regular(p, MAX_SOURCE_BYTES) for p in files):
        return None
    data=b"\n".join(p.read_bytes() for p in files)
    tokens={m.group(1).decode("ascii").casefold() for m in SQL_NAMES.finditer(data)}
    indicators={
        "PHP_FILES":len(files),
        "SQL_TABLE_TOKENS":len(tokens),
        "HAS_SQLITE_DSN":b"sqlite:" in data.lower(),
        "HAS_POST_BRANCH":b"$_POST" in data,
        "HAS_CREATE_TABLE":bool(re.search(rb"CREATE\s+TABLE",data,re.I)),
        "HAS_SQL_INSERT":bool(re.search(rb"INSERT\s+INTO",data,re.I)),
        "HAS_EMAIL_VALIDATOR":b"FILTER_VALIDATE_EMAIL" in data,
        "HAS_CONSENT_NAMED_FIELD":bool(re.search(rb"\$_POST\s*\[\s*['\"](?:consent|privacy_consent|accept_terms|agree)['\"]",data,re.I)),
        "HAS_CSRF_NAMED_FIELD":bool(re.search(rb"\bcsrf\b|\bnonce\b",data,re.I)),
        "HAS_SQLITE_LITERAL_SUFFIX":bool(re.search(rb"\.sqlite(?:3)?\b|\.db\b",data,re.I)),
        "HAS_FILE_STORAGE_FUNCTION":bool(re.search(rb"file_put_contents\s*\(|fwrite\s*\(",data,re.I)),
    }
    for k,v in indicators.items(): print_field(k,v)
    return data,tokens

def candidate_files():
    dirs=0
    total_candidates=0
    truncated=False
    seen=set()
    for root in PRIVATE_ROOTS:
        if not owner_dir(root):
            continue
        queue=[(root,0)]
        while queue:
            folder,depth=queue.pop(0)
            if folder in seen: continue
            seen.add(folder)
            dirs+=1
            if dirs>MAX_DIRS:
                truncated=True;break
            try:
                children=list(folder.iterdir())
            except OSError:
                continue
            if len(children)>MAX_DIR_CHILDREN:
                truncated=True;continue
            for p in children:
                if p.suffix.casefold() in SUFFIXES and owner_regular(p,MAX_DB_SIZE):
                    total_candidates+=1
                    if total_candidates>MAX_FILES:
                        truncated=True;break
                    yield p
                elif depth<2 and p.name.casefold() in SAFE_DIR_NAMES and owner_dir(p):
                    queue.append((p,depth+1))
            if total_candidates>MAX_FILES:break
        if total_candidates>MAX_FILES or dirs>MAX_DIRS:break
    print_field("DIRECTORIES_VISITED",min(dirs,MAX_DIRS))
    print_field("SEARCH_TRUNCATED",truncated)

def main():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":
        print_field("STATE","ACCOUNT_MISMATCH")
        return 12
    info=php_inventory()
    if info is None:
        print_field("STATE","UNSAFE_PHP_SOURCE")
        return 13
    source,tokens=info
    totals=dict(
        SQLITE_CANDIDATES=0, VALID_SQLITE_SCHEMAS=0,
        DB_FILENAME_REFERENCED_BY_PHP=0,
        DB_WITH_SHARED_SQL_TABLE_NAME=0,
        DB_WITH_CONTACT_AND_MESSAGE_COLUMNS=0,
        DB_WITH_ANY_SNAPSHOT_LEAD_ROW=0,
        DB_WITH_WAL_SIBLING=0, DB_METADATA_ERRORS=0,
    )
    for path in candidate_files():
        try:
            with path.open("rb") as handle:
                if handle.read(16)!=b"SQLite format 3\x00":continue
            totals["SQLITE_CANDIDATES"]+=1
            if path.name.encode("utf-8") in source:
                totals["DB_FILENAME_REFERENCED_BY_PHP"]+=1
            if path.with_name(path.name+"-wal").exists():
                totals["DB_WITH_WAL_SIBLING"]+=1
            uri="file:"+quote(str(path),safe="/")+"?mode=ro&immutable=1"
            with sqlite3.connect(uri,uri=True,timeout=1) as db:
                db.execute("PRAGMA query_only=ON")
                tables=[
                    x[0] for x in db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ) if isinstance(x[0],str) and re.fullmatch("[A-Za-z_][A-Za-z0-9_]{0,79}",x[0])
                ]
                totals["VALID_SQLITE_SCHEMAS"]+=1
                if {t.casefold() for t in tables}&tokens:
                    totals["DB_WITH_SHARED_SQL_TABLE_NAME"]+=1
                seen_lead=False
                has_row=False
                for table in tables:
                    col={z[1].casefold() for z in db.execute(
                        'PRAGMA table_info("'+table+'")'
                    ) if isinstance(z[1],str)}
                    if col&SCHEMA_EMAIL and col&SCHEMA_CONTENT:
                        seen_lead=True
                        if db.execute(
                            'SELECT EXISTS(SELECT 1 FROM "'+table+'" LIMIT 1)'
                        ).fetchone()[0]:
                            has_row=True
                totals["DB_WITH_CONTACT_AND_MESSAGE_COLUMNS"]+=int(seen_lead)
                totals["DB_WITH_ANY_SNAPSHOT_LEAD_ROW"]+=int(has_row)
        except (OSError,sqlite3.Error):
            totals["DB_METADATA_ERRORS"]+=1
    for k,v in totals.items():print_field(k,v)
    print_field("STATE","READ_ONLY_COMPLETED")
    print_field("PHP_EXECUTION_PATH_VERIFIED","unknown")
    print_field("PHP_POST_PERSISTENCE_VERIFIED","unknown")
    print_field("CUSTOMER_ROW_VALUES_READ","false")
    print_field("LIVE_DB_WRITES","0")
    print_field("PUBLIC_POSTS_SENT","0")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
