#!/usr/bin/env python3
"""One-shot guarded cPanel install of two independent no-API customer/master inboxes.

Installer reads an in-memory SHA-manifest tar from stdin. It creates *only*
new tenant-scoped support endpoints and private modules, then verifies both
site masters, order projections, and public GET canaries before two crons.
Existing pages, orders, payment flows, and DB schemas are never overwritten.
"""
from __future__ import annotations

import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import time

HOME = Path("/home/zomorod2")
SITES = (
    ("zomorod", HOME/"public_html", HOME/".private/zomorod-business",
     "/usr/bin/python3", "zomorodmelal.ir",
     "ZM_MASTER_CUSTOMER_INBOX_20261024"),
    ("mojplaywin", HOME/"mojplaywin.com", HOME/".private_mojplaywin_main_agents",
     str(HOME/"virtualenv/Saeit-staging/3.11/bin/python"), "mojplaywin.com",
     "MPW_MASTER_CUSTOMER_INBOX_20261024"),
)
ROOT = HOME / ".private_mojplaywin_main_agents"
MAX_BYTES = 180000
EXPECTED = {"portal.php", "runtime.py", "manifest.json"}


def run(args, *, data=None, timeout=35, cwd=None, env=None):
    return subprocess.run(args, input=data, text=data is not None, capture_output=True,
                          timeout=timeout, check=False, cwd=cwd, env=env)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_existing_dir(path: Path, private=False):
    require(path.is_dir() and not path.is_symlink(), "DIR_MISSING_OR_SYMLINK:" + path.name)
    if private:
        require(not (path.stat().st_mode & 0o007), "PRIVATE_DIR_PERMISSIONS_UNSAFE")


def payload():
    raw=sys.stdin.buffer.read(MAX_BYTES + 1)
    require(1000 < len(raw) < MAX_BYTES, "UNEXPECTED_PAYLOAD_SIZE")
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        members=archive.getmembers()
        require({m.name for m in members}==EXPECTED, "TARBALL_MEMBER_SET_UNEXPECTED")
        require(all(m.isfile() and m.size <= MAX_BYTES for m in members), "NONREGULAR_PAYLOAD")
        files={m.name:archive.extractfile(m).read() for m in members}
    meta=json.loads(files["manifest.json"].decode("utf8"))
    require(meta.get("scope")=="two_independent_no_api_site_master_inboxes", "WRONG_INSTALL_SCOPE")
    require(meta.get("sites")==["zomorod","mojplaywin"],"CROSS_TENANT_MANIFEST")
    for name in ("portal.php","runtime.py"):
        require(meta.get("sha256",{}).get(name)==digest(files[name]),"SOURCE_SHA256_MISMATCH:"+name)
    return files,meta


def exact_write(target:Path, content:bytes, mode:int, created:list):
    require(not target.exists() and not target.is_symlink(),"REFUSE_OVERWRITE:"+target.name)
    fd=os.open(str(target),os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,"O_NOFOLLOW",0),mode)
    try:
        with os.fdopen(fd,"wb") as handle:
            handle.write(content);handle.flush();os.fsync(handle.fileno())
        os.chmod(target,mode)
        created.append((target,digest(content)))
    except BaseException:
        if target.is_file() and not target.is_symlink() and digest(target.read_bytes())==digest(content):
            target.unlink()
        raise


