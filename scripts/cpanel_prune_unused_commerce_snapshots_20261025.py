#!/usr/bin/env python3
"""Reclaim only eleven obsolete, unreferenced commerce sandbox snapshots under cPanel staging.

Never touches live storefront roots, products, customer data, cPanel backups,
order lists, Passenger applications, or either retained runnable sandbox.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HOME = Path("/home/zomorod2")
STAGING = HOME / "Saeit-staging"
EXACT = (
    ("moj-commerce-v10-sandbox","mc10-6880988d8026"),
    ("moj-commerce-v10-sandbox","mc10-6f774717dc11"),
    ("moj-commerce-v10-sandbox","mc10-76476c84ee63"),
    ("moj-commerce-v10-sandbox","mc10-968992b02a2f"),
    ("moj-commerce-v10-sandbox","mc10-c76b20c7c550"),
    ("moj-commerce-v10-sandbox","mc10-fcc3aa05fc5d"),
    ("moj-commerce-v10-sandbox","mc10-05acaa9ac3b9"),
    ("moj-commerce-v10-sandbox","mc10-08993d786d7e"),
    ("moj-commerce-v12-sandbox","mc10-8b33ad50ceee"),
    ("moj-commerce-v12-sandbox","mc12-8595498588a0"),
    ("moj-commerce-v12-sandbox","mc12-ec28ed75f4d0"),
)
RETAIN = (
    STAGING / "moj-commerce-v10-sandbox/mc10-c3a540e57cb4",
    STAGING / "moj-commerce-v12-sandbox/mc12-20874316936e",
)
UNSAFE = {"secrets.json","credentials.json",".env",".env.local",".env.production"}

def command(argv, timeout=30):
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=True).stdout

def snapshot():
    if Path.home()!=HOME or HOME.is_symlink() or STAGING.is_symlink() or not STAGING.is_dir():
        raise RuntimeError("CPANEL_ACCOUNT_OR_STAGE_INVALID")
    for p in RETAIN:
        if p.is_symlink() or not p.is_dir() or not (p/"source.tar.gz").is_file():
            raise RuntimeError("RETAINED_STAGING_REFERENCE_MISSING")
    cron="\n".join(x for x in command(["crontab","-l"],10).splitlines()
                   if x.strip() and not x.lstrip().startswith("#"))
    proc=subprocess.run(["uapi","--output=json","PassengerApps","list_applications"],
                        capture_output=True,text=True,timeout=35,check=True)
    apps=json.dumps(json.loads(proc.stdout).get("result",{}).get("data",[]))
    refs=[]
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():continue
        for t in ("cwd","exe"):
            try:refs.append(os.readlink(p/t))
            except OSError:pass
        try:
            for fd in (p/"fd").iterdir():
                try:refs.append(os.readlink(fd))
                except OSError:pass
        except OSError:pass
    result=[]
    total_bytes=0
    for parent,ident in EXACT:
        top=STAGING/parent
        target=top/ident
        if any(p.is_symlink() or not p.is_dir() for p in (top,target)):
            raise RuntimeError("EXACT_CANDIDATE_MISSING_OR_SYMLINK")
        if target.resolve()!=target or target in RETAIN or str(target) in cron or ident in cron or str(target) in apps or ident in apps:
            raise RuntimeError("CANDIDATE_REFERENCED_BY_LIVE_SERVICE")
        if any(x==str(target) or x.startswith(str(target)+"/") for x in refs):
            raise RuntimeError("CANDIDATE_REFERENCED_BY_PROCESS")
        digest=hashlib.sha256()
        count=0
        used=0
        for root,ds,fs in os.walk(target,followlinks=False):
            for name in ds+fs:
                q=Path(root)/name
                if q.is_symlink():raise RuntimeError("SYMLINK_WITHIN_CANDIDATE")
            for name in fs:
                q=Path(root)/name
                if not q.is_file() or q.stat().st_nlink!=1 or q.stat().st_size>25*1024*1024:
                    raise RuntimeError("UNEXPECTED_CANDIDATE_FILE")
                if name.lower() in UNSAFE or q.suffix.lower() in (".sqlite",".sqlite3",".db",".sql",".pdf",".zip"):
                    raise RuntimeError("CANDIDATE_MAY_CONTAIN_USER_DATA")
                digest.update(str(q.relative_to(target)).encode())
                digest.update(str(q.stat().st_size).encode())
                count+=1;used+=q.stat().st_size
                if count>300:raise RuntimeError("CANDIDATE_OVER_FILE_LIMIT")
        if count<2 or not (2*1024**2<=used<=25*1024**2):
            raise RuntimeError("CANDIDATE_SIZE_OR_FILE_COUNT_INVALID")
        for archive in ("source.tar.gz","wheels.tar.gz"):
            if not (target/archive).is_file() or (target/archive).is_symlink():
                raise RuntimeError("SANDBOX_PROVENANCE_MISSING")
        total_bytes+=used
        result.append({"family":parent,"snapshot":ident,"files":count,"payload_bytes":used,"identity":digest.hexdigest()[:18]})
    return result,total_bytes

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true")
    args=p.parse_args()
    plan,total=snapshot()
    before=shutil.disk_usage(HOME).free
    if args.apply:
        if os.geteuid()==0:raise RuntimeError("REFUSE_ROOT")
        for parent,ident in EXACT:
            target=STAGING/parent/ident
            shutil.rmtree(target)
            if target.exists():raise RuntimeError("PARTIAL_PURGE")
        for x in RETAIN:
            if not x.is_dir() or not (x/"source.tar.gz").is_file():
                raise RuntimeError("RETAINED_SNAPSHOT_LOST")
    after=shutil.disk_usage(HOME).free
    print("CPANEL_SCOPED_UNUSED_STAGING="+json.dumps({
         "mode":"APPLY" if args.apply else "PREVIEW", "snapshot_count":len(plan),
         "files_bytes_identified":total,"candidates":plan,
         "mount_free_before":before,"mount_free_after":after,
         "retained_runnable_snapshots":len(RETAIN),
         "order_list_modified":False,"paid_products_modified":False,
         "live_site_roots_modified":False,"cPanel_backups_modified":False
    },sort_keys=True),flush=True)

if __name__=="__main__":
    try:main()
    except Exception as err:
        print("CPANEL_SCOPED_PURGE_ERROR="+type(err).__name__+":"+str(err)[:170],
              file=sys.stderr,flush=True)
        raise SystemExit(1)
# User-authorized staging generation cleanup; preview must pass exact live-reference checks first.
