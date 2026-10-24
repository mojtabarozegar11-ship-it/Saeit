#!/usr/bin/env python3
"""Upgrade ONLY the two private, API-free site-master customer workers.

Preserve original worker bytes and all real customer/order records. A guarded
rollback restores both original workers if live tests fail. Existing site
pages, cPanel cron, payments, checkout and VPS factory are never edited.
"""
from __future__ import annotations
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import pwd
import secrets
import sqlite3
import subprocess
import sys
import tarfile
import time

HOME=Path("/home/zomorod2")
ROOT=HOME/".private_mojplaywin_main_agents"
SITES=(
  ("zomorod",HOME/".private/zomorod-business","/usr/bin/python3"),
  ("mojplaywin",ROOT,str(HOME/"virtualenv/Saeit-staging/3.11/bin/python")),
)
NAME="master_customer_runtime_20261024.py"

def require(condition,reason):
    if not condition:raise RuntimeError(reason)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def write_new(path,raw,mode):
    fd=os.open(str(path),os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,"O_NOFOLLOW",0),mode)
    with os.fdopen(fd,"wb") as file:
        file.write(raw);file.flush();os.fsync(file.fileno())
    os.chmod(path,mode)

def run(args,*,cwd=None,timeout=80):
    return subprocess.run(args,text=True,capture_output=True,cwd=cwd,
                          timeout=timeout,check=False)

def validate_cycle(site,root,python):
    worker=root/NAME
    result=run([python,"-B",str(worker),"--site",site,"--once"],
               cwd=str(HOME/"Saeit-staging") if site=="mojplaywin" else str(root),
               timeout=90)
    require(result.returncode==0,"PRIVATE_MASTER_CYCLE_FAILED:"+site+":"+result.stderr[-180:].replace("\n"," "))
    try:
        report=json.loads(result.stdout.splitlines()[-1])
    except (ValueError,IndexError):
        raise RuntimeError("PRIVATE_MASTER_RESULT_INVALID:"+site)
    require(report.get("tenant")==site and report.get("real_site_master_invoked") is True
            and report.get("mode")=="local_no_external_ai_api","MASTER_IDENTITY_NOT_VERIFIED:"+site)
    require(report.get("payments_mutated") is False and
            report.get("site_pages_mutated") is False and
            report.get("external_messages_sent") is False,"UNEXPECTED_SIDE_EFFECT:"+site)
    return report

