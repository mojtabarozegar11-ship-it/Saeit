"""Install and execute 5 real MojPlayWin private robots, then schedule hourly.

Self-contained trusted bootstrap; receives exactly runner.py + SHA256 manifest
through stdin. This only adds a private script, private reports/queue and ONE
new MojPlayWin-only Cron entry. It never alters Apache, Passenger, shared Django,
the public webroot, payments, VPS, or sibling sites.
"""
import fcntl
import getpass
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

TENANT="mojplaywin-main"
ROOT=Path("/home/zomorod2/.private_mojplaywin_main_agents")
STAGE=ROOT/"v91_verified_main_port_20261018"
EVO=ROOT/"evolution_runtime_20261018"
SCRIPTS=STAGE/"scripts"
TARGET=SCRIPTS/"mpw_main_private_execution_robots.py"
LOG=EVO/"robots_execution_last.log"
BACKUP=EVO/"robots_crontab_before_20261018.txt"
MARK="MPW_MAIN_PRIVATE_EXECUTION_ROBOTS_20261018"
LOCK=EVO/"robots_activation.lock"

def need(ok,why):
    if not ok:raise RuntimeError(why)

def safe(path):
    return path.is_dir() and not path.is_symlink() and not path.stat().st_mode&0o077

def package():
    raw=sys.stdin.buffer.read(35001)
    need(0<len(raw)<=35000,"INVALID_BOT_INSTALL_BUNDLE")
    with tarfile.open(fileobj=io.BytesIO(raw),mode="r:gz") as archive:
        rows=archive.getmembers()
        need(len(rows)==2 and {x.name for x in rows}=={"runner.py","manifest.json"}
             and all(x.isfile() and 0<x.size<23000 for x in rows),"UNEXPECTED_BOT_PACKAGE")
        payload=archive.extractfile("runner.py").read()
        manifest=json.load(archive.extractfile("manifest.json"))
    need(manifest.get("tenant")==TENANT
         and manifest.get("scope")=="five_main_site_only_private_execution_robots"
         and manifest.get("runner_sha256")==hashlib.sha256(payload).hexdigest(),
         "BAD_BOT_SOURCE_SIGNATURE")
    compile(payload,"runner.py","exec")
    return payload

