#!/usr/bin/env python3
"""Read-only, redacted diagnostics of factory cron categories and historical log errors."""
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
st = ops.lstat()
assert stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode) and st.st_uid == os.geteuid()
cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
assert cron.returncode == 0 or "no crontab for" in cron.stderr.lower()
lines = [ln for ln in cron.stdout.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
categories = {
    "factory_single_product": r"single-product-runtime|SAEIT_SINGLE_PRODUCT_FACTORY_V1",
    "factory_forty_families": r"factory[-_]40|family[-_]master|build50",
    "factory_research": r"stage[2-6]|research-navigator|agri200|qc1000",
    "factory_autonomous": r"autonomous-product-runtime|factory_vps_product_cycle",
    "owner500": r"OWNER500|owner500",
    "mojprop_or_trading": r"mojprop|moj.trade|omega|signal",
    "commerce_or_tron": r"mojplaywin|tron|checkout|storefront",
    "mojcoin": r"mojcoin|living.cities|moj.coin",
}
hits = {key: sum(bool(re.search(pat, ln, re.I)) for ln in lines) for key,pat in categories.items()}
matched = sum(any(re.search(pat,ln,re.I) for pat in categories.values()) for ln in lines)
target = ops / "master-agent/cycle.log"
log = {"status": "absent", "content_printed": False}
try:
    v = target.lstat()
except FileNotFoundError:
    pass
else:
    if v.st_uid != os.geteuid() or not stat.S_ISREG(v.st_mode):
        log["status"] = "unsafe"
    else:
        log["status"] = "present"
        log["age_hours_band"] = ("<1" if time.time()-v.st_mtime < 3600
                                 else "1-24" if time.time()-v.st_mtime < 86400
                                 else "1-72" if time.time()-v.st_mtime < 72*3600 else ">72")
        log["size_band"] = ("0" if v.st_size == 0 else "<=64KiB" if v.st_size <= 65536
                            else "<=1MiB" if v.st_size <= 1048576 else ">1MiB")
        with target.open("rb") as f:
            f.seek(max(0,v.st_size - 131072))
            sample = f.read(131072).decode("utf-8", "replace").lower()
        markers = {
            "disk_full": ("no space left on device", "disk quota exceeded"),
            "sqlite_lock": ("database is locked",),
            "traceback": ("traceback (most recent call last)",),
            "permission": ("permission denied",),
            "backup_failure": ("backup failed", "backup_error", "restore failed"),
            "tick_failure": ("tick_exit_failure", "factory_run_error"),
            "successful_cycle": ("cycle_completed", "factory_tick_ok", "factory_run_completed"),
        }
        log["last_128k_marker_counts"] = {
            key: sum(sample.count(item) for item in needles)
            for key,needles in markers.items()
        }
        log["sample_limit_bytes"] = 131072
out = {"schema": "owner.factory.rootcause.redacted.readonly.v1",
       "active_cron_total": len(lines),
       "classified_cron_markers": hits,
       "other_cron_lines": len(lines) - matched,
       "master_log_abstract": log,
       "cron_edited": False,
       "log_edited": False,
       "service_started": False,
       "customer_data_accessed": False,
       "backups_touched": False,
       "delete_allowed": False}
print("FACTORY_ROOTCAUSE_METADATA="+json.dumps(out,sort_keys=True,separators=(",",":")))
