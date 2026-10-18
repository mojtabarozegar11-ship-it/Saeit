"""Install ONLY MojPlayWin's private, self-contained telemetry collector on cPanel.

Source is SHA-attested over stdin. No public, Django, Passenger, payments,
other tenant files, or unrelated Cron entries are changed.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path("/home/zomorod2/.private_mojplaywin_main_agents")
EVO = ROOT / "evolution_runtime_20261018"
DEST = EVO / "mpw_monitor_collector.py"
CRON_MARK = "MPW_MAIN_AGENT_DASHBOARD_COLLECTOR_20261018"
CRON_COMMAND = "*/15 * * * * /usr/bin/python3 -B " + str(DEST) + " --collect >/dev/null 2>&1 # " + CRON_MARK


def ensure(value, message):
    if not value:
        raise RuntimeError(message)


def private(p):
    return p.is_dir() and not p.is_symlink() and (p.stat().st_mode & 0o077) == 0


def execute():
    ensure(len(sys.argv) == 2 and re.fullmatch(r"[0-9a-f]{64}", sys.argv[1]),
           "EXPECTED_SHA256_REQUIRED")
    ensure(private(ROOT) and private(EVO), "PRIVATE_TENANT_DIR_UNSAFE")
    ensure(os.geteuid() == ROOT.stat().st_uid, "WRONG_TENANT_USER")
    ensure(not DEST.is_symlink(), "COLLECTOR_SYMLINK_BLOCKED")
    raw = sys.stdin.buffer.read(40000)
    ensure(8000 < len(raw) < 30000, "COLLECTOR_SIZE_REJECTED")
    ensure(hashlib.sha256(raw).hexdigest() == sys.argv[1],
           "COLLECTOR_SOURCE_SHA_MISMATCH")
    compile(raw, "mpw_monitor_collector.py", "exec")
    current = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=15)
    ensure(current.returncode == 0, "CRONTAB_READ_FAILED")
    previous_cron = current.stdout
    old_lines = [x for x in previous_cron.splitlines() if CRON_MARK in x]
    ensure(len(old_lines) <= 1, "DUPLICATE_MONITOR_CRON")
    ensure(not old_lines or old_lines[0].strip() == CRON_COMMAND, "MONITOR_CRON_CONFLICT")
    old_source = DEST.read_bytes() if DEST.is_file() else None
    ensure(old_source is None or len(old_source) < 30000, "EXISTING_COLLECTOR_UNSAFE")
    os.umask(0o077)
    fd, temp_name = tempfile.mkstemp(prefix=".mpw-monitor-", dir=str(EVO))
    modified = False
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_name, DEST)
        modified = True
        # Execute now and prove that each individual inventory category exists.
        run = subprocess.run(["/usr/bin/python3", "-B", str(DEST), "--collect"],
                             capture_output=True, text=True, timeout=45)
        ensure(run.returncode == 0 and "private_history_updated" in run.stdout,
               "PRIVATE_MONITOR_COLLECTOR_FAILED:" + run.stderr[-180:])
        history = EVO / "agent_dashboard_telemetry.json"
        ensure(history.is_file() and not history.is_symlink() and
               history.stat().st_size < 300000, "PRIVATE_HISTORY_OUTPUT_INVALID")
        if not old_lines:
            replacement = previous_cron.rstrip("\n") + "\n" + CRON_COMMAND + "\n"
            update = subprocess.run(["crontab", "-"], input=replacement,
                                    text=True, capture_output=True, timeout=15)
            ensure(update.returncode == 0, "MONITOR_CRON_INSTALL_FAILED")
        final = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=True, timeout=15).stdout
        ensure(sum(CRON_MARK in x for x in final.splitlines()) == 1, "MONITOR_CRON_COUNT_INVALID")
        for line in previous_cron.splitlines():
            ensure(line in final.splitlines(), "EXISTING_CRON_ENTRY_MODIFIED")
        return {"status": "private_dashboard_collector_operational",
                "historical_snapshots_cron": "*/15 * * * *",
                "existing_crons_preserved": True, "public_files_changed": False}
    except Exception:
        if modified:
            if old_source is None:
                DEST.unlink(missing_ok=True)
            else:
                fd, rollback_name = tempfile.mkstemp(prefix=".mpw-monitor-rollback-", dir=str(EVO))
                with os.fdopen(fd, "wb") as stream:
                    stream.write(old_source)
                os.chmod(rollback_name, 0o600)
                os.replace(rollback_name, DEST)
        raise
    finally:
        if os.path.lexists(temp_name):
            os.unlink(temp_name)


if __name__ == "__main__":
    import json
    print(json.dumps(execute(), sort_keys=True))
