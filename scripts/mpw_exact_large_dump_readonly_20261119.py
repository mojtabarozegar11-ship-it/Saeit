"""Exact metadata-identified staging dump: bounded owner-only read-only inspection.

No raw paths, SQL rows, dump bytes, command lines, restore or deletion.
A header/footer marker and no visible open handle do not prove integrity or redundancy.
"""
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import time

HOME=Path("/home/zomorod2")
STAGING=HOME/"Saeit-staging"
TARGET_ROOT=STAGING/"backups"
TARGET_ID="33c2a27a1cefb335"
TARGET_SIZE=17901606016
TARGET_MTIME=1795033731
SAMPLE=65536
ROOTS=(TARGET_ROOT,HOME/".backups",HOME/"Saeit"/"backups",
       HOME/"separated-backups",HOME/"restore-staging")
MAX_ENTRIES=16000
MAX_SECONDS=35

def token(rel):
    return hashlib.sha256(os.fsencode(str(rel))).hexdigest()[:16]

def safe_tree(root):
    try:
        info=root.lstat()
        return root.resolve()==root and stat.S_ISDIR(info.st_mode) and info.st_uid==os.geteuid()
    except OSError:
        return False

def identity(info):
    return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)

def inspect_markers(head,tail):
    return {
        "sql_header_marker": head.startswith((b"-- MySQL dump",b"-- MariaDB dump")) or
            b"-- MySQL dump" in head[:4096] or b"-- MariaDB dump" in head[:4096],
        "gzip_magic": head.startswith(b"\x1f\x8b"),
        "database_ddl_marker": b"CREATE DATABASE" in head or b"-- Current Database:" in head,
        "sql_completion_marker": b"-- Dump completed on " in tail,
        "tail_ends_newline": tail.endswith(b"\n"),
    }

def find_exact(root, staging, target_id, *, size, mtime, seconds=MAX_SECONDS):
    start=time.monotonic()
    seen=0
    matches=[]
    incomplete=False
    if not safe_tree(root):
        return [],False
    device=root.stat().st_dev
    stack=[(root,0)]
    while stack:
        parent,depth=stack.pop()
        if depth>12:
            incomplete=True
            continue
        try:
            with os.scandir(parent) as entries:
                for e in entries:
                    if seen>=MAX_ENTRIES or time.monotonic()-start>seconds:
                        return matches,False
                    seen+=1
                    try:
                        s=e.stat(follow_symlinks=False)
                        if s.st_uid!=os.geteuid() or s.st_dev!=device:
                            incomplete=True
                            continue
                        p=Path(e.path)
                        if stat.S_ISDIR(s.st_mode):
                            stack.append((p,depth+1))
                        elif stat.S_ISREG(s.st_mode) and s.st_size==size and int(s.st_mtime)==mtime and token(p.relative_to(staging))==target_id:
                            matches.append((p,s))
                    except OSError:
                        incomplete=True
        except OSError:
            incomplete=True
    return matches,not incomplete

def bounded_sample(path,expected):
    if not hasattr(os,"O_NOATIME") or not hasattr(os,"O_NOFOLLOW"):
        return {"sample_available":False}
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NOATIME)
    try:
        before=os.fstat(fd)
        if identity(before)!=identity(expected) or before.st_uid!=os.geteuid() or not stat.S_ISREG(before.st_mode):
            raise ValueError("target changed")
        head=os.pread(fd,SAMPLE,0)
        tail=os.pread(fd,SAMPLE,max(0,before.st_size-SAMPLE))
        after=os.fstat(fd)
        if identity(before)!=identity(after) or identity(after)!=identity(path.lstat()):
            raise ValueError("target changed during sample")
        return {"sample_available":True,**inspect_markers(head,tail)}
    finally:
        os.close(fd)

