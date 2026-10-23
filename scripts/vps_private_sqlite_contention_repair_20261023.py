#!/usr/bin/env python3
"""Guarded private VPS-only SQLite contention repair; no database writes.

The 2026-10-23 live audit confirmed that factory_staging_tick re-seeds all
agents on EVERY tick. seed_factory_agents writes update_or_create records
inside transaction.atomic, with SQLite's default 5-second timeout.
This repair preserves self-healing but only re-seeds when the master,
capabilities or fresh grants are missing. It also increases the DB busy timeout.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys

TICK_MARKER = "# AGENT_SEED_READINESS_GUARD_V1_20261023"
DB_MARKER = "# VPS_FACTORY_SQLITE_BUSY_TIMEOUT_V1_20261023"

OLD_TICK_CALL = '        call_command("seed_factory_agents")'
NEW_TICK_CALL = '''        # AGENT_SEED_READINESS_GUARD_V1_20261023
        # Read-only health checks on routine ticks; re-seed only on actual
        # absence, revocation or imminent expiry (within two hours).
        from datetime import timedelta as _factory_timedelta
        from django.utils import timezone as _factory_timezone
        from core.models import Agent as _FactoryAgent
        from core.models import AgentCapability as _FactoryCapability
        from core.models import AgentToolGrant as _FactoryGrant
        from core.management.commands.seed_factory_agents import CAPABILITIES as _factory_seed_specs
        _factory_expected = {code for code, *_ in _factory_seed_specs}
        _factory_refresh_at = _factory_timezone.now() + _factory_timedelta(hours=2)
        _factory_capabilities_ok = _FactoryCapability.objects.filter(
            code__in=_factory_expected, active=True
        ).count() == len(_factory_expected)
        _factory_grants_ok = _FactoryGrant.objects.filter(
            capability_code__in=_factory_expected,
            active=True,
            valid_until__gt=_factory_refresh_at,
        ).values("capability_code").distinct().count() == len(_factory_expected)
        _factory_master_ok = _FactoryAgent.objects.filter(
            code="factory-master-agent", active=True
        ).exists()
        if not (_factory_expected and _factory_capabilities_ok
                and _factory_grants_ok and _factory_master_ok):
            call_command("seed_factory_agents")
            self.stdout.write("FACTORY_AGENT_SEED_REFRESHED")
        else:
            self.stdout.write("FACTORY_AGENT_SEED_HEALTHY_NO_WRITE")'''

SQLITE_BLOCK = '''
# VPS_FACTORY_SQLITE_BUSY_TIMEOUT_V1_20261023
# SQLite is local to this private VPS runtime. Improve coexistence with the
# separately scheduled master/evolution agents; no journal-mode conversion.
if DATABASES["default"]["ENGINE"].endswith("sqlite3"):
    DATABASES["default"].setdefault("OPTIONS", {})["timeout"] = 45
'''

def planned_patch(path: Path, kind: str) -> str | None:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("EXPECTED_PRIVATE_FILE_MISSING_OR_SYMLINK: " + kind)
    original = path.read_text(encoding="utf-8")
    if kind == "tick":
        if TICK_MARKER in original:
            return None
        if original.count(OLD_TICK_CALL) != 1 or "def handle(" not in original:
            raise RuntimeError("TICK_SOURCE_FINGERPRINT_CHANGED")
        new = original.replace(OLD_TICK_CALL, NEW_TICK_CALL)
    else:
        if DB_MARKER in original:
            return None
        if "DATABASES" not in original or "config" not in str(path):
            raise RuntimeError("SETTINGS_SOURCE_FINGERPRINT_CHANGED")
        new = original.rstrip() + "\n" + SQLITE_BLOCK
    compile(new, str(path), "exec")
    return new

def validate(root: Path) -> None:
    script = """
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.conf import settings
from django.db import connection
from core.management.commands.factory_staging_tick import Command
from core.management.commands.seed_factory_agents import CAPABILITIES
from core.models import Agent, AgentCapability, AgentToolGrant
assert len(CAPABILITIES) > 0
assert settings.DATABASES["default"]["ENGINE"].endswith("sqlite3")
assert int(settings.DATABASES["default"]["OPTIONS"]["timeout"]) == 45
with connection.cursor() as cursor:
    cursor.execute("PRAGMA busy_timeout")
    value = int(cursor.fetchone()[0])
