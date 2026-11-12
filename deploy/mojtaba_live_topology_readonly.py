#!/usr/bin/env python3
"""Read-only, disclosure-minimized live host topology evidence for Mojtaba.bot.ai.

Run locally as githubops (VPS) or zomorod2 (cPanel) via a verified trusted
session. No service changes, database reads, file writes or external requests.
A matching process/cron string is an *indicator*, never proof of successful
task execution, retirement, customer delivery or live single-bot operation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import getpass
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


SCHEMA = "mojtaba.bot.ai.live-topology-observation.v1"
TARGETS = {
    "vps": {
        "expected_user": "githubops",
        "relative_core": "factory-runtime/django-app/core",
        "source_files": (
            "unified_bot_identity.py",
            "management/commands/audit_agent_fleet.py",
            "management/commands/online_income_cycle.py",
            "management/commands/consolidate_legacy_agents.py",
        ),
    },
    "cpanel": {
        "expected_user": "zomorod2",
        "relative_core": "Saeit/core",
        "source_files": (
            "unified_bot_identity.py",
            "canonical_agent_handoff.py",
            "newsletter_engine.py",
            "weather_agent.py",
            "management/commands/knowledge_agent_cycle.py",
            "management/commands/newsletter_process_queue.py",
            "management/commands/company_activity_agent_cycle.py",
        ),
    },
}
# Specific scheduler/worker identifiers, not generic words like "python",
# "agent", "factory" or "mojtaba" that match the audit process itself.
ROUTES = (
    "mojtaba_bot_cycle_worker.py",
    "mojtaba_bot_cycle_coordinator.py",
    "online_income_cycle",
    "run_economic_worker",
    "run_factory_worker",
    "knowledge_agent_cycle",
    "knowledge_agent_generate",
    "newsletter_process_queue",
    "company_activity_agent_cycle",
    "weather_agent_cycle",
    "site_agent_workforce.php",
    "site_agents.php",
    "factory_staging_tick",
    "factory_agent_runtime",
    "stage4_due_dispatch",
    "autonomous_master_loop",
    "SAEIT_MOJTRADE_OBSERVER_V1",
)
CRON_TOKENS = re.compile(r"^[0-9*/?,LW#-]{1,40}$", re.IGNORECASE)


def route_flags(command: str) -> list[str]:
    lower = command.casefold()
    return [tag for tag in ROUTES if tag.casefold() in lower]


def call_readonly(args: list[str], *, timeout: int = 10) -> tuple[str, str]:
    """Return (state, stdout), never echo stderr, command arguments or secrets."""
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                              timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable", ""
    if proc.returncode == 0:
        return "observed", proc.stdout[:512000]
    if args[:2] == ["crontab", "-l"] and proc.returncode == 1:
        # rc=1 is commonly 'no crontab', but can be an access failure.
        # Do not claim zero scheduled jobs from this ambiguous signal.
        return "unavailable_or_empty", ""
    return "unavailable", ""


def safe_cron(stdout: str) -> list[dict]:
    out = []
    for line in stdout.splitlines()[:500]:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("@"):
            continue
        parts = line.split(maxsplit=5)
        if len(parts) != 6 or not all(CRON_TOKENS.fullmatch(x) for x in parts[:5]):
            continue
        flags = route_flags(parts[5])
        out.append({
            "schedule": " ".join(parts[:5]),
            "command_digest": hashlib.sha256(parts[5].encode()).hexdigest()[:16],
            "known_route_flags": flags,
        })
    return out


def safe_processes(stdout: str) -> dict:
    count = Counter()
    seen = 0
    for line in stdout.splitlines()[:20000]:
        if not line.strip():
            continue
        seen += 1
        # Never publish process arguments, environment variables, URLs or PIDs.
        for flag in route_flags(line):
            count[flag] += 1
    return {"inspected": seen, "route_match_counts": dict(sorted(count.items())),
            "process_identity_proven": False}


def safe_service_units(stdout: str) -> list[dict]:
    entries = []
    for line in stdout.splitlines()[:1000]:
        parts = line.split()
        if len(parts) < 4 or not parts[0].endswith(".service"):
            continue
        flags = route_flags(parts[0])
        if flags:
            entries.append({
                "unit_name_digest": hashlib.sha256(parts[0].encode()).hexdigest()[:16],
                "known_route_flags": flags,
                "load": parts[1] if parts[1] in {"loaded", "not-found", "masked"} else "other",
                "active": parts[2] if parts[2] in {"active", "inactive", "failed", "activating"} else "other",
            })
    return entries


def safe_source_digests(home: Path, role: str) -> dict:
    cfg = TARGETS[role]
    root = home / cfg["relative_core"]
    result = {}
    for name in cfg["source_files"]:
        path = root / name
        try:
            if (path.is_symlink() or not path.is_file()
                    or not 0 < path.stat().st_size <= 512000):
                result[name] = {"state": "unavailable_or_unsafe"}
            else:
                result[name] = {
                    "state": "file_observed_not_runtime_executed",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
        except OSError:
            result[name] = {"state": "unavailable_or_unsafe"}
    return result


def collect(role: str, *, home: Path | None = None, username: str | None = None) -> dict:
    if role not in TARGETS:
        raise ValueError("unknown host role")
    user = username if username is not None else getpass.getuser()
    if user != TARGETS[role]["expected_user"]:
        raise PermissionError("MOJTABA_LIVE_TOPOLOGY_WRONG_HOST_USER")
    root = home or Path.home()

    cron_state, cron_raw = call_readonly(["crontab", "-l"])
    process_state, ps_raw = call_readonly(["ps", "-eo", "args="])
    service_state, services_raw = call_readonly([
        "systemctl", "--user", "list-units", "--type=service",
        "--all", "--plain", "--no-legend", "--no-pager",
    ])
    cron_rows = safe_cron(cron_raw) if cron_state == "observed" else []
    processes = safe_processes(ps_raw) if process_state == "observed" else {
        "inspected": None, "route_match_counts": {}, "process_identity_proven": False
    }
    return {
        "schema": SCHEMA,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "host_role": role,
        "expected_user_verified": True,
        "read_only": True,
        "database_queried": False,
        "external_network_used": False,
        "cron": {
            "state": cron_state, "enumerated_entries": len(cron_rows)
            if cron_state == "observed" else None,
            "entries": cron_rows,
        },
        "processes": {"state": process_state, **processes},
        "user_services": {
            "state": service_state,
            "candidate_units": safe_service_units(services_raw)
            if service_state == "observed" else [],
            "system_services_inventoried": False,
        },
        "installed_source_digests": safe_source_digests(root, role),
        "attestation": {
            "source_code_deployment_matches_pr": False,
            "canonical_worker_executed": False,
            "external_schedulers_fully_enumerated": False,
            "legacy_workers_retired": False,
            "handoff_verified": False,
            "automatic_deactivation_authorized": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=tuple(TARGETS), required=True)
    args = parser.parse_args(argv)
    try:
        report = collect(args.role)
    except PermissionError:
        print("MOJTABA_TOPOLOGY_PREFLIGHT=wrong_host_user", file=sys.stderr)
        return 2
    print("MOJTABA_LIVE_TOPOLOGY=" + json.dumps(
        report, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
