"""Install only an additional MojPlayWin V11 audit cron, preserving original jobs.

Never edits web roots, Django, databases, Zomorod, factory or other cron jobs.
Before modifying crontab, creates a private exact rollback copy and checks
private source hashes and successful 11-agent production-isolated canary.
"""
import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path

ROOT=Path("/home/zomorod2/.private_mojplaywin_main_agents/site_health_v11_port_20261018")
SCRIPT=ROOT/"mpw_v91_port/site_health_v11.py"
ORIGIN=ROOT/"mpw_v91_port/heritage/zomorod_v11_site_agents_reference.php"
MARK="# MPW_V11_MAIN_ONLY_SITE_HEALTH_20261018"
BACKUP=ROOT/"cron_before_mpw_v11_activation_20261018.txt"

def require(cond,code):
    if not cond:raise RuntimeError(code)

def crontab_read(program):
    result=subprocess.run([program,"-l"],capture_output=True,text=True,timeout=10)
    require(result.returncode==0,"EXISTING_CRONTAB_UNAVAILABLE")
    return result.stdout

def main():
    require(ROOT.is_dir() and not ROOT.is_symlink() and ROOT.stat().st_mode&0o077==0,"PRIVATE_STAGE_INVALID")
    manifest=json.loads((ROOT/"manifest.json").read_text())
    for rel,p in (("mpw_v91_port/site_health_v11.py",SCRIPT),
                  ("mpw_v91_port/heritage/zomorod_v11_site_agents_reference.php",ORIGIN)):
        require(p.is_file() and not p.is_symlink(),"MISSING_SOURCE")
        require(hashlib.sha256(p.read_bytes()).hexdigest()==manifest["sha256"][rel],"SOURCE_TAMPERED")
    last=json.loads((ROOT/"last_scan.json").read_text())
    require(last.get("tenant")=="mojplaywin-main" and last.get("total_agents")==11,"CANARY_MISSING")
    require(len(last.get("runs",[]))==11,"INCOMPLETE_CANARY")
    require(set(x.get("code") for x in last["runs"])==
            {"master","content","seo","commerce","agriculture","research",
             "economic","weather","quality","media","security"},"ROLES_MISMATCH")
    require(all(x.get("status")=="ok" for x in last["runs"]),"REAL_CANARY_NOT_ALL_OK")
    python=shutil.which("python3")
    flock=shutil.which("flock")
    cron=shutil.which("crontab")
    require(python and flock and cron,"CRON_TOOL_UNAVAILABLE")
    new_job=(f"37 * * * * {flock} -n {ROOT}/cron_worker.lock {python} -B {SCRIPT} --once "
             f"> {ROOT}/last_cycle.log 2>&1 {MARK}")
    before=crontab_read(cron)
    entries=[line for line in before.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    require(any("# MPW_V91_MAIN_ONLY_20261018" in row for row in entries),"OTHER_PRIVATE_MPW_CRON_NOT_FOUND")
    require(len(entries)>=9,"EXISTING_JOBS_MISSING")
    existing=[line for line in entries if MARK in line]
    if existing:
        require(existing==[new_job],"MISMATCHED_EXISTING_AGENT_CRON")
        status="already_installed_and_verified"
        after=before
    else:
        require(MARK not in before,"DUPLICATE_MARKER")
        require(not BACKUP.exists() and not BACKUP.is_symlink(),"BACKUP_ALREADY_EXISTS")
        fd=os.open(str(BACKUP),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as save:
            save.write(before)
        after=before+("" if before.endswith("\n") else "\n")+new_job+"\n"
        try:
            result=subprocess.run([cron,"-"],input=after,text=True,capture_output=True,timeout=12)
            require(result.returncode==0,"NEW_JOB_INSTALL_FAILED")
            readback=crontab_read(cron)
            require(readback==after,"CRON_READBACK_NOT_IDENTICAL")
        except BaseException:
            subprocess.run([cron,"-"],input=before,text=True,capture_output=True,timeout=12)
            raise
        status="new_main_only_job_installed"
    confirmed=crontab_read(cron)
    orig=[row for row in before.splitlines() if row.strip() and not row.lstrip().startswith("#")]
    updated=[row for row in confirmed.splitlines() if row.strip() and not row.lstrip().startswith("#")]
    require([row for row in updated if MARK not in row]==orig,"OTHER_CRON_CHANGED")
    require(sum(MARK in row for row in updated)==1,"NEW_JOB_NOT_UNIQUE")
    print(json.dumps({"status":status,
         "site":"mojplaywin-main","role_count":11,
         "hourly_schedule":"minute 37 every hour",
         "original_cron_entry_count":len(orig),
         "current_cron_entry_count":len(updated),
         "other_jobs_preserved_byte_for_byte":True,
         "private_rollback_copy_present":BACKUP.exists(),
         "live_website_modified":False,
         "zomorod_modified":False,"factory_modified":False},sort_keys=True))

if __name__=="__main__":
    main()
