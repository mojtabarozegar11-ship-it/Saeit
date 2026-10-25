#!/usr/bin/env python3
"""Fail-closed in-place fix for installed private Stage2 atomic handoff race."""
import argparse
import ast
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

OPS=Path("/home/githubops/factory-runtime/operations/production-instructions")
AREA=Path("/home/githubops/factory-runtime/private/autonomous-product-cycle/production-instructions")
BACKUPS=OPS.parent/"backups"
LIVE=OPS/"stage2-research-serial.py"
OLD="0651bedc72cfce394b91f907b73855b5b084f4370ecf18fe56c602bec8586fca"
ENGLISH="SAEIT_ENGLISH_FIRST_SINGLE_ACTIVE_20261025"
BULK="SAEIT_FACTORY_OWNER_DELEGATE_COORDINATION_V1"

def sha(b):return hashlib.sha256(b).hexdigest()

def run(candidate,expected,run_id,apply):
    if os.geteuid()==0 or os.getenv("USER")!="githubops":
        raise RuntimeError("WRONG_USER")
    if not re.fullmatch(r"[0-9]{5,15}-[0-9]{1,3}",run_id):
        raise RuntimeError("INVALID_RUN")
    if not re.fullmatch(r"[a-f0-9]{64}",expected):
        raise RuntimeError("INVALID_TARGET_SHA")
    for path in (OPS,AREA,BACKUPS,AREA/"orders"):
        if not path.is_dir() or path.is_symlink():raise RuntimeError("UNSAFE_FACTORY_SCOPE")
    if not LIVE.is_file() or LIVE.is_symlink():raise RuntimeError("LIVE_WORKER_UNSAFE")
    before=LIVE.read_bytes()
    original_sha=sha(before)
    if original_sha not in (OLD,expected):
        raise RuntimeError("UNKNOWN_DEPLOYED_STAGE2_WORKER_SHA:"+original_sha[:12])
    source=Path(candidate)
    if source.parent!=OPS or not source.name.startswith(".stage2-verified-upload-") or source.is_symlink() or not source.is_file():
        raise RuntimeError("UNSAFE_CANDIDATE_FILE")
    updated=source.read_bytes()
    if sha(updated)!=expected:raise RuntimeError("PROPOSED_CONTENT_DIGEST_WRONG")
    ast.parse(updated.decode("utf8"))
    if (b"STAGE2_UNSAFE_STAGE1_ATOMIC_TEMP" not in updated
            or b"STAGE2_UNEXPECTED_INBOX_FILE" not in updated
            or b"only_order_id" not in updated):
        raise RuntimeError("SOURCE_SCOPE_INVARIANT_MISSING")
    beforecron=subprocess.run(["crontab","-l"],capture_output=True,text=True,check=True,timeout=8).stdout
    active=[x for x in beforecron.splitlines() if x.strip() and not x.lstrip().startswith("#")]
    if sum(ENGLISH in x for x in active)!=1 or any(BULK in x for x in active):
        raise RuntimeError("PRIVATE_SCHEDULER_SCOPE_NOT_SAFE")
    report={"mode":"APPLY" if apply else "DRY_RUN","old_sha":original_sha,
            "new_sha":expected,"orders_unchanged":True,
            "customer_products_modified":False,"storefront_modified":False}
    if not apply:return report
    locks=[]
    try:
        for p in (OPS/".english-first-single-active.lock",AREA/"stage-02/.worker.lock"):
            if p.is_symlink():raise RuntimeError("WORKER_LOCK_SYMLINK")
            fd=os.open(p,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(fd)
                raise RuntimeError("STAGE2_IS_ACTIVE_RETRY")
            locks.append(fd)
        if sha(LIVE.read_bytes())!=original_sha:
            raise RuntimeError("DEPLOYED_WORKER_CHANGED_DURING_LOCK")
        backup=BACKUPS/("stage2-atomic-preimage-"+run_id+".py")
        if backup.exists() or backup.is_symlink():raise RuntimeError("BACKUP_ALREADY_EXISTS")
        fd=os.open(backup,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"wb") as out:
            out.write(before);out.flush();os.fsync(out.fileno())
        fd,temporary=tempfile.mkstemp(prefix=".atomic-stage2-install-",dir=OPS)
        try:
            os.fchmod(fd,0o600)
            with os.fdopen(fd,"wb") as stream:
                stream.write(updated);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,LIVE)
            if sha(LIVE.read_bytes())!=expected:
                raise RuntimeError("INSTALLED_SHA_MISMATCH")
        except Exception:
            if sha(LIVE.read_bytes())==expected:
                os.replace(backup,LIVE)
            if os.path.exists(temporary):os.unlink(temporary)
            raise
        source.unlink()
        report["patched"]=True
        report["rollback_backup"]=backup.name
        report["new_sha_verified"]=True
        return report
    finally:
        for fd in reversed(locks):os.close(fd)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--candidate",required=True)
    parser.add_argument("--expected-sha",required=True)
    parser.add_argument("--run-id",required=True)
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    try:print("STAGE2_ATOMIC_RACE_FIX="+json.dumps(run(args.candidate,args.expected_sha,args.run_id,args.apply),sort_keys=True),flush=True)
    except Exception as exc:
        print("STAGE2_ATOMIC_RACE_FIX_FAILED="+type(exc).__name__+":"+str(exc)[:220],file=sys.stderr,flush=True)
        sys.exit(1)
