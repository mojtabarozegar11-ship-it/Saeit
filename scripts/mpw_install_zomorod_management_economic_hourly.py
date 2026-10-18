"""Schedule two verified MojPlayWin-only Zomorod-derived policy agents hourly.

Every existing cron entry stays byte-for-byte intact; private rollback copy
is recorded and revalidated. No public site, Zomorod or factory scheduling.
"""
import hashlib,json,os,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path("/home/zomorod2/.private_mojplaywin_main_agents/management_intelligence_20261018")
SCRIPT=ROOT/"worker.py"
BACKUP=ROOT/"cron_before_management_intelligence_20261018.txt"
MARK="# MPW_ZOMOROD_MANAGEMENT_INTELLIGENCE_MAIN_ONLY_20261018"

def require(x,m):
    if not x:raise RuntimeError(m)
def cronread(program):
    out=subprocess.run([program,"-l"],capture_output=True,text=True,timeout=12)
    require(out.returncode==0,"CRON_READ_FAILED")
    return out.stdout
def main():
    require(len(sys.argv)==2 and re.fullmatch(r"[0-9a-f]{64}",sys.argv[1]),"SOURCE_SHA_REQUIRED")
    require(ROOT.is_dir() and not ROOT.is_symlink() and not ROOT.stat().st_mode&0o077,"PRIVATE_DIR_INVALID")
    require(SCRIPT.is_file() and not SCRIPT.is_symlink() and hashlib.sha256(SCRIPT.read_bytes()).hexdigest()==sys.argv[1],"SCRIPT_SHA_INVALID")
    report_a=json.loads((ROOT/"latest_company_operations.json").read_text())
    report_b=json.loads((ROOT/"latest_economic_policy.json").read_text())
    require(report_a.get("tenant")=="mojplaywin-main" and report_b.get("tenant")=="mojplaywin-main","PRIVATE_REPORT_EVIDENCE_MISSING")
    require(report_b.get("report",{}).get("trades_or_payments_executed")==0,"UNSAFE_ECONOMIC_AGENT")
    py=shutil.which("python3");flock=shutil.which("flock");cron=shutil.which("crontab")
    require(py and flock and cron,"CRON_DEPENDENCIES_MISSING")
    before=cronread(cron)
    entries=[x for x in before.splitlines() if x.strip() and not x.lstrip().startswith("#")]
    require(any("# MPW_V91_MAIN_ONLY_20261018" in x for x in entries),"PRIVATE_MASTER_JOB_ABSENT")
    require(any("# MPW_V11_MAIN_ONLY_SITE_HEALTH_20261018" in x for x in entries),"PRIVATE_MONITORS_ABSENT")
    require(any("# MPW_ZOMOROD_QUALITY_REVIEW_MAIN_ONLY_20261018" in x for x in entries),"PRIVATE_EDITORIAL_GATE_ABSENT")
    entry=f"58 * * * * {flock} -n {ROOT}/cycle.lock {py} -B {SCRIPT} > {ROOT}/last_run.log 2>&1 {MARK}"
    old=[x for x in entries if MARK in x]
    if old:
        require(old==[entry],"DIFFERENT_EXISTING_JOB")
        status="management_economic_job_previously_installed"
    else:
        require(MARK not in before,"AMBIGUOUS_MARKER")
        require(not BACKUP.exists() and not BACKUP.is_symlink(),"BACKUP_EXISTS")
        fd=os.open(str(BACKUP),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,"w") as f:f.write(before)
        after=before+("" if before.endswith("\n") else "\n")+entry+"\n"
        response=subprocess.run([cron,"-"],input=after,text=True,capture_output=True,timeout=12)
        require(response.returncode==0,"CRON_INSTALL_FAILED")
        verify=cronread(cron)
        if verify!=after:
            subprocess.run([cron,"-"],input=before,text=True,capture_output=True,timeout=12)
            raise RuntimeError("CRON_VERIFY_FAILED_ROLLED_BACK")
        status="management_economic_hourly_job_installed"
    rows=[x for x in cronread(cron).splitlines() if x.strip() and not x.lstrip().startswith("#")]
    require(len([x for x in rows if MARK in x])==1,"JOB_NOT_UNIQUE")
    require([x for x in rows if MARK not in x]==entries if not old else True,"OTHER_CRON_JOBS_CHANGED")
    print(json.dumps({"status":status,"tenant":"mojplaywin-main",
          "two_policy_roles":["company_activity_intelligence","economic_master_policy"],
          "hourly_minute":58,"previous_jobs":len(entries),"jobs_after":len(rows),
          "previous_jobs_preserved":True,"publishing_enabled":False,
          "funds_access":False,"zomorod_modified":False,"factory_modified":False},sort_keys=True))
if __name__=="__main__":main()