def main():
    require(sys.argv[1:]==["upgrade"],"UPGRADE_COMMAND_ONLY")
    require(pwd.getpwuid(os.geteuid()).pw_name=="zomorod2" and Path.home()==HOME,
            "CPANEL_IDENTITY_REQUIRED")
    require(ROOT.is_dir() and not ROOT.is_symlink() and ROOT.stat().st_mode & 0o007==0,
            "PRIVATE_BACKUP_ROOT_INVALID")
    blob=sys.stdin.buffer.read(90001)
    require(1000<len(blob)<=90000,"UNEXPECTED_MANIFEST_SIZE")
    with tarfile.open(fileobj=io.BytesIO(blob),mode="r:gz") as archive:
        members=archive.getmembers()
        require({x.name for x in members}=={"worker.py","manifest.json"} and
                all(x.isfile() and x.size<80000 for x in members),"UNEXPECTED_MANIFEST_FILES")
        files={x.name:archive.extractfile(x).read() for x in members}
    manifest=json.loads(files["manifest.json"].decode("utf8"))
    require(manifest.get("scope")=="two_private_site_master_truthful_triage" and
            manifest.get("sites")==["zomorod","mojplaywin"],"MANIFEST_SCOPE_INVALID")
    new=files["worker.py"]
    oldhash=manifest.get("old_sha256")
    require(isinstance(oldhash,str) and len(oldhash)==64 and
            manifest.get("new_sha256")==digest(new),"SOURCE_SHA256_INVALID")
    backups=ROOT/("master_customer_truthful_triage_"+str(int(time.time())))
    require(not backups.exists() and not backups.is_symlink(),"BACKUP_NAME_COLLISION")
    global_lock=ROOT/".master_customer_triage_upgrade.lock"
    require(not global_lock.is_symlink(),"UNSAFE_GLOBAL_LOCK")
    global_fd=os.open(str(global_lock),os.O_CREAT|os.O_RDWR,0o600)
    site_locks=[];changed=[];staged=[];tickets=[]
    try:
        fcntl.flock(global_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for site,root,python in SITES:
            require(root.is_dir() and not root.is_symlink() and root.stat().st_mode & 0o007==0,
                    "PRIVATE_SITE_ROOT_INVALID:"+site)
            require(Path(python).is_file() and os.access(python,os.X_OK),"PYTHON_UNAVAILABLE:"+site)
            lock=root/(".master_customer_"+site+".lock")
            require(not lock.is_symlink(),"CRON_LOCK_UNSAFE:"+site)
            fd=os.open(str(lock),os.O_CREAT|os.O_RDWR,0o600)
            fcntl.flock(fd,fcntl.LOCK_EX)
            site_locks.append(fd)
            worker=root/NAME
            require(worker.is_file() and not worker.is_symlink(),"WORKER_IDENTITY_FAILED:"+site)
            require(digest(worker.read_bytes())==oldhash,"EXISTING_WORKER_CHANGED:"+site)
            inbox=root/"master_customer_inbox.sqlite3"
            require(inbox.is_file() and not inbox.is_symlink() and
                    inbox.stat().st_mode & 0o077==0,"PRIVATE_INBOX_INVALID:"+site)
        os.mkdir(backups,0o700)
        for site,root,python in SITES:
            write_new(backups/(site+".original.py"),(root/NAME).read_bytes(),0o600)
        for site,root,python in SITES:
            worker=root/NAME
            tmp=root/(".master_customer_truthful_"+str(os.getpid())+".py")
            require(not tmp.exists() and not tmp.is_symlink(),"STAGING_PATH_COLLISION")
            write_new(tmp,new,0o600);staged.append(tmp)
            lint=run([python,"-B","-c","import ast,sys;ast.parse(open(sys.argv[1]).read())",str(tmp)],timeout=20)
            require(lint.returncode==0,"WORKER_SOURCE_NOT_PARSEABLE:"+site)
            require(digest(worker.read_bytes())==oldhash,"WORKER_CHANGED_DURING_INSTALL:"+site)
            os.replace(tmp,worker);changed.append((site,worker))
            with sqlite3.connect(root/"master_customer_inbox.sqlite3",timeout=15) as db:
                for question,state in (
                    ("QA-TRIAGE Please refund my order","needs_review"),
                    ("QA-TRIAGE My download is missing","needs_review"),
                    ("General coupon policy","handled")):
                    ticket=secrets.token_hex(12)
                    db.execute("INSERT INTO customer_questions(id,tenant,kind,full_name,email,question,"
                               "claimed_order_ref,initial_reply,processing_status)"
                               "VALUES(?,?,?,?,?,?,?,?,?)",
                               (ticket,site,"question","Triage QA","triage-test@example.com",question,
                                "","Synthetic verification only","queued"))
                    tickets.append((root,site,ticket,question,state))
                db.commit()
            report=validate_cycle(site,root,python)
            with sqlite3.connect(root/"master_customer_inbox.sqlite3",timeout=12) as db:
                for folder,tenant,ticket,question,state in tickets:
                    if tenant!=site:continue
                    row=db.execute("SELECT processing_status,master_processed_utc FROM customer_questions "
                                   "WHERE id=? AND tenant=?",(ticket,site)).fetchone()
                    require(row is not None and row[0]==state and row[1],
                            "FALSE_CUSTOMER_RESOLUTION_STILL_PRESENT:"+site+":"+state)
                pulse=db.execute("SELECT queued,review,guidance,review_older_than_day,last_success_utc "
                                 "FROM master_customer_worker_health WHERE tenant=?",(site,)).fetchone()
                require(pulse is not None and pulse[4] and pulse[1]>=2 and pulse[2]>=1,
                        "MASTER_HEALTH_HEARTBEAT_INVALID:"+site)
            print("LIVE_CUSTOMER_MASTER_TRUTHFUL_TRIAGE="+site+":PASS")
            print("LIVE_CUSTOMER_MASTER_PRIVATE_HEALTH="+site+":PASS")
            require(report["payments_mutated"] is False,"PAYMENT_MUTATION_REPORTED")
        write_new(backups/"receipt.json",json.dumps({
            "scope":"two_private_site_master_truthful_triage",
            "old_worker_sha256":oldhash,"new_worker_sha256":digest(new),
            "sites":["zomorod","mojplaywin"],"real_orders_mutated":False,
            "public_pages_mutated":False,"cron_changed":False},sort_keys=True).encode(),0o600)
        print("BOTH_SITES_NO_API_MASTER_REVIEW_FIX_LIVE=PASS")
        print("EXISTING_PAYMENT_ORDER_PUBLIC_DATA_CHANGED=NO")
    except BaseException:
        for site,worker in reversed(changed):
            try:
                if worker.is_file() and not worker.is_symlink() and digest(worker.read_bytes())==digest(new):
                    original=(backups/(site+".original.py")).read_bytes()
                    require(digest(original)==oldhash,"BACKUP_NOT_EXACT:"+site)
                    tmp=worker.parent/(".master_customer_restore_"+str(os.getpid())+".py")
                    write_new(tmp,original,0o600);staged.append(tmp)
                    os.replace(tmp,worker)
                    print("RESTORED_PRIVATE_WORKER="+site+":PASS")
                else: print("PRIVATE_WORKER_REQUIRES_REVIEW="+site)
            except Exception:
                print("PRIVATE_WORKER_REQUIRES_REVIEW="+site)
        raise
    finally:
        for root,site,ticket,question,state in tickets:
            try:
                with sqlite3.connect(root/"master_customer_inbox.sqlite3",timeout=15) as db:
                    db.execute("DELETE FROM customer_questions WHERE id=? AND tenant=? AND "
                               "email=? AND question=?",
                               (ticket,site,"triage-test@example.com",question))
                    db.commit()
            except Exception:
                print("EXACT_SYNTHETIC_CLEANUP_REQUIRES_REVIEW="+site)
        for tmp in staged:
            try:
                if tmp.is_file() and not tmp.is_symlink():tmp.unlink()
            except OSError:pass
        for fd in reversed(site_locks):
            os.close(fd)
        os.close(global_fd)

if __name__=="__main__":
    main()
