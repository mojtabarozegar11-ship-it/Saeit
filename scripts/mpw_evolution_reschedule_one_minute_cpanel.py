"""Reschedule ONLY the already-running MojPlayWin private evolution cron to every minute.

No webroot, Django, Passenger, finance, tenant or other cron modifications.
Fails closed unless original known hourly job and private source are proven.
"""
from __future__ import annotations
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone

ROOT = Path("/home/zomorod2/.private_mojplaywin_main_agents")
STAGE = ROOT / "v91_verified_main_port_20261018"
RUNTIME = ROOT / "evolution_runtime_20261018"
AGENT_STATE = STAGE / "operator_state"
DEST = STAGE / "mpw_v91_port" / "evolution.py"
MARK = "# MPW_PRIVATE_EVOLUTION_MAIN_ONLY_20261018"
OWNER_FLAG = "MPW_V91_MAIN_ONLY_PRIVATE_20261018"


def require(yes, error):
    if not yes:
        raise RuntimeError(error)


def private_dir(directory):
    return directory.is_dir() and not directory.is_symlink() and not (directory.stat().st_mode & 0o077)


def cron_read(binary):
    p = subprocess.run([binary, "-l"], capture_output=True, text=True, timeout=12)
    require(p.returncode == 0, "EXISTING_CRONTAB_UNAVAILABLE")
    return p.stdout


def cron_lines(original, flock, python):
    tail = (f"{flock} -n {RUNTIME}/cron.lock {python} -B {DEST} --once "
            f"> {RUNTIME}/last_cycle.log 2>&1 {MARK}")
    old_line = "59 * * * * " + tail
    new_line = "* * * * * " + tail
    lines = original.splitlines(keepends=True)
    positions = [i for i, line in enumerate(lines) if MARK in line]
    require(len(positions) == 1, "EVOLUTION_CRON_NOT_UNIQUE")
    position = positions[0]
    actual = lines[position].rstrip("\r\n")
    require(actual in (old_line, new_line), "UNKNOWN_EVOLUTION_CRON_COMMAND")
    desired = original if actual == new_line else "".join(
        new_line + ("\r\n" if lines[i].endswith("\r\n") else "\n") if i == position else line
        for i, line in enumerate(lines))
    # Everything but the single five-field cron schedule must remain byte-for-byte unchanged.
    require(desired.replace(new_line, old_line, 1) == original
            if actual == old_line else desired == original,
            "UNRELATED_CRON_MUTATION")
    return desired, actual == new_line


def read_report():
    p = RUNTIME / "last_report.json"
    require(p.is_file() and not p.is_symlink() and p.stat().st_size < 30000,
            "PRIVATE_EVOLUTION_REPORT_MISSING")
    row = json.loads(p.read_text(encoding="utf-8"))
    require(row.get("tenant") == "mojplaywin-main"
            and row.get("status") == "active_private_learning"
            and row.get("master_generation") == 64
            and row.get("auto_published") is False
            and row.get("self_modified_code") is False
            and row.get("shared_runtime_modified") is False
            and row.get("executed_financial_actions") == 0,
            "EVOLUTION_ISOLATION_NOT_VERIFIED")
    return row


def main():
    os.umask(0o077)
    require(getpass.getuser() == "zomorod2", "INVALID_CPANEL_IDENTITY")
    require(all(private_dir(p) for p in (ROOT, STAGE, AGENT_STATE, RUNTIME)),
            "PRIVATE_CPANEl_STAGE_NOT_VERIFIED")
    enabled = AGENT_STATE / "enabled"
    require(enabled.is_file() and not enabled.is_symlink()
            and enabled.read_text(encoding="utf-8").strip() == OWNER_FLAG,
            "PRIVATE_MASTER_OWNER_FLAG_DISABLED")
    require(DEST.is_file() and not DEST.is_symlink(), "PRIVATE_EVOLUTION_MODULE_MISSING")
    report = read_report()
    cron = shutil.which("crontab")
    flock = shutil.which("flock")
    python = shutil.which("python3")
    require(bool(cron and flock and python), "CRON_EXECUTABLES_UNAVAILABLE")
    original = cron_read(cron)
    desired, already = cron_lines(original, flock, python)
    if not already:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = RUNTIME / f"cron_before_every_minute_{stamp}.txt"
        require(not backup.exists() and not backup.is_symlink(), "CRON_BACKUP_COLLISION")
        fd = os.open(str(backup), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(original)
            handle.flush()
            os.fsync(handle.fileno())
        require(cron_read(cron) == original, "CRON_CHANGED_DURING_PREFLIGHT")
        installed = False
        try:
            p = subprocess.run([cron, "-"], input=desired, capture_output=True,
                               text=True, timeout=12)
            require(p.returncode == 0, "CRON_INSTALL_FAILED")
            installed = True
            require(cron_read(cron) == desired, "CRON_READBACK_MISMATCH")
        except BaseException:
            if installed:
                subprocess.run([cron, "-"], input=original, capture_output=True,
                               text=True, timeout=12)
            raise
    check = cron_read(cron)
    after, is_minutely = cron_lines(check, flock, python)
    require(is_minutely and after == check and check == desired,
            "MINUTELY_SCHEDULE_NOT_PROVEN")
    verified = read_report()
    print(json.dumps({
        "status": "MPW_PRIVATE_EVOLUTION_EVERY_MINUTE_ACTIVE",
        "tenant": "mojplaywin-main", "schedule": "* * * * *",
        "evolution_epoch_before_next_cron": verified.get("epoch"),
        "master_generation": verified["master_generation"],
        "active_policy": verified.get("active_policy"),
        "verified_outcomes": verified.get("verified_outcome_count"),
        "prior_cron_entries_preserved_exactly": True,
        "no_public_site_or_payment_change": True,
        "shared_passenger_restarted": False,
        "previously_minutely": already
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