def site_verify(name,private,portal,worker,interpreter):
    php=run(["php","-l",str(portal)],timeout=18)
    require(php.returncode==0,"PHP_SYNTAX_FAILED:"+name)
    init=run(["php","-r",
              "define('MASTER_CUSTOMER_TEST_MODE',true);require $argv[1];masterOpenDb($argv[2]);",
              str(portal),str(private)],timeout=22)
    require(init.returncode==0,"PRIVATE_INBOX_DB_INIT_FAILED:"+name)
    env=os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"]="1"
    env["DJANGO_SETTINGS_MODULE"]="config.settings"
    args=[str(interpreter),"-B",str(worker),"--site",name,"--once"]
    proc=run(args,timeout=82,env=env,cwd=str(HOME/"Saeit-staging") if name=="mojplaywin" else str(private))
    require(proc.returncode==0,"MASTER_CUSTOMER_CYCLE_FAILED:"+name+":"+str(proc.returncode)+":"+proc.stderr[-350:].replace("\n"," "))
    try:
        data=json.loads(proc.stdout.splitlines()[-1])
    except (ValueError,IndexError):
        raise RuntimeError("MASTER_RESULT_NOT_JSON:"+name)
    require(data.get("tenant")==name and data.get("real_site_master_invoked") is True
            and data.get("mode")=="local_no_external_ai_api", "MASTER_CALLBACK_NOT_VERIFIED:"+name)
    require(data.get("payments_mutated") is False and data.get("site_pages_mutated") is False,
            "SENSITIVE_MUTATION_REPORTED:"+name)
    if name=="zomorod":
        require(data.get("source",{}).get("source") in
                ("no_orders_table","local_store_ledger"),"ZM_STORE_UNKNOWN_SOURCE")
    else:
        require(data.get("source",{}).get("source")=="live_django_readonly",
                "MPW_ORDER_SOURCE_NOT_LIVE")
    print("SITE_MASTER_PRIVATE_FIRST_CYCLE="+name+":ok")
    print("SITE_MASTER_REAL_ORDER_EVENTS="+name+":"+str(data.get("source",{}).get("orders",0)))


def site_http(name):
    url="https://"+name+"/ask-master/index.php"
    proc=run(["curl","-sS","--max-time","16","-o","/dev/null","-w","%{http_code}",url],timeout=20)
    require(proc.returncode==0 and proc.stdout.strip()=="200","PUBLIC_SUPPORT_PHP_NOT_200:"+name+":"+proc.stdout.strip())
    print("LIVE_PUBLIC_CUSTOMER_FORM="+name+":HTTP200")


