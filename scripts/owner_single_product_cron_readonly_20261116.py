#!/usr/bin/env python3
"""Safe status check for the existing single-product Cron without invoking it."""
import json
import os
import pwd
import re
import stat
import subprocess
import time
from pathlib import Path

assert pwd.getpwuid(os.geteuid()).pw_name == "githubops"
ops = Path("/home/githubops/factory-runtime/operations")
s = ops.lstat()
assert stat.S_ISDIR(s.st_mode) and s.st_uid == os.geteuid()
cron = subprocess.run(["crontab","-l"],capture_output=True,text=True,timeout=8)
assert cron.returncode == 0, "NO_CRONTAB_ACCESS"
lines = [line for line in cron.stdout.splitlines()
         if line.strip() and not line.lstrip().startswith("#")
         and ("single-product-runtime" in line or "SAEIT_SINGLE_PRODUCT_FACTORY_V1" in line)]
runner = ops / "single-product-runtime/run-single-product-cycle.sh"
logpath = ops / "single-product-cycle.log"
out = {"schema":"owner.factory.single_product_cron.readonly.v1",
       "matching_active_cron_lines":len(lines),
       "cron_marker_count":sum("SAEIT_SINGLE_PRODUCT_FACTORY_V1" in row for row in lines),
       "cron_contains_expected_55s_timeout":sum("/usr/bin/timeout 55s" in row for row in lines),
       "cron_contains_flock":sum("flock" in row for row in lines),
       "cron_has_pause_hold_guard":sum(bool(re.search(r"PAUSE|HOLD|DISABLE|STOP",row,re.I)) for row in lines),
       "runner_state":"absent","log_state":"absent",
       "log_age_minutes":None,"last_32k_error_counts":None,
       "cron_journal_available":False,"cron_journal_recent_single_product_invocations":None,
       "scheduler_changed":False,"worker_invoked_by_audit":False,"logs_changed":False,
       "backups_touched":False,"business_data_read":False,"costs_incurred":False}
for key,p in (("runner_state",runner),("log_state",logpath)):
    try:
        z=p.lstat()
        out[key] = ("safe_file" if stat.S_ISREG(z.st_mode) and z.st_uid==os.geteuid()
                    else "unsafe_type_or_owner")
    except FileNotFoundError:
        pass
if out["log_state"] == "safe_file":
    z=logpath.stat()
    out["log_age_minutes"]=int(max(0,time.time()-z.st_mtime)//60)
    with logpath.open("rb") as f:
        f.seek(max(0,z.st_size-32768))
        tail=f.read(32768).decode("utf-8","replace")
    groups = {
        "python_traceback":r"Traceback \(most recent call last\)",
        "file_missing":r"No such file or directory|FileNotFoundError",
        "database_locked":r"database is locked|OperationalError",
        "permission":r"Permission denied|PermissionError",
        "timeout_or_killed":r"timed out|Terminated|Killed",
        "shell_failure":r"command not found|syntax error|unbound variable"
    }
    out["last_32k_error_counts"] = {k:len(re.findall(v,tail,re.I)) for k,v in groups.items()}
j=subprocess.run(["journalctl","-t","CRON","--since","10 minutes ago","--no-pager","--output=cat"],
                 capture_output=True,text=True,timeout=9)
if j.returncode == 0 and len(j.stdout) < 300000:
    out["cron_journal_available"]=True
    rows=j.stdout.splitlines()[-3000:]
    out["cron_journal_recent_single_product_invocations"]=sum(
        "(githubops) CMD" in row and "single-product-runtime/" in row
        for row in rows)
print("SINGLE_PRODUCT_CRON_METADATA="+json.dumps(out,sort_keys=True,separators=(",",":")))
