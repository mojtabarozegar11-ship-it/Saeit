"""Install and run only MojPlayWin's evidence-based evolution in private cPanel staging.

Read one SHA-verified tar.gz from stdin. Nothing in webroot, shared Passenger,
payments, products, other tenants, the original V91 or VPS factory is touched.
"""
from __future__ import annotations
import getpass
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

HOME = Path("/home/zomorod2")
ROOT = HOME / ".private_mojplaywin_main_agents"
STAGE = ROOT / "v91_verified_main_port_20261018"
STATE = STAGE / "operator_state"
DEST = STAGE / "mpw_v91_port" / "evolution.py"
RUNTIME = ROOT / "evolution_runtime_20261018"
MARK = "# MPW_PRIVATE_EVOLUTION_MAIN_ONLY_20261018"
FLAG = "MPW_V91_MAIN_ONLY_PRIVATE_20261018"


def require(condition, name):
    if not condition:
        raise RuntimeError(name)


def private(path):
    return path.is_dir() and not path.is_symlink() and (path.stat().st_mode & 0o077) == 0


def read_crontab(cron):
    result = subprocess.run([cron, "-l"], text=True, capture_output=True, timeout=12)
    require(result.returncode == 0, "EXISTING_CRONTAB_UNAVAILABLE")
    return result.stdout


def stage_source(src):
    require(private(ROOT) and private(STAGE) and private(STATE),
            "MPW_ISOLATED_PRIVATE_STAGE_MISSING")
    require((STAGE / "mpw_v91_port" / "ORIGIN.json").is_file(),
            "VERIFIED_V91_ORIGIN_MISSING")
    enabled = STATE / "enabled"
    require(enabled.is_file() and not enabled.is_symlink() and enabled.read_text().strip() == FLAG,
            "MPW_MAIN_PRIVATE_OWNER_FLAG_MISSING")
    heartbeat = STATE / "heartbeat.json"
    require(heartbeat.is_file() and not heartbeat.is_symlink() and heartbeat.stat().st_size < 10000,
            "MASTER_HEARTBEAT_MISSING")
    data = json.loads(heartbeat.read_text())
    require(data.get("tenant") == "mojplaywin-main" and data.get("master_generation") == 64
            and data.get("auto_publish") is False and data.get("factory_connected") is False,
            "MASTER_MAIN_ISOLATION_NOT_PROVEN")
    require(DEST.parent.is_dir() and not DEST.parent.is_symlink(),
            "PRIVATE_MODULE_PARENT_INVALID")
    require(not DEST.is_symlink(), "UNSAFE_EXISTING_EVOLUTION_MODULE")
    if RUNTIME.exists():
        require(private(RUNTIME), "EVOLUTION_RUNTIME_NOT_PRIVATE")
    else:
        RUNTIME.mkdir(mode=0o700)
    original = DEST.read_bytes() if DEST.exists() else None
    # Atomic replacement only for this one private module, with exact local rollback.
    fd, tmp = tempfile.mkstemp(prefix=".mpw-evolution-", dir=str(DEST.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(src)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, DEST)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)
    return original


def restore_source(old):
    if old is None:
        if DEST.exists() and not DEST.is_symlink():
            DEST.unlink()
    else:
        fd, tmp = tempfile.mkstemp(prefix=".mpw-evolution-restore-", dir=str(DEST.parent))
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(old)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, DEST)
        finally:
            if os.path.lexists(tmp):
                os.unlink(tmp)


def input_source():
    packed = sys.stdin.buffer.read(250001)
    require(len(packed) <= 250000 and bool(packed), "EVOLUTION_PACKAGE_INVALID_SIZE")
    with tarfile.open(fileobj=io.BytesIO(packed), mode="r:gz") as tar:
        members = tar.getmembers()
        require({m.name for m in members} == {"evolution.py", "manifest.json"}
                and len(members) == 2
                and all(m.isfile() and m.size <= 60000 for m in members),
                "EVOLUTION_PACKAGE_MEMBERS_REJECTED")
        src = tar.extractfile("evolution.py").read()
        manifest = json.loads(tar.extractfile("manifest.json").read())
    require(manifest.get("tenant") == "mojplaywin-main"
            and manifest.get("deployment_scope") == "private-only"
            and manifest.get("sha256") == hashlib.sha256(src).hexdigest()
            and 2000 <= len(src) < 25000, "EVOLUTION_SOURCE_SHA_MISMATCH")
    compile(src, "private_mpw_evolution.py", "exec")
    return src


