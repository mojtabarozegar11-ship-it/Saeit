#!/usr/bin/env python3
"""Read-only SHA-256 content equality proof for two known November master backups.

No writes/deletes, no production DB access, no keys, no private paths in output.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import zlib

ROOT=Path("/home/githubops/factory-runtime/operations/backups")
NAMES=(
    "master-before-20261105T154953Z.sqlite3",
    "master-before-20261105T210434Z.sqlite3",
)
MAGIC=b"SQLite format 3"+bytes([0])
BUF=2*1024*1024


def examine(name):
    p=ROOT/name
    pre=p.lstat()
    if not stat.S_ISREG(pre.st_mode) or pre.st_nlink!=1:
        raise RuntimeError("UNSAFE_BACKUP_FILE")
    if pre.st_size<1024*1024:
        raise RuntimeError("SUSPICIOUS_BACKUP_SIZE")
    for ext in ("-wal","-shm","-journal"):
        if (ROOT/(name+ext)).exists():
            raise RuntimeError("SQLITE_SIDECAR_PRESENT")
    flags=os.O_RDONLY|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(p,flags)
    try:
        initial=os.fstat(fd)
        if (initial.st_ino,initial.st_size,initial.st_mtime_ns)!=(pre.st_ino,pre.st_size,pre.st_mtime_ns):
            raise RuntimeError("CHANGED_BEFORE_READ")
        digest=hashlib.sha256()
        count=0
        with os.fdopen(fd,"rb",closefd=False) as stream:
            header=stream.read(16)
            if header!=MAGIC:
                raise RuntimeError("SQLITE_HEADER_NOT_VALID")
            digest.update(header)
            count+=len(header)
            while True:
                part=stream.read(BUF)
                if not part: break
                count+=len(part)
                if count>initial.st_size:raise RuntimeError("GROWING_BACKUP")
                digest.update(part)
        after=os.fstat(fd)
        if count!=initial.st_size or (initial.st_ino,initial.st_size,initial.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
            raise RuntimeError("CHANGED_DURING_READ")
        return {"name":name,"bytes":count,"sha256":digest.hexdigest(),"unchanged":True}
    finally:
        os.close(fd)


def main():
    if os.geteuid()!=__import__("pwd").getpwnam("githubops").pw_uid:
        raise RuntimeError("WRONG_IDENTITY")
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise RuntimeError("UNSAFE_ROOT")
    started=time.monotonic()
    files=[examine(n) for n in NAMES]
    identical=(files[0]["bytes"]==files[1]["bytes"] and files[0]["sha256"]==files[1]["sha256"])
    report={"schema":"moj.factory.sqlite.content-equivalence.v1","read_only":True,
            "vps_files_changed":0,"files_deleted":0,"files":files,
            "same_size":files[0]["bytes"]==files[1]["bytes"],"sha256_equal":identical,
            "deletion_permitted":False,"elapsed_seconds":round(time.monotonic()-started,2)}
    print("MOJ_FACTORY_SQLITE_EQUIVALENCE="+json.dumps(report,sort_keys=True),flush=True)


if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("MOJ_FACTORY_SQLITE_EQUIVALENCE_FAILED="+type(exc).__name__+":"+str(exc),file=sys.stderr,flush=True)
        sys.exit(1)