assert value >= 45000, value
print("FACTORY_SQLITE_TIMEOUT_VERIFIED_MS=" + str(value))
print("FACTORY_SEED_CAPABILITIES_EXPECTED=" + str(len(CAPABILITIES)))
print("FACTORY_AGENT_MASTER_PRESENT=" + str(Agent.objects.filter(code="factory-master-agent",active=True).exists()))
from datetime import timedelta
from django.utils import timezone
expected_codes = {code for code, *_ in CAPABILITIES}
threshold = timezone.now() + timedelta(hours=2)
print("FACTORY_SEED_ACTIVE_CAPABILITY_COUNT=" + str(AgentCapability.objects.filter(code__in=expected_codes,active=True).count()))
print("FACTORY_SEED_FRESH_GRANT_COUNT=" + str(AgentToolGrant.objects.filter(capability_code__in=expected_codes,active=True,valid_until__gt=threshold).values("capability_code").distinct().count()))
"""
    env = os.environ.copy()
    env.setdefault("SAEIT_ENV", "production")
    env.setdefault("MOJ_FACTORY_LOCAL_MODE", "1")
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=root, env=env, capture_output=True, text=True, timeout=90
    )
    if result.returncode != 0:
        # Never print potentially sensitive Django exception payloads.
        raise RuntimeError("DJANGO_RUNTIME_VALIDATION_FAILED")
    for line in result.stdout.splitlines():
        if line.startswith(("FACTORY_SQLITE_TIMEOUT_VERIFIED_MS=",
                            "FACTORY_SEED_CAPABILITIES_EXPECTED=",
                            "FACTORY_AGENT_MASTER_PRESENT=",
                            "FACTORY_SEED_ACTIVE_CAPABILITY_COUNT=",
                            "FACTORY_SEED_FRESH_GRANT_COUNT=")):
            print(line, flush=True)

def report_live_log(root: Path) -> None:
    # Observes actual subsequent loop ticks; never treats process presence as production.
    log = root.parent / "operations/vps-only-factory.log"
    if not log.is_file():
        print("FACTORY_POSTPATCH_LOOP_LOG_MISSING", flush=True)
        return
    result = subprocess.run(
        ["tail", "-n", "500", str(log)], capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        print("FACTORY_POSTPATCH_LOOP_LOG_UNREADABLE", flush=True)
        return
    data = result.stdout
    first_healthy = data.find("FACTORY_AGENT_SEED_HEALTHY_NO_WRITE")
    if first_healthy >= 0:
        since_healthy = data[first_healthy:]
        print("FACTORY_AFTER_FIRST_HEALTHY_TICK_LOCK_ERRORS=" +
              str(since_healthy.count("database is locked")), flush=True)
        print("FACTORY_AFTER_FIRST_HEALTHY_TICK_FAILURES=" +
              str(since_healthy.count("TICK_EXIT_FAILURE")), flush=True)
        print("FACTORY_AFTER_FIRST_HEALTHY_TICK_OK=" +
              str(since_healthy.count("FACTORY_TICK_OK")), flush=True)
    else:
        print("FACTORY_AFTER_FIRST_HEALTHY_TICK_NOT_OBSERVED", flush=True)
    print("FACTORY_POSTPATCH_STAGE4_RETRY_BLOCKS_LAST_500=" +
          str(data.count("Stage 4 retry window has not elapsed")), flush=True)
    print("FACTORY_POSTPATCH_NO_WRITE_EVENTS_LAST_500=" +
          str(data.count("FACTORY_AGENT_SEED_HEALTHY_NO_WRITE")), flush=True)
    print("FACTORY_POSTPATCH_REFRESH_EVENTS_LAST_500=" +
          str(data.count("FACTORY_AGENT_SEED_REFRESHED")), flush=True)
    print("FACTORY_POSTPATCH_SQLITE_LOCKS_LAST_500=" +
          str(data.count("database is locked")), flush=True)
    print("FACTORY_POSTPATCH_TICK_FAILURES_LAST_500=" +
          str(data.count("TICK_EXIT_FAILURE")), flush=True)

def apply(root: Path, backups: Path) -> None:
    paths = [
        (root / "core/management/commands/factory_staging_tick.py", "tick"),
        (root / "config/settings.py", "settings"),
    ]
    changes = [(path, kind, planned_patch(path,kind)) for path, kind in paths]
    need = [(p,k,c) for p,k,c in changes if c is not None]
    if not need:
        print("FACTORY_SQLITE_REPAIR_ALREADY_INSTALLED", flush=True)
        validate(root)
        report_live_log(root)
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backupdir = backups / ("sqlite-agent-contention-" + stamp + "-" + str(os.getpid()))
    backupdir.mkdir(parents=True, mode=0o700, exist_ok=False)
    originals: list[tuple[Path,Path]] = []
    try:
        for path, kind, replacement in need:
            backup = backupdir / (kind + ".py.orig")
            shutil.copy2(path, backup)
            originals.append((path,backup))
            temp = path.with_name(path.name + ".factory-sqlite-guard-" + str(os.getpid()))
            try:
                temp.write_text(replacement, encoding="utf-8")
                os.chmod(temp, path.stat().st_mode & 0o777)
                os.replace(temp, path)
            finally:
                temp.unlink(missing_ok=True)
            print("FACTORY_SQLITE_REPAIR_PATCHED=" + kind, flush=True)
        validate(root)
    except Exception as exc:
        for path, backup in reversed(originals):
            shutil.copy2(backup, path)
        print("FACTORY_SQLITE_REPAIR_ROLLED_BACK=" + type(exc).__name__, flush=True)
        raise
    print("FACTORY_SQLITE_REPAIR_INSTALLED_WITH_PRIVATE_BACKUP",flush=True)
    report_live_log(root)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--backups", type=Path, required=True)
    args = parser.parse_args()
    apply(args.root.resolve(), args.backups.resolve())

if __name__ == "__main__":
    main()
