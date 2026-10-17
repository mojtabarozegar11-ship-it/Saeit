#!/usr/bin/env python3
"""Atomic main-only six-template release with exact preimage verification.

Only core/templates/mojplaywin/{founder_signature,unified_visual_tokens,
theme,footer,store,home}.html. No shared Django code, WSGI, Passenger, payment,
product/order, DB, child-site file or global URL changes. Private file backups
are retained and independently sha256 verified for rollback. No chdir or glob.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

APP = Path("/home/zomorod2/Saeit-staging")
TEMPLATES = APP / "core/templates/mojplaywin"
BACKROOT = Path("/home/zomorod2/.mpw-mainonly-template-backups")
NAMES = ("founder_signature.html","unified_visual_tokens.html",
         "theme.html","footer.html","store.html","home.html")
LIMIT = 200000
def digest(b):
    return hashlib.sha256(b).hexdigest()

def roots():
    for p in (APP,APP/"core",APP/"core/templates",TEMPLATES):
        if not p.is_dir() or p.is_symlink():
            raise RuntimeError("unsafe fixed main-only directory")
    if BACKROOT.is_symlink():
        raise RuntimeError("backup root is symlink")
    BACKROOT.mkdir(mode=0o700,exist_ok=True)
    os.chmod(BACKROOT,0o700)

def file_state(p):
    if p.is_symlink():
        raise RuntimeError("main template is symlink")
    if not p.exists():
        return None
    if not p.is_file() or p.stat().st_size>LIMIT:
        raise RuntimeError("main template unsafe size/type")
    return p.read_bytes()

def checked_payload(data):
    if data.get("classification")!="MPW_EXACT_MAINONLY_SIX" or set(data.get("files",{}))!=set(NAMES):
        raise RuntimeError("wrong template allowlist")
    result={}
    for name in NAMES:
        v=data["files"][name]
        if set(v)!={"old_sha256","new_sha256","new_b64"}:
            raise RuntimeError("wrong template metadata")
        raw=base64.b64decode(v["new_b64"],validate=True)
        if len(raw)>LIMIT or digest(raw)!=v["new_sha256"]:
            raise RuntimeError("new template hash mismatch")
        old=v["old_sha256"]
        if old is not None and not re.fullmatch("[0-9a-f]{64}",old):
            raise RuntimeError("old hash format")
        if not raw.startswith(b"{%"):
            raise RuntimeError("unexpected template contents")
        result[name]=(old,raw)
    return result

def write_atomic(path,data,runid,mode=0o600):
    tmp=path.parent/(".mpw-safe-"+runid+"-"+path.name+".tmp")
    fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,mode)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,mode)
        os.replace(tmp,path)
        dr=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(dr)
        finally:os.close(dr)
    finally:
        if tmp.exists():tmp.unlink()

def release_dir(runid):
    if not re.fullmatch(r"[0-9]{8,14}",runid):
        raise RuntimeError("invalid GitHub release ID")
    roots()
    d=BACKROOT/("run-"+runid)
    if d.is_symlink():
        raise RuntimeError("backup directory symlink")
    return d

def deploy(runid,payload):
    data=checked_payload(payload)
    backup=release_dir(runid)
    if backup.exists():
        raise RuntimeError("release already exists")
    for name in NAMES:
        old,raw=data[name]
        existing=file_state(TEMPLATES/name)
        if old is None and existing is not None:
            raise RuntimeError("unexpected existing new template")
        if old is not None and (existing is None or digest(existing)!=old):
            raise RuntimeError("live preimage is not exact GitHub baseline")
    backup.mkdir(mode=0o700)
    manifest={"phase":"prepared","runid":runid,"files":{}}
    for name in NAMES:
        prior=file_state(TEMPLATES/name)
        old,new=data[name]
        if prior is not None:
            saved=backup/name
            fd=os.open(saved,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,"wb") as f:
                f.write(prior);f.flush();os.fsync(f.fileno())
            if digest(saved.read_bytes())!=old:
                raise RuntimeError("backup verification failed")
        manifest["files"][name]={"old":old,"new":digest(new),
                                  "mode":stat.S_IMODE((TEMPLATES/name).stat().st_mode) if prior is not None else 0o644}
    write_atomic(backup/"manifest.json",json.dumps(manifest,sort_keys=True).encode(),runid)
    try:
        for name in NAMES:
            old,new=data[name]
            write_atomic(TEMPLATES/name,new,runid,manifest["files"][name]["mode"])
            if digest((TEMPLATES/name).read_bytes())!=digest(new):
                raise RuntimeError("post write hash mismatch")
        manifest["phase"]="installed"
        write_atomic(backup/"manifest.json",json.dumps(manifest,sort_keys=True).encode(),runid)
    except Exception:
        rollback(runid)
        raise
    print(json.dumps({"classification":"MAIN_ONLY_TEMPLATES_ATOMIC_INSTALLED",
        "scoped_files":len(NAMES),"shared_runtime_modified":False,"passenger_restart":False,
        "products_payments_changed":False,"protected_subsites_modified":False,
        "post_release_smoke_pending":True},sort_keys=True))

def rollback(runid):
    backup=release_dir(runid)
    if not backup.is_dir():
        raise RuntimeError("no verified backup")
    manifest=json.loads((backup/"manifest.json").read_text())
    if manifest.get("runid")!=runid or set(manifest.get("files",{}))!=set(NAMES):
        raise RuntimeError("backup manifest incorrect")
    for name in reversed(NAMES):
        meta=manifest["files"][name]
        target=TEMPLATES/name
        now=file_state(target)
        if now is not None and digest(now) not in {meta["old"],meta["new"]}:
            raise RuntimeError("rollback refuses unrelated file changes")
        if meta["old"] is None:
            if now is not None:target.unlink()
        else:
            prior=(backup/name).read_bytes()
            if digest(prior)!=meta["old"]:
                raise RuntimeError("backup integrity failure")
            write_atomic(target,prior,runid,meta["mode"])
    print(json.dumps({"classification":"MAIN_ONLY_ROLLBACK_VERIFIED",
          "restored_files":len(NAMES),"passenger_restart":False,
          "protected_subsites_modified":False},sort_keys=True))

if __name__=="__main__":
    try:
        mode=sys.argv[1]
        runid=sys.argv[2]
        if mode=="deploy" and len(sys.argv)==3:
            payload=json.load(sys.stdin)
            deploy(runid,payload)
        elif mode=="rollback" and len(sys.argv)==3:
            rollback(runid)
        else:raise RuntimeError("unsupported command")
    except Exception as exc:
        print(json.dumps({"classification":"MAIN_ONLY_RELEASE_REFUSED",
            "error_type":type(exc).__name__,"passenger_restart":False},sort_keys=True))
        raise SystemExit(1)
