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
from contextlib import closing
from datetime import datetime, timezone
import os
import pwd
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from urllib.parse import quote


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
    "mojtaba.bot.ai",
    "mojtaba-bot-ai",
    "mojtaba_bot",
    "mojtrade_observer",
    "mojcoin",
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
CRON_ALIASES = frozenset({
    "@reboot", "@hourly", "@daily", "@weekly", "@monthly",
    "@yearly", "@annually", "@midnight",
})
CRON_SCAN_LINE_LIMIT = 500
OBSERVATION_OUTPUT_LIMIT = 512000


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
        return "observed", proc.stdout[:OBSERVATION_OUTPUT_LIMIT]
    if args[:2] == ["crontab", "-l"] and proc.returncode == 1:
        # rc=1 is commonly 'no crontab', but can be an access failure.
        # Do not claim zero scheduled jobs from this ambiguous signal.
        return "unavailable_or_empty", ""
    return "unavailable", ""


def safe_cron(stdout: str) -> list[dict]:
    """Redact scheduled commands, including cron @reboot/@hourly aliases."""
    out = []
    for line in stdout.splitlines()[:CRON_SCAN_LINE_LIMIT]:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            alias, sep, command = line.partition(" ")
            if alias.lower() not in CRON_ALIASES or not sep or not command.strip():
                continue
            schedule = alias.lower()
            command = command.strip()
        else:
            parts = line.split(maxsplit=5)
            if len(parts) != 6 or not all(CRON_TOKENS.fullmatch(x) for x in parts[:5]):
                continue
            schedule = " ".join(parts[:5])
            command = parts[5]
        flags = route_flags(command)
        out.append({
            "schedule": schedule,
            "command_digest": hashlib.sha256(command.encode()).hexdigest()[:16],
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
            # Refuse symlinked parents too: do not follow an app-directory
            # redirect to a private file outside the known runtime root.
            parents = tuple(parent for parent in path.parents
                            if parent == home or home in parent.parents)
            if (any(folder.is_symlink() for folder in parents)
                    or path.is_symlink() or not path.is_file()
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


PHP_SITE_CODES = frozenset({
    "master", "content", "seo", "commerce", "agriculture", "research",
    "economic", "weather", "quality", "media", "security",
})
PHP_SITE_TABLES = frozenset({
    "agents", "runs", "site_work_state", "site_work_outputs",
    "site_work_generation_evidence",
})


def safe_sqlite_status_counts(connection: sqlite3.Connection, table: str) -> dict:
    """Whitelist table/status names and aggregate all unexpected values."""
    allowed = {
        "runs": {"ok", "warning", "error"},
        "site_work_outputs": {"review", "blocked", "failed"},
    }
    if table not in allowed:
        raise ValueError("unknown aggregate status table")
    aggregate = Counter()
    for status, count in connection.execute(
        "SELECT status, COUNT(*) FROM " + table + " GROUP BY status"
    ):
        key = status if status in allowed[table] else "unexpected_status"
        aggregate[key] += int(count)
    return dict(sorted(aggregate.items()))


def cpanel_php_registry_snapshot(home: Path) -> dict:
    """Read the site's known private SQLite without making or mutating files.

    SQLite mode=ro,immutable=1 never creates journal/WAL/SHM files; if a
    WAL sidecar is present, fail closed rather than reading a possibly stale
    main DB and calling the result complete.
    """
    root = home / ".private" / "zomorod-business"
    db = root / "site_agents.sqlite3"
    base = {
        "state": "unknown_not_observed",
        "path_scope": "private_site_agents_sqlite3_only",
        "read_only_immutable": True,
        "database_state_proves_live_workers": False,
        "live_scheduler_verified": False,
        "records": None,
        "known_source_roles": len(PHP_SITE_CODES),
        "known_roles_found": None,
        "enabled_count": None,
        "agent_roles": [],
        "run_status_counts": {},
        "recent_worker_output_status_counts": {},
        "incomplete_wal_snapshot": False,
    }
    try:
        if (home.is_symlink() or (home / ".private").is_symlink()
                or root.is_symlink() or db.is_symlink()):
            return {**base, "state": "unsafe_symlink"}
        if not db.is_file():
            return {**base, "state": "private_database_not_observed"}
        if db.stat().st_size <= 0 or db.stat().st_size > 512 * 1024 * 1024:
            return {**base, "state": "unsupported_database_size"}
        if (root / (db.name + "-wal")).exists():
            return {**base, "state": "wal_present_snapshot_not_consistent",
                    "incomplete_wal_snapshot": True}
    except OSError:
        return {**base, "state": "database_metadata_unavailable"}

    # No PRAGMA journal_mode change and no write-capable handle; only approved
    # aggregate metadata leaves the host. A missing table is not zero rows.
    uri = "file:" + quote(str(db), safe="/") + "?mode=ro&immutable=1"
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=2)) as conn:
            conn.execute("PRAGMA query_only=ON")
            tables = set(
                name for (name,) in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ) if name in PHP_SITE_TABLES
            )
            if "agents" not in tables:
                return {**base, "state": "agents_table_unavailable"}
            roles = [
                (str(code), int(enabled)) for code, enabled in
                conn.execute("SELECT code, enabled FROM agents ORDER BY code")
            ]
            known = [
                {"code": code, "enabled": enabled == 1}
                for code, enabled in roles if code in PHP_SITE_CODES
            ]
            unknown_rows = sum(code not in PHP_SITE_CODES for code, _ in roles)
            result = {
                **base,
                "state": "source_registry_snapshot_only",
                "records": len(roles),
                "known_roles_found": len(known),
                "enabled_count": sum(enabled == 1 for _, enabled in roles),
                "unknown_code_records": unknown_rows,
                "agent_roles": known,
            }
            if "runs" in tables:
                result["run_status_counts"] = safe_sqlite_status_counts(
                    conn, "runs"
                )
            if "site_work_outputs" in tables:
                result["recent_worker_output_status_counts"] = (
                    safe_sqlite_status_counts(conn, "site_work_outputs")
                )
            result["missing_expected_tables"] = sorted(PHP_SITE_TABLES - tables)
            return result
    except (sqlite3.DatabaseError, OSError, ValueError, TypeError):
        return {**base, "state": "sqlite_read_failed"}


