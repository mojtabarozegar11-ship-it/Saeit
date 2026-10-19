"""Install six other MAIN-only private MojPlayWin execution robots, with canary.

Requires SHA-verified source provided as tar through stdin. No shared runtime,
payments, customer records, public webroot writes, VPS or sibling sites.
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
BASE=Path("/home/zomorod2/.private_mojplaywin_main_agents")
STAGE=BASE/"v91_verified_main_port_20261018"
EVO=BASE/"evolution_runtime_20261018"
SCRIPTS=STAGE/"scripts"
SCRIPT=SCRIPTS/"mpw_main_extended_robots.py"
BEFORE_CRON=EVO/"extended_robots_cron_before_20261018.txt"
TAG="MPW_MAIN_EXTENDED_ROBOTS_20261018"
LOCK=EVO/"extended_robots_install.lock"

def require(ok,why):
    if not ok:raise RuntimeError(why)

def private(path):
    return path.is_dir() and not path.is_symlink() and (path.stat().st_mode & 0o077)==0

def get_package():
    b=sys.stdin.buffer.read(37001)
    require(0<len(b)<=37000,"ROBOT_BUNDLE_LIMIT")
    with tarfile.open(fileobj=io.BytesIO(b),mode="r:gz") as f:
        rows=f.getmembers()
        require(len(rows)==2 and {r.name for r in rows}=={"runner.py","manifest.json"}
                and all(r.isfile() and r.size<25000 for r in rows),
                "ROBOT_BUNDLE_MEMBERS_NOT_ALLOWED")
        content=f.extractfile("runner.py").read()
        manifest=json.load(f.extractfile("manifest.json"))
    require(manifest.get("tenant")==TENANT
            and manifest.get("scope")=="mpw_six_main_readonly_execution_robots"
            and manifest.get("sha256")==hashlib.sha256(content).hexdigest(),
            "SIX_ROBOT_UNVERIFIED_SOURCE")
    compile(content,"runner.py","exec")
    return content

def atomic(path,data):
    require(not path.is_symlink(),"ROBOT_SCRIPT_SYMLINK")
    fd,temp=tempfile.mkstemp(prefix=".mpw-six-bots-",dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.lexists(temp):os.unlink(temp)

def readcron():
    p=subprocess.run(["crontab","-l"],capture_output=True,text=True,timeout=16)
    require(p.returncode==0,"CANNOT_READ_AGENT_CRON")
    return p.stdout

def main():
    os.umask(0o077)
    require(getpass.getuser()=="zomorod2","INVALID_CPANEL_MAIN_OWNER")
    buf=get_package()
    require(all(private(p) for p in (BASE,STAGE,EVO,SCRIPTS,STAGE/"operator_state")),
            "PRIVATE_ROBOT_STAGE_INVALID")
    enabled=STAGE/"operator_state/enabled"
    require(enabled.is_file() and not enabled.is_symlink()
            and enabled.read_text().strip()=="MPW_V91_MAIN_ONLY_PRIVATE_20261018",
            "ROBOT_OWNER_ENABLE_MISSING")
    original=readcron()
    guards=("MPW_V91_MAIN_ONLY_20261018",
            "MPW_V11_MAIN_ONLY_SITE_HEALTH_20261018",
            "MPW_ZOMOROD_QUALITY_REVIEW_MAIN_ONLY_20261018",
            "MPW_ZOMOROD_MANAGEMENT_INTELLIGENCE_MAIN_ONLY_20261018",
            "MPW_PRIVATE_EVOLUTION_MAIN_ONLY_20261018",
            "MPW_77_MODULES_MAIN_ONLY_20261018",
            "MPW_MAIN_PRIVATE_EXECUTION_ROBOTS_20261018")
    for marker in guards:
        require(sum(marker in r and not r.lstrip().startswith("#") for r in original.splitlines())==1,
                "DEPENDENT_ROBOT_CRON_MISSING:"+marker)
    newcron=("32 * * * * /usr/bin/flock -n "+str(EVO/"extended_robots.cron.lock")
             +" /usr/bin/python3 -B "+str(SCRIPT)+" --once > "
             +str(EVO/"extended_robots_last.log")+" 2>&1 # "+TAG)
    existing=[x for x in original.splitlines() if TAG in x]
    require(not existing or existing==[newcron],"UNOWNED_BOT_CRON_PRESENT")
    require(not SCRIPT.is_symlink() and not BEFORE_CRON.is_symlink(),
            "PRIVATE_SOURCE_OR_BACKUP_SYMLINK")
    backup=SCRIPT.read_bytes() if SCRIPT.is_file() else None
    fd=os.open(str(LOCK),os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0),0o600)
    wrote_cron=False
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        require(readcron()==original,"CRON_UPDATED_DURING_PRECHECK")
        try:
            atomic(SCRIPT,buf)
            require(hashlib.sha256(SCRIPT.read_bytes()).hexdigest()==hashlib.sha256(buf).hexdigest(),
                    "ROBOT_INSTALLED_SHA_MISMATCH")
            p=subprocess.run(["/usr/bin/python3","-B",str(SCRIPT),"--once"],
                             capture_output=True,text=True,timeout=65)
            require(p.returncode==0,"REAL_SIX_ROBOT_CANARY_FAILED:"+p.stderr[-1100:])
            runner=json.loads(p.stdout.strip().splitlines()[-1])
            report_path=EVO/"extended_robots_status_20261018.json"
            queue_path=EVO/"extended_robots_pending_release_20261018.json"
            require(report_path.is_file() and not report_path.is_symlink()
                    and queue_path.is_file() and not queue_path.is_symlink(),
                    "EXTENDED_ROBOT_REPORT_ABSENT")
            report=json.loads(report_path.read_text())
            queue=json.loads(queue_path.read_text())
            require(runner.get("robots_executed")==6
                    and report.get("status")=="six_extended_main_robots_executed"
                    and report.get("tenant")==TENANT
                    and report.get("robot_count")==6 and len(report.get("roles",[]))==6
                    and report.get("public_site_modified") is False
                    and report.get("finance_executed") is False
                    and report.get("sibling_sites_modified") is False
                    and queue.get("tenant")==TENANT
                    and queue.get("automatic_publication") is False,
                    "UNSAFE_OR_INCOMPLETE_SIX_ROBOTS")
            required={"seo_metadata","reference_origin","release_reconciliation",
                     "public_content_security","disk_capacity","publication_worklist"}
            require({r.get("name") for r in report["roles"]}==required,"SIX_ROBOT_ROLE_MISMATCH")
            if not existing:
                require(not BEFORE_CRON.exists(),"SIX_ROBOT_CRON_BACKUP_COLLISION")
                bfd=os.open(str(BEFORE_CRON),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
                with os.fdopen(bfd,"w") as f:f.write(original)
                updated=original.rstrip("\n")+"\n"+newcron+"\n"
                cp=subprocess.run(["crontab","-"],input=updated,capture_output=True,
                                  text=True,timeout=15)
                require(cp.returncode==0,"SIX_ROBOT_CRON_INSTALL_FAILED")
                wrote_cron=True
                require(readcron()==updated,"SIX_ROBOT_CRON_READBACK_FAILED")
            result=readcron()
            require(sum(TAG in x for x in result.splitlines())==1
                    and all(row in result.splitlines() for row in original.splitlines()),
                    "OTHER_PRIVATE_CRONS_CHANGED")
            print(json.dumps({"status":"SIX_ADDITIONAL_MPW_ROBOTS_ACTIVE",
              "new_robots_executed":6,
              "new_robots_healthy":report["healthy"],
              "warnings":report["warnings"],"total_main_only_robots":11,
              "scheduled":"32 * * * *",
              "other_agent_robots_and_modules_untouched":True,
              "site_changed":False,"subsites_changed":False,
              "payments_or_trades":0},sort_keys=True))
        except BaseException:
            if wrote_cron:
                subprocess.run(["crontab","-"],input=original,
                               capture_output=True,text=True,timeout=15)
            if backup is None:
                if SCRIPT.is_file() and not SCRIPT.is_symlink():SCRIPT.unlink()
            else:atomic(SCRIPT,backup)
            raise
    finally:os.close(fd)

if __name__=="__main__":main()
