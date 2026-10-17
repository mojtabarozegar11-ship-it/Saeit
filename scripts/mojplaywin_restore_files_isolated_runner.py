#!/usr/bin/env python3
"""Extract verified MojPlayWin backup tar into a fresh, private CI sandbox.

stdin is PRIVATE plaintext TAR from SSH/GPG, NEVER tee/print/store archive.
Reject absolute/traversal paths, devices and unsafe links. Symlinks are
materialized only after regular files, and only when their targets remain
inside sandbox. No production writes. Caller removes sandbox after test.
"""
from __future__ import annotations

import json
import os
import posixpath
import shutil
import stat
import sys
import tarfile
from pathlib import Path, PurePosixPath

ROOTS={"Saeit-staging","mojplaywin.com"}
MAX_ENTRIES=150000
MAX_BYTES=10*1024**3
MIN_FREE_BYTES=1024**3


def safe_parts(name):
    if not isinstance(name,str) or name.startswith("/"):
        raise ValueError("unsafe absolute path")
    p=PurePosixPath(name)
    parts=p.parts
    if (not parts or parts[0] not in ROOTS or
        any(x in ("..","") for x in parts) or name.startswith("./")):
        raise ValueError("unsafe relative archive path")
    return parts


def check_parents(base,parts):
    p=base
    for name in parts[:-1]:
        p=p/name
        if p.is_symlink():
            raise ValueError("symlinked directory forbidden")
        if p.exists() and not p.is_dir():
            raise ValueError("archive parent is not directory")
        p.mkdir(mode=0o700,exist_ok=True)
    return base.joinpath(*parts)


def space(path):
    statv=os.statvfs(path)
    return statv.f_bavail*statv.f_frsize


def recover(stream, directory):
    base=Path(directory).resolve()
    if not base.is_dir() or base.is_symlink():
        raise ValueError("missing private restore directory")
    s=base.stat()
    if not stat.S_ISDIR(s.st_mode) or bool(s.st_mode & 0o077):
        raise ValueError("restore root must be private")
    result={"classification":"ISOLATED_FILE_RECOVERY_REHEARSAL",
            "regular_files_restored":0,"directories_restored":0,
            "symlinks_restored":0,"hardlinks_restored":0,
            "regular_bytes_restored":0,"root_count_restored":0,
            "restore_complete":False,"production_modified":False}
    present=set()
    links=[]
    seen=set()
    total=0
    with tarfile.open(fileobj=stream,mode="r|") as archive:
        for item in archive:
            parts=safe_parts(item.name)
            if len(seen)>=MAX_ENTRIES:
                raise ValueError("too many tar members")
            normalized="/".join(parts)
            if normalized in seen:
                raise ValueError("archive duplicate path")
            seen.add(normalized)
            present.add(parts[0])
            dest=check_parents(base,parts)
            if dest.is_symlink():
                raise ValueError("symlink target collision")
            if item.isdir():
                dest.mkdir(mode=0o700,parents=True,exist_ok=True)
                result["directories_restored"]+=1
            elif item.isfile():
                if space(base)<MIN_FREE_BYTES or item.size<0 or total+item.size>MAX_BYTES:
                    raise ValueError("insufficient isolated capacity")
                parent=dest.parent
                parent.mkdir(mode=0o700,exist_ok=True)
                src=archive.extractfile(item)
                if src is None:
                    raise ValueError("missing regular member bytes")
                n=0
                with dest.open("xb") as out:
                    while True:
                        chunk=src.read(131072)
                        if not chunk:
                            break
                        n+=len(chunk)
                        out.write(chunk)
                if n!=item.size:
                    raise ValueError("incomplete restored regular file")
                os.chmod(dest,(item.mode & 0o700) | 0o600)
                total+=n
                result["regular_files_restored"]+=1
                result["regular_bytes_restored"]=total
            elif item.issym() or item.islnk():
                links.append((parts,item.linkname,item.issym()))
            else:
                raise ValueError("special file member not permitted in sandbox")
    # Never permit links to become parents before all ordinary files exist.
    for parts,target,is_symlink in links:
        if not isinstance(target,str) or target.startswith("/"):
            raise ValueError("absolute archive link cannot be restored into sandbox")
        candidate=posixpath.normpath(
            posixpath.join(*(parts[:-1] if is_symlink else ()),target)
        ) if is_symlink else posixpath.normpath(target)
        safe_parts(candidate)
        path=base.joinpath(*parts)
        check_parents(base,parts)
        referent=base.joinpath(*PurePosixPath(candidate).parts)
        if referent.is_symlink():
            raise ValueError("nested archive links not restored")
        if is_symlink:
            if path.exists() or path.is_symlink():
                raise ValueError("link collision")
            os.symlink(target,path)
            result["symlinks_restored"]+=1
        else:
            if not referent.is_file() or path.exists() or path.is_symlink():
                raise ValueError("hardlink target missing")
            os.link(referent,path)
            result["hardlinks_restored"]+=1
    if present != ROOTS or result["regular_files_restored"]<1:
        raise ValueError("source roots missing from recovered archive")
    # Drain rest of the decrypted stream so the upstream GPG integrity verifier
    # can reach EOF and validate the signed completion footer.
    while stream.read(131072):
        pass
    result["root_count_restored"]=len(present)
    result["restore_complete"]=True
    return result


if __name__=="__main__":
    try:
        if len(sys.argv)!=2:
            raise ValueError("expected one isolated temporary directory")
        print(json.dumps(recover(sys.stdin.buffer,sys.argv[1]),sort_keys=True))
    except Exception:
        print("SANDBOX_FILE_RECOVERY_FAILED_NO_RELEASE",file=sys.stderr)
        raise SystemExit(1)
