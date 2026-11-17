#!/usr/bin/env python3
"""Stream two verified immutable factory SQLite backup snapshots to stdout as gzip tar.

Run only under the already authenticated githubops VPS identity, via SSH stdin.
No writes or file deletions are performed on the VPS by this program.
The output MUST be encrypted before publication as a GitHub artifact.
"""
import datetime
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import tarfile

ROOT=Path("/home/githubops/factory-runtime/operations/backups")
NAME=re.compile(r"master-before-[0-9]{8}T[0-9]{6}Z[.]sqlite3\Z")

def snapshots():
    s=ROOT.lstat()
    if not stat.S_ISDIR(s.st_mode) or stat.S_ISLNK(s.st_mode):
        raise RuntimeError("BACKUP_ROOT_UNSAFE")
    selected=[]
    for p in ROOT.iterdir():
        if not NAME.fullmatch(p.name):
            continue
        st=p.lstat()
        if stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_size>=4096 and not p.with_name(p.name+"-wal").exists():
            selected.append((p,st))
    selected.sort(key=lambda v:(v[1].st_mtime_ns,v[0].name),reverse=True)
    if len(selected)<2:
        raise RuntimeError("FEWER_THAN_TWO_SAFE_MASTER_SNAPSHOTS")
    return selected[:2]

def main():
    if os.geteuid()!=__import__("pwd").getpwnam("githubops").pw_uid:
        raise RuntimeError("WRONG_VPS_IDENTITY")
    chosen=snapshots()
    meta=[]
    for path,pre in chosen:
        con=sqlite3.connect(path.as_uri()+"?mode=ro&immutable=1",uri=True,timeout=30)
        try:
            if con.execute("PRAGMA quick_check").fetchone()[0]!="ok":
                raise RuntimeError("SQLITE_QUICK_CHECK_FAILED")
            if con.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise RuntimeError("SQLITE_INTEGRITY_CHECK_FAILED")
        finally:
            con.close()
        now=path.lstat()
        if (pre.st_size,pre.st_mtime_ns,pre.st_ino)!=(now.st_size,now.st_mtime_ns,now.st_ino):
            raise RuntimeError("SNAPSHOT_CHANGED_BEFORE_STREAM")
        meta.append({"name":path.name,"bytes":pre.st_size,"integrity_check":"ok"})
    print("FACTORY_SNAPSHOT_SOURCE="+json.dumps({"selected":meta,"status":"fully_checked","local_backup_deleted":False},sort_keys=True),file=sys.stderr,flush=True)
    with tarfile.open(fileobj=sys.stdout.buffer,mode="w|gz") as tar:
        for path,pre in chosen:
            flags=os.O_RDONLY|getattr(os,"O_NOFOLLOW",0)
            fd=os.open(path,flags)
            try:
                initial=os.fstat(fd)
                if (pre.st_ino,pre.st_size,pre.st_mtime_ns)!=(initial.st_ino,initial.st_size,initial.st_mtime_ns):
                    raise RuntimeError("SNAPSHOT_REPLACED_BEFORE_STREAM")
                info=tarfile.TarInfo("operations/backups/"+path.name)
                info.size=initial.st_size
                info.mtime=int(initial.st_mtime)
                info.uid=0
                info.gid=0
                info.mode=0o600
                with os.fdopen(fd,"rb",closefd=False) as f:
                    tar.addfile(info,f)
                after=os.fstat(fd)
                if (initial.st_ino,initial.st_size,initial.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
                    raise RuntimeError("SNAPSHOT_CHANGED_DURING_STREAM")
            finally:
                os.close(fd)
    print("FACTORY_SNAPSHOT_STREAM_FINISHED=true",file=sys.stderr,flush=True)

if __name__=="__main__":
    try: main()
    except Exception as exc:
        print("FACTORY_SNAPSHOT_STREAM_FAILED="+type(exc).__name__+":"+str(exc),file=sys.stderr,flush=True)
        sys.exit(1)