def atomic(path,data):
    need(not path.is_symlink(),"BOT_SCRIPT_DESTINATION_SYMLINK")
    fd,tmp=tempfile.mkstemp(prefix=".mpw-bots-",dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as file:
            file.write(data);file.flush();os.fsync(file.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.lexists(tmp):os.unlink(tmp)

def cronread():
    r=subprocess.run(["crontab","-l"],capture_output=True,text=True,timeout=15)
    need(r.returncode==0,"BOT_ORIGINAL_CRON_UNAVAILABLE")
    return r.stdout

def main():
    os.umask(0o077)
    need(getpass.getuser()=="zomorod2","INVALID_CPANEL_ACCOUNT")
    payload=package()
    need(all(safe(x) for x in (ROOT,STAGE,EVO,SCRIPTS,STAGE/"operator_state")),
         "BOT_PRIVATE_OWNER_DIRECTORIES_UNSAFE")
    enabled=STAGE/"operator_state/enabled"
    need(enabled.is_file() and not enabled.is_symlink()
         and enabled.read_text().strip()=="MPW_V91_MAIN_ONLY_PRIVATE_20261018",
         "BOT_OWNER_FLAG_MISSING")
    need((EVO/"all_77_modules_last_run.json").is_file()
         and (EVO/"gen65_operational_report.json").is_file(),
         "BOT_DEPENDENT_RUNTIME_MISSING")
    need(not TARGET.is_symlink() and not BACKUP.is_symlink(),
         "BOT_SCRIPT_OR_CRON_BACKUP_SYMLINK")
    before=cronread()
    need(sum("MPW_PRIVATE_EVOLUTION_MAIN_ONLY_20261018" in row for row in before.splitlines())==1,
         "GEN65_ONE_MINUTE_SCHEDULER_NOT_FOUND")
    lines=[x for x in before.splitlines() if MARK in x]
    job=("26 * * * * /usr/bin/flock -n "+str(EVO/"robots_execution.cron.lock")
         +" /usr/bin/python3 -B "+str(TARGET)+" --once > "+str(LOG)
         +" 2>&1 # "+MARK)
    need(not lines or lines==[job],"OTHER_BOT_JOB_CANNOT_BE_OVERWRITTEN")
    previous=TARGET.read_bytes() if TARGET.is_file() else None
    handle=os.open(str(LOCK),os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0),0o600)
    wrote_cron=False
    try:
        fcntl.flock(handle,fcntl.LOCK_EX)
        need(cronread()==before,"CRON_CHANGED_DURING_BOT_ACTIVATION")
        try:
            atomic(TARGET,payload)
            need(hashlib.sha256(TARGET.read_bytes()).hexdigest()==hashlib.sha256(payload).hexdigest(),
                 "BOT_INSTALLED_SHA_MISMATCH")
            run=subprocess.run(["/usr/bin/python3","-B",str(TARGET),"--once"],
                               capture_output=True,text=True,timeout=110)
            need(run.returncode==0,"BOT_REAL_CANARY_FAILED:"+run.stderr[-800:])
            summary=json.loads(run.stdout.strip().splitlines()[-1])
            need(summary.get("status")=="five_main_robots_executed"
                 and summary.get("robots_executed")==5,"BOT_CANARY_INCOMPLETE")
            report=json.loads((EVO/"robots_execution_20261018.json").read_text())
            queue=json.loads((EVO/"robots_editorial_review_queue_20261018.json").read_text())
            need(report.get("tenant")==TENANT and report.get("robot_count")==5
                 and report.get("site_writes")==0 and report.get("subsite_writes")==0
                 and report.get("financial_actions")==0
                 and set(x.get("name") for x in report.get("roles",[]))==
                     {"main_route_observer","editorial_integrity","draft_fingerprint",
                      "editorial_review_queue","agent_runtime_watch"}
                 and queue.get("tenant")==TENANT
                 and queue.get("automated_approval") is False,
                 "BOT_REAL_PRIVATE_RESULT_UNVERIFIED")
            if not lines:
                need(not BACKUP.exists(),"BOT_BACKUP_CONFLICT")
                fd=os.open(str(BACKUP),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
                with os.fdopen(fd,"w") as f:f.write(before)
                proposed=before.rstrip("\n")+"\n"+job+"\n"
                r=subprocess.run(["crontab","-"],input=proposed,capture_output=True,text=True,timeout=15)
                need(r.returncode==0,"BOT_CRON_INSTALL_FAILED")
                wrote_cron=True
                need(cronread()==proposed,"BOT_CRON_READBACK_DIFF")
            after=cronread()
            need(sum(MARK in x for x in after.splitlines())==1
                 and all(row in after.splitlines() for row in before.splitlines()),
                 "BOT_EXISTING_JOBS_MODIFIED")
            print(json.dumps({"status":"FIVE_MAIN_ONLY_EXECUTION_ROBOTS_RUNNING",
                "tenant":TENANT,"robots_executed":5,
                "healthy":report["successful"],"warnings":report["warnings"],
                "review_tasks":len(queue["items"]),
                "schedule":"26 * * * *",
                "all_previous_crons_preserved":True,
                "gen64_gen65_existing":True,
                "public_site_changed":False,
                "subsites_changed":False,
                "payments_or_trades_executed":0},sort_keys=True))
        except BaseException:
            if wrote_cron:
                subprocess.run(["crontab","-"],input=before,text=True,capture_output=True,timeout=15)
            if previous is None:
                if TARGET.is_file() and not TARGET.is_symlink():TARGET.unlink()
            else:
                atomic(TARGET,previous)
            raise
    finally:
        os.close(handle)
if __name__=="__main__":main()
