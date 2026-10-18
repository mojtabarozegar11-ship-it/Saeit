"""Read-only cPanel cron inventory for MojPlayWin V91 main-only agent worker."""
import json,shutil,subprocess,os,sys
name=shutil.which("crontab")
if not name:
    print(json.dumps({"kind":"MPW_V91_CPANEL_CRON_PREFLIGHT","cron_supported":False,
                      "existing_jobs_protected":True,"wrote_changes":False}))
    sys.exit(0)
try:
    p=subprocess.run([name,"-l"],capture_output=True,text=True,timeout=12)
    if p.returncode==0:
        all_lines=p.stdout.splitlines()
        count=sum(bool(s.strip() and not s.lstrip().startswith("#") and
                       not s.lstrip().startswith(("MAILTO=","PATH=","SHELL="))) for s in all_lines)
        status="ok"
        own=sum("MPW_V91_MAIN_ONLY_20261018" in x for x in all_lines)
    elif p.returncode==1 and "no crontab" in p.stderr.lower():
        count=0
        status="no_prior_crontab"
        own=0
    else:
        status="cannot_safely_read_cron"
        count=-1
        own=0
except (OSError,subprocess.TimeoutExpired):
    status="unavailable"
    count=-1
    own=0
print(json.dumps({"kind":"MPW_V91_CPANEL_CRON_PREFLIGHT",
        "cron_supported":True,"status":status,
        "existing_noncomment_entries":count,
        "matching_mpw_main_worker_entries":own,
        "existing_jobs_protected":True,
        "wrote_changes":False},sort_keys=True))
