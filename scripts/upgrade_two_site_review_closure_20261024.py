#!/usr/bin/env python3
"""Atomic, guarded closure upgrade for the two API-free private site masters.

Site-local operator queue + staff review closure. Does not edit payments,
checkout, emails, public HTML, native orders, or scheduled jobs.
"""
from __future__ import annotations
import fcntl
import hashlib
import importlib.util
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

HOME = Path("/home/zomorod2")
ROOT = HOME / ".private_mojplaywin_main_agents"
SITES = (
    ("zomorod", HOME/".private/zomorod-business", "/usr/bin/python3"),
    ("mojplaywin", ROOT, str(HOME/"virtualenv/Saeit-staging/3.11/bin/python")),
)
OP = "master_customer_operator_reply_20261024.py"
WORKER = "master_customer_runtime_20261024.py"
SCOPE = "two_private_master_review_closure_v1"

def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)

def sha(blob):
    return hashlib.sha256(blob).hexdigest()

def write_new(path, blob):
    fd = os.open(str(path), os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,"O_NOFOLLOW",0), 0o600)
    with os.fdopen(fd, "wb") as fp:
        fp.write(blob);fp.flush();os.fsync(fp.fileno())
    os.chmod(path, 0o600)

def run(args, timeout=95, cwd=None):
    return subprocess.run(args, timeout=timeout, cwd=cwd, capture_output=True,
                          text=True, check=False)

