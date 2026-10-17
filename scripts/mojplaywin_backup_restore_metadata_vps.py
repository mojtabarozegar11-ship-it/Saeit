#!/usr/bin/env python3
"""Audit the recoverability of an authenticated tar backup without writing files.

Run only on isolated VPS; stream GPG plaintext directly into Python tarfile.
No filenames, confidential data, key, SQL, paths or archive contents are logged.
"""
from __future__ import annotations
import base64
import io
import json
import os
import posixpath
import subprocess
import sys
import tarfile
import types
from collections import Counter
from pathlib import PurePosixPath

FIXED="mojplaywin_20261017_direct_39028678930"
ALLOWED_ROOTS={"Saeit-staging","mojplaywin.com"}

def start(recovery_b64: str):
    mod=types.ModuleType("verified_recovery")
    exec(compile(base64.b64decode(recovery_b64),"<reviewed-repository-recovery>","exec"),mod.__dict__)
    mod.STEM=FIXED
    # Avoid shipping real data to GitHub: both decryption and tar parse run on VPS.
    command=("import base64,sys,types;"
             "m=types.ModuleType('backup_recovery');"
             "exec(base64.b64decode(sys.argv[1]),m.__dict__);"
             "m.STEM=sys.argv[2];"
             "m.decrypt_to_stdout('files')")
    return subprocess.Popen(["python3","-c",command,recovery_b64,FIXED],
                            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)

def audit(stream):
    counts=Counter()
    roots=set()
    visited=set()
    problems=Counter()
    samples=Counter()
    with tarfile.open(fileobj=stream,mode="r|") as archive:
        for member in archive:
            counts["members"]+=1
            counts["regular_bytes"]+=member.size if member.isfile() else 0
            if member.isdir():counts["directories"]+=1
            elif member.isfile():counts["regular"]+=1
            elif member.issym():counts["symlinks"]+=1
            elif member.islnk():counts["hardlinks"]+=1
            else:
                counts["special"]+=1
                problems["special_tar_entry"]+=1
            name=member.name
            p=PurePosixPath(name)
            parts=p.parts
            if (name.startswith("/") or name.startswith("./") or
                not parts or parts[0] not in ALLOWED_ROOTS or
                any(x in ("..","") for x in parts)):
                problems["unsafe_member_path"]+=1
                continue
            roots.add(parts[0])
            normalized="/".join(parts)
            if normalized in visited:problems["repeated_member_path"]+=1
            visited.add(normalized)
            if member.issym() or member.islnk():
                target=member.linkname
                if not target:
                    problems["empty_link"]+=1
                elif target.startswith("/"):
                    problems["absolute_link"]+=1
                    if target.startswith("/home/zomorod2/Saeit-staging/") or target=="/home/zomorod2/Saeit-staging":
                        counts["absolute_link_points_to_backed_app"]+=1
                    elif target.startswith("/home/zomorod2/mojplaywin.com/") or target=="/home/zomorod2/mojplaywin.com":
                        counts["absolute_link_points_to_backed_docroot"]+=1
                    elif target.startswith("/home/zomorod2/"):
                        counts["absolute_link_points_to_other_account_root"]+=1
                    elif target.startswith(("/usr/","/bin/","/lib/","/etc/")):
                        counts["absolute_link_points_to_os"]+=1
                    else:
                        counts["absolute_link_points_to_other"]+=1
                else:
                    candidate=posixpath.normpath(
                        posixpath.join(*(parts[:-1] if member.issym() else ()),target)
                    ) if member.issym() else posixpath.normpath(target)
                    ref=PurePosixPath(candidate)
                    if (candidate.startswith("/") or candidate.startswith("./") or
                        not ref.parts or ref.parts[0] not in ALLOWED_ROOTS or
                        any(x in ("..","") for x in ref.parts)):
                        problems["link_escapes_backup_roots"]+=1
                if member.issym() and name.endswith("/"):
                    problems["symlink_dir_anomaly"]+=1
    # tarfile stops on trailer blocks; consume the authenticated footer to EOF.
    while stream.read(131072):
        counts["post_tar_bytes"]+=1
    return {
      "classification":"ENCRYPTED_FILES_TAR_READ_ONLY_AUDIT",
      "has_both_expected_roots":roots==ALLOWED_ROOTS,
      "counts":dict(counts),
      "problems":dict(problems),
      "safe_for_exact_isolated_restore":bool(
           roots==ALLOWED_ROOTS and not any(problems.values())),
      "release_permitted":False,
    }

def main():
    if len(sys.argv)!=2:raise SystemExit("INVALID_INPUT")
    p=start(sys.argv[1])
    try:
        if p.stdout is None:raise RuntimeError("no stream")
        report=audit(p.stdout)
        p.stdout.close()
        if p.wait(timeout=90):
            raise RuntimeError("encrypted source integrity failed")
        print(json.dumps(report,sort_keys=True),flush=True)
    except Exception as exc:
        print("ARCHIVE_READ_ONLY_AUDIT_FAILED_KIND="+type(exc).__name__,flush=True)
        if p.poll() is None:
            p.kill();p.wait()
        raise SystemExit(1)

if __name__=="__main__":
    main()