def handles(expected, *, proc=Path("/proc")):
    checked=0
    denied=0
    refs=0
    files=0
    deadline=time.monotonic()+8
    try:
        entries=list(proc.iterdir())
    except OSError:
        return {"visible_owner_processes_checked":0,"visibility_incomplete":True,"matching_open_handles":None}
    for p in entries:
        if not p.name.isdecimal():
            continue
        if time.monotonic()>deadline or checked>=256 or files>=20000:
            denied+=1
            break
        try:
            if p.stat().st_uid!=os.geteuid():
                continue
            checked+=1
            with os.scandir(p/"fd") as fds:
                for f in fds:
                    if files>=20000 or time.monotonic()>deadline:
                        denied+=1
                        break
                    files+=1
                    try:
                        s=f.stat(follow_symlinks=True)
                        refs+=int((s.st_dev,s.st_ino)==(expected.st_dev,expected.st_ino))
                    except FileNotFoundError:
                        continue
                    except OSError:
                        denied+=1
        except (PermissionError,OSError):
            denied+=1
    return {"visible_owner_processes_checked":checked,"fd_entries_checked":files,
            "visibility_incomplete":bool(denied),"matching_open_handles":refs,
            "all_runtime_dependencies_proven_absent":False}

def same_size_candidates(expected):
    deadline=time.monotonic()+15
    entries=0
    other=0
    alias=0
    roots_checked=0
    incomplete=False
    for root in ROOTS:
        if not safe_tree(root):
            incomplete=True
            continue
        roots_checked+=1
        stack=[(root,0)]
        dev=root.stat().st_dev
        while stack:
            parent,depth=stack.pop()
            if depth>6:
                incomplete=True
                continue
            try:
                with os.scandir(parent) as it:
                    for e in it:
                        if entries>=MAX_ENTRIES or time.monotonic()>deadline:
                            return {"roots_checked":roots_checked,"complete":False,"same_size_other_inodes":other,"same_inode_aliases":alias}
                        entries+=1
                        try:
                            s=e.stat(follow_symlinks=False)
                            if s.st_uid!=os.geteuid() or s.st_dev!=dev:
                                incomplete=True
                                continue
                            if stat.S_ISDIR(s.st_mode):
                                stack.append((Path(e.path),depth+1))
                            elif stat.S_ISREG(s.st_mode) and s.st_size==expected.st_size:
                                if (s.st_dev,s.st_ino)==(expected.st_dev,expected.st_ino):
                                    alias+=1
                                else:
                                    other+=1
                        except OSError:
                            incomplete=True
            except OSError:
                incomplete=True
    return {"roots_checked":roots_checked,"complete":not incomplete,
            "same_size_other_inodes":other,"same_inode_aliases_including_target":alias}

def audit():
    out={"schema":"mpw.exact_dump.readonly.v1","read_only":True,"target_verified":False,
         "raw_sql_disclosed":False,"checksum_verified":False,"restore_verified":False,
         "duplicate_verified":False,"safe_to_delete":False,"release_authorized":False}
    if pwd.getpwuid(os.geteuid()).pw_name!="zomorod2":
        return out
    matches,complete=find_exact(TARGET_ROOT,STAGING,TARGET_ID,size=TARGET_SIZE,mtime=TARGET_MTIME)
    out["target_search_complete"]=complete
    out["matching_candidates"]=len(matches)
    if not complete or len(matches)!=1:
        return out
    path,s=matches[0]
    out.update(target_verified=True,logical_bytes=s.st_size,allocated_bytes=s.st_blocks*512,
               mode=oct(stat.S_IMODE(s.st_mode)),hardlink_count=s.st_nlink,mtime_unix=int(s.st_mtime),
               file_type_by_suffix="plain_sql" if path.name.lower().endswith(".sql") else "other_sql_archive")
    try:
        out["markers"]=bounded_sample(path,s)
    except (OSError,ValueError) as exc:
        out["sample_error_type"]=type(exc).__name__
    out["open_handles"]=handles(s)
    out["candidate_inventory"]=same_size_candidates(s)
    out["unchanged_at_end"]=identity(s)==identity(path.lstat())
    return out

if __name__=="__main__":
    try:
        print("MPW_EXACT_DUMP_READONLY="+json.dumps(audit(),sort_keys=True),flush=True)
    except Exception as exc:
        raise SystemExit("MPW_EXACT_DUMP_FAILED="+type(exc).__name__) from None