def validate(site, root, python):
    for fname in (OP, WORKER):
        p = root/fname
        require(p.is_file() and not p.is_symlink(), "UPGRADE_MODULE_MISSING:"+site)
        lint = run([python,"-B","-c",
                    "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf8').read())",
                    str(p)], timeout=20)
        require(lint.returncode == 0, "DEPLOYED_PYTHON_SYNTAX_FAIL:"+site)
    # Exercise the real module against synthetic, isolated memory only.
    smoke = (
      "import importlib.util,sqlite3,sys;"
      "p=sys.argv[1];site=sys.argv[2];"
      "spec=importlib.util.spec_from_file_location('review_smoke',p);"
      "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);"
      "d=sqlite3.connect(':memory:');d.execute('PRAGMA foreign_keys=ON');"
      "d.execute('CREATE TABLE customer_questions(id TEXT PRIMARY KEY,tenant TEXT,"
      "processing_status TEXT,master_processed_utc TEXT)');"
      "ticket='9'*24;"
      "d.execute('INSERT INTO customer_questions VALUES(?,?,?,?)',"
      "(ticket,site,'needs_review',None));"
      "assert len(m.list_pending_reviews(d,site))==1;"
      "assert m.save_reply(d,site,ticket,'Confirmed individual support response.','operator')=='stored';"
      "assert m.save_reply(d,site,ticket,'Confirmed individual support response.','operator')=='already_recorded';"
      "assert not m.list_pending_reviews(d,site);"
      "assert d.execute('SELECT processing_status FROM customer_questions').fetchone()[0]=='handled';"
      "print('PRIVATE_REVIEW_CLOSURE_SMOKE='+site+':PASS')"
    )
    test = run([python,"-B","-c",smoke,str(root/OP),site],timeout=25,cwd=str(root))
    require(test.returncode==0 and "PRIVATE_REVIEW_CLOSURE_SMOKE="+site+":PASS" in test.stdout,
            "PRIVATE_REVIEW_CLOSURE_SMOKE_FAILED:"+site+":"+test.stderr[-160:])
    live = run([python,"-B",str(root/WORKER),"--site",site,"--once"],
               timeout=100,cwd=str(HOME/"Saeit-staging") if site=="mojplaywin" else str(root))
    require(live.returncode==0, "REAL_MASTER_CYCLE_FAILED:"+site+":"+live.stderr[-160:])
    try:
        result = json.loads(live.stdout.splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError("MASTER_CYCLE_JSON_INVALID:"+site)
    require(result.get("tenant")==site and result.get("real_site_master_invoked") is True
            and result.get("mode")=="local_no_external_ai_api"
            and isinstance(result.get("staff_replies_completed"),int)
            and result.get("payments_mutated") is False
            and result.get("external_messages_sent") is False,
            "MASTER_CYCLE_SIDE_EFFECT_OR_IDENTITY_FAIL:"+site)
    print("LIVE_PRIVATE_REVIEW_CLOSURE="+site+":PASS")
    print("LIVE_REVIEW_WAITING="+site+":"+str(result["review_waiting"]))
    print("LIVE_STAFF_COMPLETIONS="+site+":"+str(result["staff_replies_completed"]))

def main():
    require(sys.argv[1:]==["upgrade"],"UPGRADE_ONLY")
    require(pwd.getpwuid(os.geteuid()).pw_name=="zomorod2" and Path.home()==HOME,
            "CPANEL_ACCOUNT_REQUIRED")
    require(ROOT.is_dir() and not ROOT.is_symlink() and ROOT.stat().st_mode & 0o007==0,
            "PRIVATE_ROOT_UNSAFE")
    payload = sys.stdin.buffer.read(120001)
    require(800<len(payload)<=120000,"PAYLOAD_SIZE_INVALID")
    with tarfile.open(fileobj=io.BytesIO(payload),mode="r:gz") as archive:
        members=archive.getmembers()
        require({x.name for x in members}=={"operator.py","worker.py","manifest.json"}
                and all(x.isfile() and x.size<70000 for x in members),
                "PAYLOAD_MEMBERS_UNEXPECTED")
        files={x.name:archive.extractfile(x).read() for x in members}
    meta=json.loads(files["manifest.json"].decode("utf8"))
    require(meta.get("scope")==SCOPE and meta.get("sites")==["zomorod","mojplaywin"],
            "PAYLOAD_SCOPE_INVALID")
    for name in ("operator.py","worker.py"):
        require(meta.get("new",{}).get(name)==sha(files[name]),
                "PAYLOAD_CONTENT_HASH_INVALID:"+name)
        old=meta.get("old",{}).get(name)
        require(isinstance(old,str) and len(old)==64,"OLD_SOURCE_HASH_REQUIRED:"+name)
    backup=ROOT/("master_customer_review_closure_"+str(int(time.time()))+"_"+secrets.token_hex(3))
    global_lock=ROOT/".master_customer_triage_upgrade.lock"
    require(not backup.exists() and not global_lock.is_symlink(),"BACKUP_OR_LOCK_UNSAFE")
    gfd=os.open(str(global_lock),os.O_CREAT|os.O_RDWR,0o600)
    locks=[];staged=[];replaced=[]
    try:
        fcntl.flock(gfd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for site,root,python in SITES:
            require(root.is_dir() and not root.is_symlink() and root.stat().st_mode & 0o007==0,
                    "SITE_PRIVATE_ROOT_UNSAFE:"+site)
            require(Path(python).is_file(),"PRIVATE_SITE_PYTHON_MISSING:"+site)
            local_lock=root/(".master_customer_"+site+".lock")
            require(not local_lock.is_symlink(),"SITE_LOCK_SYMLINK:"+site)
            fd=os.open(str(local_lock),os.O_CREAT|os.O_RDWR,0o600)
            fcntl.flock(fd,fcntl.LOCK_EX)
            locks.append(fd)
            inbox=root/"master_customer_inbox.sqlite3"
            require(inbox.is_file() and not inbox.is_symlink() and inbox.stat().st_mode & 0o077==0,
                    "INBOX_PRIVATE_IDENTITY_FAILED:"+site)
            for package_name,deployed_name in (("operator.py",OP),("worker.py",WORKER)):
                deployed=root/deployed_name
                require(deployed.is_file() and not deployed.is_symlink()
                        and deployed.stat().st_mode & 0o077==0
                        and sha(deployed.read_bytes())==meta["old"][package_name],
                        "DEPLOYED_PRECONDITION_CHANGED:"+site+":"+package_name)
        os.mkdir(backup,0o700)
        for site,root,python in SITES:
            for package_name,deployed_name in (("operator.py",OP),("worker.py",WORKER)):
                write_new(backup/(site+"."+package_name+".old"),(root/deployed_name).read_bytes())
        for site,root,python in SITES:
            for package_name,deployed_name in (("operator.py",OP),("worker.py",WORKER)):
                deployed=root/deployed_name
                stage=root/(".review_closure_"+str(os.getpid())+"_"+deployed_name)
                require(not stage.exists() and not stage.is_symlink(),"STAGING_COLLISION")
                write_new(stage,files[package_name]);staged.append(stage)
                require(sha(deployed.read_bytes())==meta["old"][package_name],
                        "SOURCE_RACE_DETECTED:"+site)
                os.replace(stage,deployed);replaced.append((site,deployed,package_name))
        for site,root,python in SITES:
            validate(site,root,python)
        print("TWO_SITE_REVIEW_CLOSURE_LIVE=PASS")
        print("NATIVE_ORDERS_PAYMENTS_PUBLIC_PAGES_CRON_CHANGED=NO")
        print("RECOVERABLE_PRIVATE_BACKUP_CREATED=YES")
    except BaseException:
        for site,deployed,package_name in reversed(replaced):
            older=backup/(site+"."+package_name+".old")
            if older.is_file():
                stage=deployed.with_name(".review_closure_rollback_"+str(os.getpid())+"_"+deployed.name)
                write_new(stage,older.read_bytes())
                os.replace(stage,deployed)
        print("REVIEW_CLOSURE_ATOMIC_ROLLBACK=EXECUTED",file=sys.stderr)
        raise
    finally:
        for stage in staged:
            if stage.is_file():
                stage.unlink()
        for fd in reversed(locks):
            os.close(fd)
        os.close(gfd)

if __name__=="__main__":
    main()