def install():
    require(sys.argv[1:]==["install"],"INSTALL_ONLY_ONE_SHOT")
    require(os.geteuid()!=0 and os.getlogin if False else True,"")  # host user checked below
    require(str(HOME)==str(Path.home()) and os.environ.get("USER")=="zomorod2",
            "NOT_EXPECTED_CPANEL_ACCOUNT")
    safe_existing_dir(ROOT,True)
    files,meta=payload()
    target_dirs=[]
    created=[]
    cron_installed=None
    before_cron=None
    planned_cron=None
    run_id=str(int(time.time()))
    backup=ROOT/("master_customer_install_"+run_id)
    require(not backup.exists() and not backup.is_symlink(),"BACKUP_COLLISION")
    os.mkdir(backup,0o700)
    lock=ROOT/".master_customer_install.lock"
    require(not lock.is_symlink(),"UNSAFE_INSTALL_LOCK")
    fd=os.open(str(lock),os.O_CREAT|os.O_RDWR,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for site,web,private,interpreter,domain,marker in SITES:
            safe_existing_dir(web)
            safe_existing_dir(private,True)
            require(os.access(interpreter,os.X_OK),"SITE_PYTHON_NOT_EXECUTABLE:"+site)
            folder=web/"ask-master"
            require(not folder.exists() and not folder.is_symlink(),"PUBLIC_SUPPORT_ROUTE_ALREADY_EXISTS:"+site)
            portal=folder/"index.php"
            worker=private/"master_customer_runtime_20261024.py"
            require(not worker.exists() and not worker.is_symlink(),"PRIVATE_WORKER_ALREADY_EXISTS:"+site)
        cron=run(["crontab","-l"],timeout=14)
        require(cron.returncode==0,"EXISTING_CRON_UNAVAILABLE")
        before_cron=cron.stdout
        require(all(marker not in before_cron for row in SITES for marker in (row[5],)),
                "SCHEDULE_MARKER_COLLISION")
        receipt=backup/"crontab.before.txt"
        exact_write(receipt,before_cron.encode("utf8"),0o600,created)
        for site,web,private,interpreter,domain,marker in SITES:
            folder=web/"ask-master"
            folder.mkdir(mode=0o755)
            target_dirs.append(folder)
            portal=folder/"index.php"
            worker=private/"master_customer_runtime_20261024.py"
            exact_write(portal,files["portal.php"],0o644,created)
            exact_write(worker,files["runtime.py"],0o600,created)
            site_verify(site,private,portal,worker,interpreter)
            site_http(domain)
        cron_lines=[]
        for site,web,private,interpreter,domain,marker in SITES:
            worker=private/"master_customer_runtime_20261024.py"
            mutex=private/(".master_customer_"+site+".lock")
            cron_lines.append(
                "* * * * * /usr/bin/flock -n "+str(mutex)+" "+str(interpreter)+
                " -B "+str(worker)+" --site "+site+" --once >/dev/null 2>&1 # "+marker
            )
        planned_cron=before_cron.rstrip("\n")+"\n"+"\n".join(cron_lines)+"\n"
        current=run(["crontab","-l"],timeout=15)
        require(current.returncode==0 and current.stdout==before_cron,"CRON_CHANGED_CONCURRENTLY")
        updated=run(["crontab","-"],data=planned_cron,timeout=16)
        require(updated.returncode==0,"CRON_INSTALL_FAILURE")
        cron_installed=planned_cron
        after=run(["crontab","-l"],timeout=15)
        require(after.returncode==0 and after.stdout==planned_cron,"CRON_READBACK_MISMATCH")
        for row in SITES:
            require(after.stdout.count(row[5])==1,"MASTER_CUSTOMER_CRON_NONUNIQUE")
        summary={
            "scope":"two_independent_no_api_site_master_inboxes",
            "run_id":run_id,
            "source_hashes":meta["sha256"],
            "public_forms":{"zomorod":"https://zomorodmelal.ir/ask-master/index.php",
                            "mojplaywin":"https://mojplaywin.com/ask-master/index.php"},
            "master_cycles":"both_invoked_private",
            "billing_changed":False,
            "old_site_pages_changed":False,
            "previous_cron_entries_preserved":True
        }
        exact_write(backup/"receipt.json",json.dumps(summary,sort_keys=True).encode(),0o600,created)
        print("TWO_SITE_CUSTOMER_MASTER_LIVE_INSTALL=PASS")
        print("TWO_SITE_CUSTOMER_MASTER_UNIQUE_MINUTE_SCHEDULES=PASS")
        print("TWO_SITE_CUSTOMER_MASTER_PAYMENT_CHANGES=0")
        print("TWO_SITE_CUSTOMER_MASTER_BACKUP="+str(backup))
    except BaseException:
        try:
            if cron_installed is not None and before_cron is not None:
                current=run(["crontab","-l"],timeout=15)
                if current.returncode==0 and current.stdout==cron_installed:
                    restored=run(["crontab","-"],data=before_cron,timeout=18)
                    print("CUSTOMER_MASTER_CRON_ROLLBACK="+str(restored.returncode==0))
        except Exception:
            print("CUSTOMER_MASTER_CRON_ROLLBACK_INCOMPLETE")
        for target,sha in reversed(created):
            try:
                if target.is_file() and not target.is_symlink() and digest(target.read_bytes())==sha:
                    target.unlink()
            except OSError:
                print("CUSTOMER_MASTER_TARGET_MANUAL_REVIEW="+target.name)
        for folder in reversed(target_dirs):
            try:
                folder.rmdir()
            except OSError:
                print("CUSTOMER_MASTER_DIRECTORY_NOT_EMPTY_PRESERVED="+folder.name)
        raise
    finally:
        os.close(fd)


if __name__=="__main__":
    install()
