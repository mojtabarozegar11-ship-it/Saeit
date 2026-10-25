#!/usr/bin/env python3
"""Losslessly archive three exact superseded factory rollback SQLite snapshots.

Preserve all customer/shop paths, the current factory DB, and every newer rollback.
Never erase unverified data. Dry run performs a real streaming compression estimate.
"""
from __future__ import annotations
import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import time
import zlib

HOME=Path("/home/githubops")
OPS=HOME/"factory-runtime/operations"
BACKUPS=OPS/"backups"
TARGETS=("native-master-20261022T042604Z-2134354","native-master-20261022T043500Z-2141700","native-master-20261022T082246Z-2190240")
TARGET_NAME=TARGETS[0]
TARGET=BACKUPS/TARGET_NAME
SOURCE=TARGET/"sqlite-before.sqlite3"
ARCHIVE=TARGET/"sqlite-before.sqlite3.gz"
RECEIPT=TARGET/"sqlite-backup-lossless-archive-20261025.json"
MIN_SAVING=300*1024*1024

def sha_file(path):
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(4*1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()

def run(apply,run_id):
    if os.geteuid()==0 or os.getenv("USER")!="githubops":
        raise RuntimeError("NOT_GITHUBOPS")
    if not re.fullmatch(r"[0-9]{5,15}-[0-9]{1,3}",run_id):
        raise RuntimeError("BAD_RUN_ID")
    for p in (HOME,OPS,BACKUPS,TARGET):
        if not p.is_dir() or p.is_symlink():raise RuntimeError("UNSAFE_BACKUP_DIRECTORY")
    if not SOURCE.is_file() or SOURCE.is_symlink() or ARCHIVE.exists() or ARCHIVE.is_symlink() or RECEIPT.exists() or RECEIPT.is_symlink():
        raise RuntimeError("EXPECTED_RAW_BACKUP_ONLY")
    fstat=SOURCE.stat()
    if not stat.S_ISREG(fstat.st_mode) or fstat.st_nlink!=1 or not 600_000_000<=fstat.st_size<=700_000_000:
        raise RuntimeError("BACKUP_SIZE_OR_LINK_UNEXPECTED")
    if time.time()-fstat.st_mtime<36*3600:
        raise RuntimeError("BACKUP_NOT_OLD_ENOUGH")
    newer=[p for p in BACKUPS.glob("native-master-20261022*")
           if p.name>TARGET_NAME and p.is_dir() and not p.is_symlink()
           and (p/"sqlite-before.sqlite3").is_file()
           and not (p/"sqlite-before.sqlite3").is_symlink()]
    if len(newer)<3:raise RuntimeError("INSUFFICIENT_NEWER_UNCOMPRESSED_RECOVERY_BACKUPS")
    cron=subprocess.run(["crontab","-l"],capture_output=True,text=True,check=True,timeout=8).stdout
    procs=subprocess.run(["ps","-u","githubops","-o","args="],capture_output=True,text=True,check=True,timeout=8).stdout
    if TARGET_NAME in cron or TARGET_NAME in procs:
        raise RuntimeError("HISTORICAL_ROLLBACK_CURRENTLY_REFERENCED")
    if shutil.disk_usage(OPS).free<850_000_000:
        raise RuntimeError("NOT_ENOUGH_SPACE_FOR_SAFE_TRANSITION")
    lock=OPS/".rollback-snapshot-lossless-archive.lock"
    if lock.is_symlink():raise RuntimeError("UNSAFE_LOCK")
    with lock.open("a+b") as guard:
        fcntl.flock(guard.fileno(),fcntl.LOCK_EX)
        before_free=shutil.disk_usage(OPS).free
        src_digest=hashlib.sha256()
        archive_digest=hashlib.sha256()
        size=0
        archive_bytes=0
        compressor=zlib.compressobj(level=3,wbits=31)
        tmp=None
        output=None
        try:
            if apply:
                fd,tmpname=tempfile.mkstemp(prefix=".verified-lossless-backup-",dir=TARGET)
                tmp=Path(tmpname)
                os.fchmod(fd,0o600)
                output=os.fdopen(fd,"wb")
            with SOURCE.open("rb") as stream:
                for buf in iter(lambda:stream.read(4*1024*1024),b""):
                    src_digest.update(buf);size+=len(buf)
                    compressed=compressor.compress(buf)
                    if output is not None:output.write(compressed)
                    archive_bytes+=len(compressed)
                final=compressor.flush()
                archive_bytes+=len(final)
                if output is not None:
                    output.write(final);output.flush();os.fsync(output.fileno())
            if output is not None:
                output.close();output=None
            if size!=fstat.st_size or SOURCE.stat().st_mtime_ns!=fstat.st_mtime_ns:
                raise RuntimeError("ORIGINAL_BACKUP_CHANGED_DURING_COMPRESSION")
            saved=size-archive_bytes
            if saved<MIN_SAVING:
                raise RuntimeError("COMPRESSED_BACKUP_SAVING_BELOW_SAFETY_THRESHOLD")
            report={"mode":"APPLY" if apply else "DRY_RUN",
                    "snapshot":TARGET_NAME,"original_bytes":size,
                    "gzip_bytes":archive_bytes,"saving_bytes":saved,
                    "newer_uncompressed_backups_preserved":len(newer),
                    "shop_customer_and_order_data_modified":False,
                    "live_factory_database_modified":False}
            if not apply:return report
            assert tmp is not None
            if tmp.stat().st_size!=archive_bytes:raise RuntimeError("ARCHIVE_SIZE_MISMATCH")
            with gzip.open(tmp,"rb") as reader:
                check=hashlib.sha256();recovered=0
                for buf in iter(lambda:reader.read(4*1024*1024),b""):
                    check.update(buf);recovered+=len(buf)
            if recovered!=size or check.hexdigest()!=src_digest.hexdigest():
                raise RuntimeError("LOSSLESS_ROUNDTRIP_HASH_MISMATCH")
            gzip_digest=sha_file(tmp)
            if ARCHIVE.exists() or SOURCE.stat().st_mtime_ns!=fstat.st_mtime_ns:
                raise RuntimeError("DESTINATION_OR_ORIGINAL_CHANGED")
            os.rename(tmp,ARCHIVE);tmp=None
            audit={"schema":"saeit.factory.backup.lossless-archive.v1","original_file":SOURCE.name,
                   "archive_file":ARCHIVE.name,"original_sha256":src_digest.hexdigest(),
                   "gzip_sha256":gzip_digest,"original_bytes":size,
                   "compressed_bytes":archive_bytes,
                   "newer_original_snapshots_left":len(newer),
                   "recover_with":"gzip -dk sqlite-before.sqlite3.gz"}
            fd,proofname=tempfile.mkstemp(prefix=".archive-proof-",dir=TARGET)
            try:
                with os.fdopen(fd,"w",encoding="utf8") as proof:
                    json.dump(audit,proof,sort_keys=True)
                    proof.write("\n");proof.flush();os.fsync(proof.fileno())
                os.chmod(proofname,0o600)
                os.rename(proofname,RECEIPT)
            finally:
                if os.path.exists(proofname):os.unlink(proofname)
            if sha_file(SOURCE)!=src_digest.hexdigest():
                raise RuntimeError("RAW_BACKUP_CHANGED_AT_FINAL_GATE")
            SOURCE.unlink()
            report.update({"compression_hash_verified":True,
                           "archive_preserved":ARCHIVE.name,
                           "original_uncompressed_duplicate_removed":True,
                           "free_bytes_before":before_free,
                           "free_bytes_after":shutil.disk_usage(OPS).free})
            return report
        finally:
            if output is not None:output.close()
            if tmp is not None and tmp.exists():tmp.unlink()

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true")
    p.add_argument("--run-id",required=True)
    args=p.parse_args()
    try:
        reports=[]
        for target_name in TARGETS:
            TARGET_NAME=target_name
            TARGET=BACKUPS/TARGET_NAME
            SOURCE=TARGET/"sqlite-before.sqlite3"
            ARCHIVE=TARGET/"sqlite-before.sqlite3.gz"
            RECEIPT=TARGET/"sqlite-backup-lossless-archive-20261025.json"
            result=run(args.apply,args.run_id)
            reports.append(result)
            print("LOSSLESS_BATCH_ITEM="+json.dumps(result,sort_keys=True),flush=True)
        print("LOSSLESS_BATCH_SUMMARY="+json.dumps({"mode":"APPLY" if args.apply else "DRY_RUN","count":len(reports),"estimated_saving_bytes":sum(x["saving_bytes"] for x in reports),"remaining_factory_database_unchanged":True},sort_keys=True),flush=True)
    except Exception as exc:
        print("LOSSLESS_BATCH_FAILED="+type(exc).__name__+":"+str(exc)[:190],flush=True)
        raise
