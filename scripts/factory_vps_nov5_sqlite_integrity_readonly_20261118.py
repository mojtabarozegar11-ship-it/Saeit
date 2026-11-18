#!/usr/bin/env python3
"""OFFLINE, READ-ONLY integrity validation of TWO existing 2026-11-05 VPS SQLite copies.

Run via owner-pinned SSH as githubops on the existing inactive VPS. Does not run factory or
connect to production MariaDB. Refuses symlinks, WAL/shm, unexpected hashes,
file mutation, non-owner paths, unreadable state, and non-ok PRAGMA reports.
No file write or deletion. This is historical backup validation only. File existence is not offsite cloud redundancy.
"""
import hashlib
import json
import os
from pathlib import Path
import pwd
import sqlite3
import stat
import sys
import time
import urllib.parse

ROOT = Path("/home/githubops/factory-runtime/operations/backups")
EXPECTED = (
    ("master-before-20261105T154953Z.sqlite3", 1408634880,
     "a9fd2175f9ace1a81d67cf7145e54b8621fd44cc06b0b2739bdc9345e21750e2"),
    ("master-before-20261105T210434Z.sqlite3", 1408634880,
     "402c16b67d430132701435eb4b3f79de88cd5c2479bb07c741c6674708a931be"),
)
MAGIC=b"SQLite format 3\x00"


def _identity(st):
    return (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)


def _validate_parent():
    if pwd.getpwuid(os.geteuid()).pw_name != "githubops":
        raise RuntimeError("VPS_OWNER_IDENTITY_FAIL")
    for p in (Path("/home/githubops"),Path("/home/githubops/factory-runtime"),ROOT.parent,ROOT):
        s=p.lstat()
        if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.geteuid() or s.st_mode & 0o022:
            raise RuntimeError("VPS_BACKUP_ROOT_UNTRUSTED")


def _hash_stable(path,expected_size,expected_sha):
    before=path.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
            or before.st_nlink!=1 or before.st_size != expected_size):
        raise RuntimeError("VPS_BACKUP_FILE_NOT_IMMUTABLE")
    for suffix in ("-wal","-shm","-journal"):
        aux=path.with_name(path.name+suffix)
        if aux.exists() or aux.is_symlink():
            raise RuntimeError("VPS_BACKUP_SIDE_CAR_PRESENT")
    fd=os.open(path,os.O_RDONLY | getattr(os,"O_NOFOLLOW",0))
    try:
        at_open=os.fstat(fd)
        if _identity(before)!=_identity(at_open):
            raise RuntimeError("BACKUP_CHANGED_BEFORE_HASH")
        sha=hashlib.sha256()
        total=0
        if os.read(fd,16)!=MAGIC:
            raise RuntimeError("NOT_SQLITE3_BACKUP")
        os.lseek(fd,0,os.SEEK_SET)
        while True:
            b=os.read(fd,1024*1024)
            if not b:break
            sha.update(b);total+=len(b)
            if total>expected_size:
                raise RuntimeError("BACKUP_GREW_DURING_HASH")
        if _identity(os.fstat(fd))!=_identity(before) or total!=expected_size or sha.hexdigest()!=expected_sha:
            raise RuntimeError("VPS_BACKUP_DIGEST_OR_MUTATION_FAIL")
    finally:
        os.close(fd)
    return before


def _inspect(name,expected_size,expected_sha):
    path=ROOT/name
    baseline=_hash_stable(path,expected_size,expected_sha)
    safe_uri="file:"+urllib.parse.quote(str(path),safe="/")+"?mode=ro&immutable=1"
    conn=sqlite3.connect(safe_uri,uri=True,timeout=30)
    try:
        conn.execute("PRAGMA query_only=ON")
        q=conn.execute("PRAGMA quick_check").fetchone()[0]
        if q!="ok":
            raise RuntimeError("SQLITE_QUICK_CHECK_NOT_OK")
        i=conn.execute("PRAGMA integrity_check").fetchone()[0]
        if i!="ok":
            raise RuntimeError("SQLITE_INTEGRITY_CHECK_NOT_OK")
        count=int(conn.execute("PRAGMA page_count").fetchone()[0])
        size=int(conn.execute("PRAGMA page_size").fetchone()[0])
    finally:
        conn.close()
    # Must not have mutated original after SQLite check.
    if _identity(path.lstat())!=_identity(baseline):
        raise RuntimeError("BACKUP_MUTATED_DURING_PRAGMA")
    return {"snapshot_id":("nov5-a" if name==EXPECTED[0][0] else "nov5-b"),
            "size":expected_size,"sha256":expected_sha,
            "quick_check":"ok","integrity_check":"ok",
            "page_count_positive":count>0,"page_size_positive":size>0,
            "source_unchanged":True,
            "production_mysql_accessed":False}


def main():
    started=time.monotonic()
    _validate_parent()
    records=[_inspect(*values) for values in EXPECTED]
    if len(records)!=2 or not all(x["page_count_positive"] and x["page_size_positive"] for x in records):
        raise RuntimeError("EXPECTED_TWO_HEALTHY_DATABASES")
    out={"schema":"factory.cpanel.historical-nov5-sqlite-integrity.v1",
         "checked_snapshots":records,"number_of_snapshots":2,
         "factory_started":False,"source_deleted":False,
         "files_written":0,"mysql_connection":False,
         "independent_google_drive_mirror_proven":False,
         "safe_to_delete":False,
         "elapsed_seconds":round(time.monotonic()-started,2)}
    print("FACTORY_VPS_NOV5_SQLITE_INTEGRITY="+json.dumps(out,sort_keys=True,separators=(",",":")),flush=True)


if __name__=="__main__":
    try:main()
    except BaseException as exc:
        # Never write file content, SQL row values, stack traces or private paths.
        code=str(exc) if type(exc) is RuntimeError else type(exc).__name__
        print("FACTORY_VPS_NOV5_INTEGRITY_HOLD="+code,flush=True,file=sys.stderr)
        sys.exit(2)