def activate():
    os.umask(0o077)
    require(getpass.getuser() == "zomorod2", "INVALID_CPANEL_OWNER")
    source = input_source()
    cron = shutil.which("crontab")
    py = shutil.which("python3")
    flock = shutil.which("flock")
    require(all((cron, py, flock)), "CRON_RUNTIME_UNAVAILABLE")
    original_cron = read_crontab(cron)
    lines = [v for v in original_cron.splitlines() if v.strip() and not v.lstrip().startswith("#")]
    required = ("MPW_V91_MAIN_ONLY_20261018",
                "MPW_V11_MAIN_ONLY_SITE_HEALTH_20261018",
                "MPW_ZOMOROD_QUALITY_REVIEW_MAIN_ONLY_20261018",
                "MPW_ZOMOROD_MANAGEMENT_INTELLIGENCE_MAIN_ONLY_20261018")
    require(all(any(term in line for line in lines) for term in required),
            "PRIOR_FOUR_PRIVATE_AGENT_CYCLES_UNVERIFIED")
    entry = (f"59 * * * * {flock} -n {RUNTIME}/cron.lock {py} -B {DEST} --once "
             f"> {RUNTIME}/last_cycle.log 2>&1 {MARK}")
    existing = [line for line in lines if MARK in line]
    require(not existing or existing == [entry], "EXISTING_EVOLUTION_JOB_MISMATCH")
    old = None
    source_installed = False
    cron_changed = False
    try:
        old = stage_source(source)
        source_installed = True
        require(hashlib.sha256(DEST.read_bytes()).hexdigest() == hashlib.sha256(source).hexdigest(),
                "INSTALLED_EVOLUTION_SHA_MISMATCH")
        if not existing:
            backup = RUNTIME / "cron_before_evolution_20261018.txt"
            require(not backup.is_symlink(), "CRON_BACKUP_SYMLINK")
            if backup.exists():
                require(backup.is_file() and backup.stat().st_size <= 250000
                        and not (backup.stat().st_mode & 0o077)
                        and backup.read_text() == original_cron,
                        "CRON_BACKUP_DIFFERS_FROM_CURRENT_JOBS")
            else:
                fd = os.open(str(backup), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, "w") as f:
                    f.write(original_cron)
            require(read_crontab(cron) == original_cron, "CRON_CHANGED_DURING_PREFLIGHT")
            target = original_cron + ("" if original_cron.endswith("\n") else "\n") + entry + "\n"
            p = subprocess.run([cron, "-"], input=target, text=True,
                               capture_output=True, timeout=12)
            require(p.returncode == 0, "CRON_INSTALL_FAILED")
            cron_changed = True
            require(read_crontab(cron) == target, "CRON_READBACK_FAILED")
        result = subprocess.run([py, "-B", str(DEST), "--once"],
                                text=True, capture_output=True, timeout=40)
        require(result.returncode == 0, "PRIVATE_EVOLUTION_FIRST_CYCLE_FAILED")
        payload = json.loads(result.stdout)
        require(payload.get("status") == "active_private_learning"
                and payload.get("epoch", 0) >= 1,
                "PRIVATE_EVOLUTION_RESULT_UNVERIFIED")
        status_path = RUNTIME / "last_report.json"
        require(status_path.is_file() and not status_path.is_symlink(),
                "PRIVATE_EVOLUTION_REPORT_MISSING")
        report = json.loads(status_path.read_text())
        require(report.get("tenant") == "mojplaywin-main"
                and report.get("status") == "active_private_learning"
                and report.get("master_generation") == 64
                and report.get("auto_published") is False
                and report.get("executed_financial_actions") == 0
                and report.get("self_modified_code") is False
                and report.get("shared_runtime_modified") is False,
                "EVOLUTION_SAFETY_INVARIANT_FAILED")
        actual = read_crontab(cron).splitlines()
        require(sum(MARK in line for line in actual) == 1, "EVOLUTION_SCHEDULE_UNVERIFIED")
        require([line for line in actual if MARK not in line] ==
                [line for line in original_cron.splitlines() if MARK not in line],
                "OTHER_CRON_JOBS_CHANGED")
        print(json.dumps({
            "status": "MPW_EVOLUTION_PRIVATE_LIVE_ACTIVE",
            "tenant": "mojplaywin-main",
            "active_policy": report.get("active_policy"),
            "decision": report.get("decision"),
            "verified_outcomes": report.get("verified_outcome_count"),
            "evolution_epoch": report.get("epoch"),
            "scheduler": "hourly_at_minute_59",
            "previous_jobs_preserved": True,
            "website_or_subsites_changed": False,
            "payment_or_products_changed": False,
            "public_publishing_enabled": False,
            "shared_passenger_restarted": False
        }, sort_keys=True))
    except BaseException:
        if cron_changed:
            subprocess.run([cron, "-"], input=original_cron,
                           text=True, capture_output=True, timeout=12)
        if source_installed:
            restore_source(old)
        raise


if __name__ == "__main__":
    activate()
