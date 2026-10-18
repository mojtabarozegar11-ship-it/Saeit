#!/usr/bin/env python3
"""Atomic update of MojPlayWin's dedicated crypto/index.php ONLY.

Requires SHA256 matching the explicitly approved prior live file. Never updates
any shared Django/Passenger/router/child site file, DB or .htaccess. Requires
payment enabled.flag absent, with an independent private rollback copy.
"""
import hashlib
import os
import pathlib
import sys

WEB=pathlib.Path("/home/zomorod2/mojplaywin.com")
FOLDER=WEB/"checkout"/"crypto"
TARGET=FOLDER/"index.php"
PRIVATE=pathlib.Path("/home/zomorod2/.mojplaywin-crypto-payments-v1")
BACKUP=PRIVATE/"index.php.previous"
TEMP=FOLDER/".moj-index-staged.tmp"
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def guard():
    for path in (WEB,FOLDER,PRIVATE):
        if path.is_symlink() or not path.is_dir():
            raise RuntimeError("Protected main-site folder missing or symlinked.")
    if TARGET.is_symlink() or not TARGET.is_file() or TARGET.stat().st_size>300000:
        raise RuntimeError("Prior crypto entrypoint missing or invalid.")
    if (PRIVATE/"enabled.flag").exists() or (PRIVATE/"enabled.flag").is_symlink():
        raise RuntimeError("Never hot-deploy while customer payments are enabled.")
    if BACKUP.exists() or BACKUP.is_symlink() or TEMP.exists() or TEMP.is_symlink():
        raise RuntimeError("Unresolved previous attempt detected; manual inspect required.")

def put_exclusive(path, content, mode):
    fd=os.open(str(path),os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,"O_NOFOLLOW",0),mode)
    with os.fdopen(fd,"wb") as f:
        f.write(content);f.flush();os.fsync(f.fileno())
    os.chmod(path,mode)

def apply(stage, before, after):
    guard()
    if stage.is_symlink() or not stage.is_file() or stage.stat().st_size>300000:
        raise RuntimeError("Unsafe stage.")
    if sha(TARGET)!=before or sha(stage)!=after:
        raise RuntimeError("Refusing unknown production bytes/source SHA mismatch.")
    original=TARGET.read_bytes()
    put_exclusive(BACKUP,original,0o600)
    try:
        put_exclusive(TEMP,stage.read_bytes(),0o644)
        os.replace(TEMP,TARGET)
    except BaseException:
        if TEMP.is_file() and not TEMP.is_symlink():TEMP.unlink()
        raise
    if sha(TARGET)!=after:
        raise RuntimeError("On-host gateway replacement hash mismatch.")
    print("ISOLATED_MAIN_DOMAIN_GATEWAY_UPDATED=true")
    print("PRODUCTION_PAYMENT_ENABLED=false")
    print("PROTECTED_SUBSITES_CODE_CHANGED=false")

def rollback(now,previous):
    for x in (WEB,FOLDER,PRIVATE):
        if x.is_symlink() or not x.is_dir():raise RuntimeError("Unsafe folder")
    if (PRIVATE/"enabled.flag").exists():
        raise RuntimeError("Payment is enabled; refusing unsafe hot rollback.")
    if not BACKUP.is_file() or BACKUP.is_symlink() or sha(BACKUP)!=previous:
        raise RuntimeError("Private rollback file missing or corrupted.")
    if not TARGET.is_file() or TARGET.is_symlink() or sha(TARGET)!=now:
        raise RuntimeError("Gateway modified since update; refusing rollback.")
    if TEMP.exists() or TEMP.is_symlink():
        raise RuntimeError("Unexpected temporary deployment state.")
    put_exclusive(TEMP,BACKUP.read_bytes(),0o644)
    os.replace(TEMP,TARGET)
    if sha(TARGET)!=previous:raise RuntimeError("Rollback integrity failure.")
    BACKUP.unlink()
    print("ISOLATED_MAIN_DOMAIN_GATEWAY_ROLLED_BACK=true")

if __name__=="__main__":
    if len(sys.argv)!=5 or sys.argv[1] not in ("apply","rollback"):
        raise SystemExit("Usage: update.py apply|rollback stagedphp sha_old sha_new")
    mode,file,old,new=sys.argv[1:]
    if mode=="apply":apply(pathlib.Path(file),old,new)
    else:rollback(new,old)
