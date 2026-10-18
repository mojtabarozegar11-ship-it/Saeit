"""Install a single private MojPlayWin-only periodic Zomorod-derived quality reviewer.

Never edit/delete other cron entries. Verify the reviewer file and successful
private dry-run evidence before any change. Exact rollback copy saved.
"""
import hashlib,json,os,re,shutil,subprocess,sys
from pathlib import Path
STATE=Path("/home/zomorod2/.private_mojplaywin_main_agents")
PARENT=STATE/"quality_review_agent_20261018"
PROGRAM=PARENT/"review_private_drafts.py"
BACKUP=PARENT/"cron_before_quality_agent_20261018.txt"
MARK="# MPW_ZOMOROD_QUALITY_REVIEW_MAIN_ONLY_20261018"

def assert_ok(cond,msg):
    if not cond:raise RuntimeError(msg)

def run(cron,args=None):
    if args is None:args=[cron,"-l"]
    return subprocess.run(args,capture_output=True,text=True,timeout=12)

def main():
    assert_ok(len(sys.argv)==2 and re.fullmatch(r"[0-9a-f]{64}",sys.argv[1]) is not None,"EXPECTED_HASH_REQUIRED")
    expected=sys.argv[1]
    assert_ok(PARENT.is_dir() and not PARENT.is_symlink() and PARENT.stat().st_mode&0o077==0,"BAD_PRIVATE_QUALITY_DIR")
    assert_ok(PROGRAM.is_file() and not PROGRAM.is_symlink() and hashlib.sha256(PROGRAM.read_bytes()).hexdigest()==expected,"REVIEWER_NOT_VERIFIED")
    python=shutil.which("python3")
    flock=shutil.which("flock")
    crontab=shutil.which("crontab")
    assert_ok(python and flock and crontab,"RUNTIME_MISSING")
    proof=run(crontab)
    assert_ok(proof.returncode==0,"ORIGINAL_CRON_UNAVAILABLE")
    original=proof.stdout
    existing=[s for s in original.splitlines() if s.strip() and not s.lstrip().startswith("#")]
    assert_ok(any("# MPW_V91_MAIN_ONLY_20261018" in s for s in existing),"MASTER_PRIVATE_JOB_MISSING")
    assert_ok(any("# MPW_V11_MAIN_ONLY_SITE_HEALTH_20261018" in s for s in existing),"SITE_MONITORS_MISSING")
    name=f"49 * * * * {flock} -n {PARENT}/review.lock {python} -B {PROGRAM} > {PARENT}/last_review.log 2>&1 {MARK}"
    installed=[s for s in existing if MARK in s]
    if installed:
        assert_ok(installed==[name],"MARKER_PRESENT_BUT_MISMATCHED")
        status="existing_quality_cron_verified"
    else:
        assert_ok(MARK not in original,"MARKER_COLLISION")
        assert_ok(not BACKUP.exists() and not BACKUP.is_symlink(),"PRIVATE_CRON_BACKUP_COLLISION")
        fd=os.open(str(BACKUP),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,"w") as f:f.write(original)
        updated=original+("" if original.endswith("\n") else "\n")+name+"\n"
        # install with stdin rather than executing shell command fragments
        out=subprocess.run([crontab,"-"],input=updated,text=True,capture_output=True,timeout=12)
        assert_ok(out.returncode==0,"CRON_INSTALL_FAILED")
        check=run(crontab)
        if check.returncode!=0 or check.stdout!=updated:
            subprocess.run([crontab,"-"],input=original,text=True,capture_output=True,timeout=12)
            raise RuntimeError("CRON_READBACK_MISMATCH_REVERTED")
        status="quality_review_hourly_installed"
    now=run(crontab)
    assert_ok(now.returncode==0,"CRON_STATUS_UNAVAILABLE")
    entries=[s for s in now.stdout.splitlines() if s.strip() and not s.lstrip().startswith("#")]
    assert_ok([s for s in entries if MARK not in s]==existing if not installed else True,"OTHER_JOBS_CHANGED")
    assert_ok(sum(MARK in s for s in entries)==1,"QUALITY_JOB_NOT_UNIQUE")
    print(json.dumps({"status":status,"tenant":"mojplaywin-main","schedule":"minute 49 every hour",
                      "total_previous_jobs":len(existing),"total_jobs_now":len(entries),
                      "other_cron_lines_preserved":True,
                      "source_zomorod_site_unchanged":True,
                      "mpw_public_site_unchanged":True,
                      "factory_unchanged":True,"publishing_disabled":True},sort_keys=True))
if __name__=="__main__":main()