def collect(role: str, *, home: Path | None = None, username: str | None = None) -> dict:
    if role not in TARGETS:
        raise ValueError("unknown host role")
    user = username if username is not None else pwd.getpwuid(os.geteuid()).pw_name
    if user != TARGETS[role]["expected_user"]:
        raise PermissionError("MOJTABA_LIVE_TOPOLOGY_WRONG_HOST_USER")
    root = home if home is not None else Path(pwd.getpwuid(os.geteuid()).pw_dir)

    cron_state, cron_raw = call_readonly(["crontab", "-l"])
    process_state, ps_raw = call_readonly(["ps", "-eo", "args="])
    service_state, services_raw = call_readonly([
        "systemctl", "--user", "list-units", "--type=service",
        "--all", "--plain", "--no-legend", "--no-pager",
    ])
    system_service_state, system_services_raw = call_readonly([
        "systemctl", "list-units", "--type=service",
        "--all", "--plain", "--no-legend", "--no-pager",
    ])
    cron_rows = safe_cron(cron_raw) if cron_state == "observed" else []
    # The output transport and the parser both have finite caps. These are
    # redacted warning flags, not proof that no other schedulers exist.
    cron_truncated = (
        cron_state == "observed" and (
            len(cron_raw.splitlines()) > CRON_SCAN_LINE_LIMIT
            or len(cron_raw) >= OBSERVATION_OUTPUT_LIMIT
        )
    )
    process_truncated = (
        process_state == "observed" and (
            len(ps_raw.splitlines()) > 20000
            or len(ps_raw) >= OBSERVATION_OUTPUT_LIMIT
        )
    )
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
            "enumeration_truncated": bool(cron_truncated),
        },
        "processes": {
            "state": process_state, **processes,
            "enumeration_truncated": bool(process_truncated),
        },
        "user_services": {
            "state": service_state,
            "candidate_units": safe_service_units(services_raw)
            if service_state == "observed" else [],
            "service_name_indicators_only": True,
        },
        "system_services": {
            "state": system_service_state,
            "candidate_units": safe_service_units(system_services_raw)
            if system_service_state == "observed" else [],
            "service_name_indicators_only": True,
        },
        "installed_source_digests": safe_source_digests(root, role),
        "private_php_site_registry": (
            cpanel_php_registry_snapshot(root) if role == "cpanel"
            else {"state": "not_applicable", "database_state_proves_live_workers": False}
        ),
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
