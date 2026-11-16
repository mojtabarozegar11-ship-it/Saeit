#!/usr/bin/env python3
"""Sanitized read-only inventory of VPS schedulers and running factory workers."""
import json
import os
import pwd
import stat
import subprocess
import time
from pathlib import Path

assert pwd.getpwuid(os.geteuid()).pw_name == "githubops", "WRONG_ACCOUNT"
root = Path("/home/githubops/factory-runtime")
ops = root / "operations"
for obj in (root, ops):
    s = obj.lstat()
    assert stat.S_ISDIR(s.st_mode) and not stat.S_ISLNK(s.st_mode) and s.st_uid == os.geteuid(), "ROOT_UNSAFE"
sub = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
assert sub.returncode == 0 or "no crontab for" in sub.stderr.lower(), "CRON_UNAVAILABLE"
active = [line for line in sub.stdout.splitlines() if line.strip() and not line.lstrip().startswith("#")]
tags = (
    "SAEIT_MASTER_AGENT_V1",
    "SAEIT_FACTORY_EVERY_MINUTE_V1",
    "SAEIT_FACTORY_LIFECYCLE_12_V1",
    "SAEIT_FACTORY_AUTOSTART",
    "SAEIT_AUTONOMOUS_PRODUCTS_V2",
)
kinds = {
    "legacy_loop": ("vps-only-loop.sh",),
    "master_agent": ("run-cycle.sh", "autonomous_master_loop"),
    "every_minute": ("factory-minute", "single-product-cycle"),
    "django_tick": ("factory_staging_tick",),
    "celery": ("celery",),
    "gunicorn": ("gunicorn",),
}
counts = {key: 0 for key in kinds}
proc_unknown = False
seen = 0
for p in Path("/proc").iterdir():
    if not p.name.isdecimal():
        continue
    try:
        if p.stat().st_uid != os.geteuid():
            continue
        seen += 1
        if seen > 750:
            proc_unknown = True
            break
        cmd = (p / "cmdline").read_bytes()[:32768].replace(bytes([0]), b" ").decode("utf-8", "replace").lower()
        for key, needles in kinds.items():
            if any(needle in cmd for needle in needles):
                counts[key] += 1
    except FileNotFoundError:
        continue
    except (PermissionError, OSError):
        proc_unknown = True
cron_state = subprocess.run(["systemctl", "is-active", "cron.service"],
                            capture_output=True, text=True, timeout=8)
timer_state = subprocess.run(["systemctl", "--user", "list-timers", "--all", "--no-pager", "--no-legend"],
                             capture_output=True, text=True, timeout=8)
loglabels = {
    "legacy_loop": ops / "vps-only-factory.log",
    "factory_minute": ops / "factory-minute-cycle.log",
    "master_cycle": ops / "master-agent/cycle.log",
    "production_warehouse": ops / "production-warehouse.log",
}
logs = {}
for key, path in loglabels.items():
    try:
        s = path.lstat()
        if s.st_uid != os.geteuid() or not stat.S_ISREG(s.st_mode):
            logs[key] = {"state": "unsafe"}
        else:
            age = int(max(0, time.time() - s.st_mtime))
            logs[key] = {"state": "present", "recent_10min": age < 600,
                         "age_band": "0-1h" if age < 3600 else "1-24h" if age < 86400 else ">1d",
                         "has_nonzero_bytes": s.st_size > 0}
    except FileNotFoundError:
        logs[key] = {"state": "absent"}
vfs = os.statvfs(root)
out = {
    "schema": "owner.factory.scheduler_matrix.readonly.v1",
    "cron_lines_active_total": len(active),
    "cron_known_tag_active_counts": {tag: sum(tag in line for line in active) for tag in tags},
    "cron_service_is_active": cron_state.returncode == 0 and cron_state.stdout.strip() == "active",
    "user_systemd_timer_status": ("present" if timer_state.returncode == 0 and timer_state.stdout.strip()
                                  else "none" if timer_state.returncode == 0 else "unavailable"),
    "owned_processes_scanned": seen,
    "owned_process_scan_complete": not proc_unknown,
    "factory_worker_process_counts": counts,
    "log_states": logs,
    "free_bytes": vfs.f_bavail * vfs.f_frsize,
    "legacy_factory_auto_resume_authorized": False,
    "deletion_allowed": False,
    "cron_modified": False,
    "services_changed": False,
    "logs_modified": False,
    "backups_modified": False,
}
print("FACTORY_SCHEDULER_MATRIX=" + json.dumps(out, sort_keys=True, separators=(",", ":")))
