#!/usr/bin/env python3
"""Guarded live install of staff-review answer handoff for two private site masters.

Atomic per-site upgrades. Exact pre-upgrade PHP hash enforced on both tenants.
No changes to order/payment databases, master Cron jobs or other site pages.
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

HOME=Path("/home/zomorod2")
ROOT=HOME/".private_mojplaywin_main_agents"
SITES=(
    ("zomorod",HOME/"public_html/ask-master",HOME/".private/zomorod-business","zomorodmelal.ir"),
    ("mojplaywin",HOME/"mojplaywin.com/ask-master",ROOT,"mojplaywin.com"),
)
OPERATOR="master_customer_operator_reply_20261024.py"
STATUS="status.php"
SCOPE="two_private_site_master_operator_reply_20261024"


def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def require(ok,why):
    if not ok:raise RuntimeError(why)


def run(args,timeout=30):
    return subprocess.run(args,capture_output=True,text=True,timeout=timeout,check=False)


def write_exclusive(path,data,mode):
    fd=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),mode)
    with os.fdopen(fd,"wb") as f:
        f.write(data);f.flush();os.fsync(f.fileno())
    os.chmod(path,mode)


def main():
    require(sys.argv[1:]==["upgrade"],"EXPECTED_UPGRADE_COMMAND")
    require(pwd.getpwuid(os.geteuid()).pw_name=="zomorod2" and Path.home()==HOME,"CPANEL_ACCOUNT_REQUIRED")
    require(ROOT.is_dir() and not ROOT.is_symlink() and ROOT.stat().st_mode & 0o007 == 0,
            "PRIVATE_BACKUP_ROOT_UNSAFE")
    stream=sys.stdin.buffer.read(125001)
    require(400<len(stream)<=125000,"INVALID_PAYLOAD_LENGTH")
    with tarfile.open(fileobj=io.BytesIO(stream),mode="r:gz") as tar:
        members=tar.getmembers()
        require({m.name for m in members}=={"status.php","operator.py","manifest.json"}
                and all(m.isfile() and m.size<80000 for m in members),"UNEXPECTED_PACKAGE_CONTENT")
        files={m.name:tar.extractfile(m).read() for m in members}
    meta=json.loads(files["manifest.json"].decode("utf8"))
    require(meta.get("scope")==SCOPE and meta.get("sites")==["zomorod","mojplaywin"],
            "PACKAGE_WRONG_SCOPE")
    old=meta.get("old_status_sha256")
    require(isinstance(old,str) and len(old)==64,"OLD_STATUS_HASH_MISSING")
    for name in ("status.php","operator.py"):
        require(meta.get("sha256",{}).get(name)==sha(files[name]),"PAYLOAD_HASH_FAILED:"+name)
    backup=ROOT/("master_customer_operator_replies_"+str(int(time.time())))
    require(not backup.exists() and not backup.is_symlink(),"BACKUP_NAME_COLLISION")
    lock=ROOT/".master_customer_operator_install.lock"
    require(not lock.is_symlink(),"INSTALL_LOCK_SYMLINK")
    fd=os.open(str(lock),os.O_CREAT|os.O_RDWR,0o600)
    written=[];staged=[];synthetic=[];site_locks=[]
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for site,web,private,domain in SITES:
            require(web.is_dir() and not web.is_symlink() and private.is_dir() and
                    not private.is_symlink() and private.stat().st_mode & 0o007==0,
                    "SITE_SCOPE_DIR_INVALID:"+site)
            present=web/STATUS
            new=private/OPERATOR
            inbox=private/"master_customer_inbox.sqlite3"
            require(present.is_file() and not present.is_symlink() and sha(present.read_bytes())==old,
                    "DEPLOYED_STATUS_IDENTITY_MISMATCH:"+site)
            require(not new.exists() and not new.is_symlink(),"OPERATOR_MODULE_ALREADY_EXISTS:"+site)
            require(inbox.is_file() and not inbox.is_symlink() and inbox.stat().st_mode & 0o077==0,
                    "PRIVATE_INBOX_IDENTITY_FAILED:"+site)
            lk=private/(".master_customer_"+site+".lock")
            require(not lk.is_symlink(),"CRON_LOCK_SYMLINK:"+site)
            sf=os.open(str(lk),os.O_CREAT|os.O_RDWR,0o600)
            fcntl.flock(sf,fcntl.LOCK_EX)
            site_locks.append(sf)
        os.mkdir(backup,0o700)
        for site,web,private,domain in SITES:
            write_exclusive(backup/(site+".status.original.php"),(web/STATUS).read_bytes(),0o600)
        for site,web,private,domain in SITES:
            status=web/STATUS
            operator=private/OPERATOR
            tmp=web/(".master_status_operator_"+str(os.getpid())+".php")
            require(not tmp.exists() and not tmp.is_symlink(),"STAGING_COLLISION:"+site)
            write_exclusive(tmp,files["status.php"],0o644);staged.append(tmp)
            lint=run(["php","-l",str(tmp)],timeout=15)
            require(lint.returncode==0,"PHP_LINT_FAILED:"+site)
            require(sha(status.read_bytes())==old,"STATUS_CHANGED_DURING_DEPLOY:"+site)
            os.replace(tmp,status);written.append((site,status,"status.php"))
            write_exclusive(operator,files["operator.py"],0o600)
            written.append((site,operator,"operator.py"))
            syntax=run(["/usr/bin/python3","-B","-c",
                        "import ast,sys;ast.parse(open(sys.argv[1]).read())",str(operator)],timeout=15)
            require(syntax.returncode==0,"PRIVATE_MODULE_PARSE_FAILED:"+site)
            require(sha(status.read_bytes())==sha(files["status.php"]) and
                    sha(operator.read_bytes())==sha(files["operator.py"]),
                    "DEPLOYED_BYTES_NOT_VERIFIED:"+site)
            spec=importlib.util.spec_from_file_location("customer_operator_"+site,operator)
            mod=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            ticket=secrets.token_hex(12)
            response="Operator synthetic response for isolated "+site+" verification."
            inbox=private/"master_customer_inbox.sqlite3"
            with sqlite3.connect(inbox,timeout=18) as db:
                db.execute("PRAGMA foreign_keys=ON")
                db.execute("INSERT INTO customer_questions(id,tenant,kind,full_name,email,question,"
                           "claimed_order_ref,initial_reply,processing_status)"
                           "VALUES(?,?,?,?,?,?,?,?,?)",
                           (ticket,site,"question","Synthetic Operator QA","operator-test@example.com",
                            "Operator QA isolated handoff request","",
                            "Synthetic QA only","needs_review"))
                db.commit()
                synthetic.append((site,inbox,ticket))
                result=mod.save_reply(db,site,ticket,response,"operator")
                require(result=="stored","OPERATOR_REPLY_NOT_SAVED:"+site)
                db.commit()
            php=r'''
            require $argv[1];
            $db=new PDO("sqlite:".$argv[2],null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
            $r=masterTrackTicket($db,$argv[3],$argv[4],"operator-test@example.com");
            if(!is_array($r) || $r["operator_answer"]!==$argv[5])exit(9);
            if(masterTrackTicket($db,$argv[3],$argv[4],"incorrect@example.com")!==null)exit(10);
            '''
            test=run(["php","-d","display_errors=0","-r",php,str(status),
                      str(inbox),site,ticket,response],timeout=22)
            require(test.returncode==0,"PRIVATE_REVIEW_TO_PUBLIC_LOOKUP_FAILED:"+site)
            public=run(["curl","-fsS","--max-time","15",
                        "https://"+domain+"/ask-master/status.php"],timeout=20)
            require(public.returncode==0 and len(public.stdout)>500,
                    "PUBLIC_TICKET_STATUS_GET_FAILED:"+site)
            print("LIVE_PRIVATE_OPERATOR_TO_TICKET_STATUS="+site+":PASS")
        write_exclusive(backup/"receipt.json",json.dumps({
            "scope":SCOPE,"old_status_sha256":old,
            "new_status_sha256":sha(files["status.php"]),
            "operator_sha256":sha(files["operator.py"]),
            "sites":["zomorod","mojplaywin"],"existing_payments_mutated":False,
            "existing_site_masters_mutated":False,"existing_cron_mutated":False,
            "external_ai_api_used":False},sort_keys=True).encode(),0o600)
        print("TWO_SITES_STAFF_REPLY_HANDOFF_LIVE=PASS")
        print("PAYMENT_ORDER_AGENT_CRON_CHANGED=NO")
    except BaseException:
        for site,path,kind in reversed(written):
            try:
                if not path.is_file() or path.is_symlink():continue
                expected=sha(files["operator.py"] if kind=="operator.py" else files["status.php"])
                if sha(path.read_bytes())!=expected:
                    print("MISMATCH_REQUIRES_MANUAL_REVIEW="+site+":"+kind);continue
                if kind=="operator.py":
                    path.unlink()
                else:
                    prior=backup/(site+".status.original.php")
                    require(prior.is_file() and sha(prior.read_bytes())==old,"BACKUP_NOT_VERIFIED:"+site)
                    restore=path.parent/(".master_reply_restore_"+str(os.getpid())+".php")
                    write_exclusive(restore,prior.read_bytes(),0o644)
                    staged.append(restore)
                    os.replace(restore,path)
                    print("ROLLED_BACK_OPERATOR_STATUS="+site+":PASS")
            except Exception:
                print("ROLLBACK_REQUIRES_REVIEW="+site+":"+kind)
        raise
    finally:
        for site,inbox,ticket in synthetic:
            try:
                with sqlite3.connect(inbox,timeout=14) as db:
                    db.execute("DELETE FROM customer_operator_replies WHERE tenant=? AND ticket_id=?",
                               (site,ticket))
                    db.execute("DELETE FROM customer_questions WHERE tenant=? AND id=? AND "
                               "email='operator-test@example.com'",(site,ticket))
                    db.commit()
            except Exception:
                print("SYNTHETIC_REVIEW_CLEANUP_REQUIRES_REVIEW="+site)
        for tmp in staged:
            try:
                if tmp.is_file() and not tmp.is_symlink():tmp.unlink()
            except OSError:pass
        for sf in reversed(site_locks):os.close(sf)
        os.close(fd)


if __name__=="__main__":
    main()
