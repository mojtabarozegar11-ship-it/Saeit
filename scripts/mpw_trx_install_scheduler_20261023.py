#!/usr/bin/env python3
"""Idempotent cPanel crontab install for canary-gated TRX payment reconciliation.

Preserves all existing tasks and creates a private backup. Worker is disabled
by the hard release gate until a completed merchant purchase has been proved.
"""
from __future__ import annotations
import os,subprocess,shutil,json,tempfile,fcntl
from pathlib import Path

HOME=Path("/home/zomorod2")
APP=HOME/"Saeit-staging"
STORE=HOME/".local/share"
WORKER=APP/"scripts/mpw_trx_commercial_reconcile_cron.py"
PYTHON=HOME/"virtualenv/Saeit-staging/3.11/bin/python"
MARK="# MPW_TRX_AUTORECONCILE_GUARDED_V1"

def execute(exe,args,input_data=None):
    return subprocess.run([exe,*args],input=input_data,stdout=subprocess.PIPE,
         stderr=subprocess.DEVNULL,timeout=25,check=False)

def install():
    if (os.geteuid()==0 or not APP.is_dir() or APP.is_symlink()
        or WORKER.is_symlink() or not WORKER.is_file()
        or not PYTHON.is_file() or not STORE.is_dir() or STORE.is_symlink()):
        raise RuntimeError("Unexpected merchant job environment")
    crontab=shutil.which("crontab") or "/usr/bin/crontab"
    flock=shutil.which("flock") or "/usr/bin/flock"
    if not (Path(crontab).is_file() and Path(flock).is_file()):
        raise RuntimeError("Crontab or process-lock utility is missing")
    locker=STORE/"mpw-trx-cron-install.lock"
    with locker.open("w") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        old=execute(crontab,["-l"])
        if old.returncode not in (0,1):
            raise RuntimeError("Existing cron cannot be read")
        existing=old.stdout.decode("utf8","replace") if old.returncode==0 else ""
        matches=sum(MARK in line for line in existing.splitlines())
        if matches>1:
            raise RuntimeError("Duplicate merchant payment scheduler entries")
        if matches==1:
            return {"status":"ALREADY_PRESENT","scheduler_enabled":True,
                    "public_payment_enabled":False,"schedule":"every minute"}
        backup=Path(tempfile.mkstemp(prefix="mpw-trx-crontab-",dir=str(STORE))[1])
        backup.write_text(existing,encoding="utf8")
        os.chmod(backup,0o600)
        # Exact executable and file paths, no shell injection or secret args.
        entry=(f"* * * * * {flock} -n {STORE}/mpw-trx-reconcile.lock "
               f"{PYTHON} -B {WORKER} >> {STORE}/mpw-trx-reconcile.log 2>&1 {MARK}")
        data=(existing.rstrip()+"\n"+entry+"\n").encode()
        result=execute(crontab,["-"],data)
        if result.returncode!=0:
            raise RuntimeError("Server rejected crontab update")
        verify=execute(crontab,["-l"])
        if verify.returncode!=0 or verify.stdout.count(MARK.encode())!=1:
            execute(crontab,["-"],existing.encode())
            raise RuntimeError("Crontab verification failed, restored backup")
        return {"status":"AUTORECONCILER_INSTALLED","scheduler_enabled":True,
                "public_payment_enabled":False,"schedule":"every minute",
                "backup_saved":True}

if __name__=="__main__":
    try:
        print("MPW_TRX_SCHEDULER="+json.dumps(install(),sort_keys=True))
    except Exception as exc:
        print("MPW_TRX_SCHEDULER="+json.dumps({
            "status":"BLOCKED","error_class":type(exc).__name__,
            "public_payment_enabled":False},sort_keys=True))
        raise SystemExit(2)
