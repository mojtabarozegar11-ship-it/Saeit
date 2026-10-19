#!/usr/bin/env python3
"""MojPlayWin-only read-only actual runtime source/worker evidence inventory.

No site writes, secret output, database reads or exposure of other domain paths.
A scheduled Cron entry proves configuration, not a successfully running worker.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import subprocess

TENANT = "mojplaywin-main"
DOMAIN = "mojplaywin.com"
ROOT = Path("/home/zomorod2/mojplaywin.com")
APP = Path("/home/zomorod2/Saeit-staging")
PRIVATE = Path("/home/zomorod2/.private_mojplaywin_main_agents")
EVO = PRIVATE / "evolution_runtime_20261018"
MARKERS = {
    "master_gen64": "MPW_V91_MAIN_ONLY_20261018",
    "site_roles": "MPW_V11_MAIN_ONLY_SITE_HEALTH_20261018",
    "quality_review": "MPW_ZOMOROD_QUALITY_REVIEW_MAIN_ONLY_20261018",
    "management": "MPW_ZOMOROD_MANAGEMENT_INTELLIGENCE_MAIN_ONLY_20261018",
    "gen65": "MPW_PRIVATE_EVOLUTION_MAIN_ONLY_20261018",
    "modules_77": "MPW_77_MODULES_MAIN_ONLY_20261018",
    "robots_five": "MPW_MAIN_PRIVATE_EXECUTION_ROBOTS_20261018",
    "robots_six": "MPW_MAIN_EXTENDED_ROBOTS_20261018",
    "telemetry": "MPW_MAIN_AGENT_DASHBOARD_COLLECTOR_20261018",
}

def _safe_file(path, limit=200_000):
    try:
        if path.is_symlink() or not path.is_file():
            return None
        if not 0 < path.stat().st_size <= limit:
            return None
        return path.read_bytes()
    except OSError:
        return None

def _report(path):
    data = _safe_file(path, 1_000_000)
    if data is None:
        return None
    try:
        result = json.loads(data)
    except (UnicodeError, ValueError):
        return None
    return result if isinstance(result, dict) and result.get("tenant") == TENANT else None

def _age_seconds(record, field, now):
    if record is None:
        return None
    raw = record.get(field)
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        age = int((now - dt.astimezone(timezone.utc)).total_seconds())
        return age if age >= 0 else None
    except (ValueError, AttributeError, TypeError):
        return None

def inspect_runtime(root=ROOT, app=APP, private=PRIVATE, cron_text=None, now=None):
    now = now or datetime.now(timezone.utc)
    root = Path(root)
    app = Path(app)
    private = Path(private)
    if not (root.is_dir() and not root.is_symlink() and
            app.is_dir() and not app.is_symlink() and
            private.is_dir() and not private.is_symlink()):
        return {"tenant": TENANT, "domain": DOMAIN, "runtime_identity": "unverified",
                "status": "missing_or_untrusted_root"}
    raw = _safe_file(root / "passenger_wsgi.py")
    expected = "APP='" + str(app) + "'"
    wsgi_targets_app = raw is not None and expected.encode() in raw
    htaccess = _safe_file(root / ".htaccess")
    expected_passenger = "PassengerAppRoot " + str(root)
    passenger_root = htaccess is not None and expected_passenger.encode() in htaccess
    if cron_text is None:
        try:
            result = subprocess.run(["crontab", "-l"], capture_output=True,
                                    text=True, timeout=12, check=True)
            cron_text = result.stdout
        except (OSError, subprocess.SubprocessError):
            cron_text = ""
    active = [x for x in cron_text.splitlines()
              if x.strip() and not x.lstrip().startswith("#")]
    cron_matches = {name: sum(marker in line for line in active)
                    for name, marker in MARKERS.items()}
    evo = private / "evolution_runtime_20261018"
    report = _report(evo / "all_77_modules_last_run.json")
    registry = (report or {}).get("per_module_capability_registry")
    registry = registry if isinstance(registry, list) else []
    loaded = sum(row.get("loaded") is True for row in registry[:77]
                 if isinstance(row, dict))
    roles = _report(private / "site_health_v11_port_20261018" / "last_scan.json")
    robots_a = _report(evo / "robots_execution_20261018.json")
    robots_b = _report(evo / "extended_robots_status_20261018.json")
    heartbeat = _report(private / "v91_verified_main_port_20261018" /
                        "operator_state" / "heartbeat.json")
    connected = bool(wsgi_targets_app and passenger_root)
    return {
        "tenant": TENANT, "domain": DOMAIN, "captured_utc": now.isoformat(),
        "runtime_identity": "Saeit-staging" if connected else "unverified",
        "runtime_identity_verified": connected,
        "passenger_wiring_verified": bool(wsgi_targets_app),
        "passenger_root_verified": bool(passenger_root),
        "wsgi_sha256": hashlib.sha256(raw).hexdigest() if raw else None,
        "cron_marker_counts": cron_matches,
        "cron_markers_unique": all(x == 1 for x in cron_matches.values()),
        "module_import_count": loaded,
        "module_functional_execution_verified": False,
        "module_report_age_seconds": _age_seconds(report, "observed_utc", now),
        "master_heartbeat_age_seconds": _age_seconds(heartbeat, "last_master_callback_utc", now),
        "site_roles_report_age_seconds": _age_seconds(roles, "observed_utc", now),
        "five_robots_report_age_seconds": _age_seconds(robots_a, "observed_utc", now),
        "six_robots_report_age_seconds": _age_seconds(robots_b, "observed_utc", now),
        "Bazei_runtime_connected": False if connected else None,
        "site_writes": 0, "other_sites_examined": False,
        "status": "runtime_identity_observed" if connected else "runtime_identity_unverified",
    }

if __name__ == "__main__":
    result = inspect_runtime()
    print("MPW_SITE_ONLY_RUNTIME_IDENTITY=" + json.dumps(result, sort_keys=True))
    if not result.get("runtime_identity_verified"):
        raise SystemExit(2)
