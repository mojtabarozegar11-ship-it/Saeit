#!/usr/bin/env python3
"""Evidence-based MojPlayWin-only autonomous *diagnosis* and QA rework ledger.

A successful heartbeat/import does not imply product production, mastering a task,
or 100% quality. This worker executes meaningful tenant-scoped checks and creates
durable, deduplicated defect work orders. It never touches public files, Django,
other tenants, payments, the global factory, or shared cPanel configuration.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile

TENANT = "mojplaywin-main"
PRIVATE = Path("/home/zomorod2/.private_mojplaywin_main_agents")
EVO = "evolution_runtime_20261018"
OWN = "onepass_agent_quality"
OUTPUT = "onepass_status.json"
ISSUES = "onepass_rework_ledger.json"
SCHEMA = "mpw.onepass.agent_quality.v1"
MAX_SIZE = 1_000_000
FIVE = ("main_route_observer", "editorial_integrity", "draft_fingerprint",
        "editorial_review_queue", "agent_runtime_watch")
SIX = ("seo_metadata", "reference_origin", "release_reconciliation",
       "public_content_security", "disk_capacity", "publication_worklist")
ROLES = ("agriculture", "commerce", "content", "economic", "master",
         "media", "quality", "research", "security", "seo", "weather")
SOURCES = {
    "master_gen64": ("v91_verified_main_port_20261018/operator_state/heartbeat.json",
                     "last_master_callback_utc", 7200),
    "gen65": (EVO + "/gen65_operational_report.json", "observed_utc", 7200),
    "site_roles": ("site_health_v11_port_20261018/last_scan.json", "observed_utc", 7200),
    "robots_five": (EVO + "/robots_execution_20261018.json", "observed_utc", 7200),
    "robots_six": (EVO + "/extended_robots_status_20261018.json", "observed_utc", 7200),
    "modules77": (EVO + "/all_77_modules_last_run.json", "observed_utc", 7200),
}
PART = re.compile(r"^[A-Za-z0-9_.-]{1,150}$")


def private_dir(path):
    return (path.is_dir() and not path.is_symlink() and
            path.stat().st_mode & 0o077 == 0)


def checked_read(root, relative):
    path = root
    for token in Path(relative).parts:
        if token in (".", "..") or not PART.fullmatch(token):
            return None
        path = path / token
        if path.is_symlink():
            return None
    try:
        if (not path.is_file() or path.stat().st_mode & 0o077 or
                not 0 < path.stat().st_size < MAX_SIZE):
            return None
        value = json.loads(path.read_bytes())
        if isinstance(value, dict) and value.get("tenant") == TENANT:
            return value
    except (OSError, UnicodeError, ValueError, TypeError):
        pass
    return None


def _private_worker_json(root, relative, now, ttl=7200):
    """Read a fixed worker receipt with freshness and scope checks.

    Legacy logs are 0644 but live under owner-only mode-0700 private
    directories; never accept a symlink, foreign UID or unbounded report.
    """
    path = root
    for token in Path(relative).parts:
        if token in (".", "..") or not PART.fullmatch(token):
            return None
        path = path / token
        if path.is_symlink():
            return None
    try:
        parent = path.parent
        if not private_dir(parent):
            return None
        stat = path.stat()
        if (not path.is_file() or stat.st_uid != root.stat().st_uid
                or stat.st_mode & 0o022 or not 0 < stat.st_size <= 100_000):
            return None
        age = (now.timestamp() - stat.st_mtime)
        if not -60 <= age <= ttl:
            return None
        obj = json.loads(path.read_bytes())
        return obj if isinstance(obj, dict) else None
    except (OSError, ValueError, UnicodeError, TypeError):
        return None


def _worker_checks(root, now):
    quality = _private_worker_json(
        root, "quality_review_agent_20261018/last_review.log", now)
    management_stdout = _private_worker_json(
        root, "management_intelligence_20261018/last_run.log", now)
    management_report = checked_read(
        root, "management_intelligence_20261018/latest_company_operations.json")
    report_recent = freshness(management_report, "observed_utc", 7200, now)
    quality_ok = (
        isinstance(quality, dict)
        and quality.get("status") == "MPW_ZOMOROD_QUALITY_STANDARDS_USED_IN_PRIVATE_REVIEW"
        and quality.get("source_hashes_verified") is True
        and type(quality.get("actual_private_drafts_scored")) is int
        and quality["actual_private_drafts_scored"] >= 0
        and isinstance(quality.get("quality_review_results"), dict)
        and quality.get("factory_or_zomorod_modified") is False
        and quality.get("website_published") is False
    )
    management_ok = (
        isinstance(management_stdout, dict)
        and management_stdout.get("status") == "MPW_ZOMOROD_REPORTING_AND_ECONOMIC_POLICIES_IN_USE"
        and type(management_stdout.get("source_modules_hash_verified")) is int
        and management_stdout["source_modules_hash_verified"] >= 2
        and type(management_stdout.get("validated_private_drafts")) is int
        and management_stdout["validated_private_drafts"] >= 0
        and management_stdout.get("shared_Django_changed") is False
        and management_stdout.get("zomorod_or_factory_modified") is False
        and management_stdout.get("financial_actions_executed") == 0
        and isinstance(management_report, dict)
        and report_recent == "recent"
        and management_report.get("factory_connected") in (False, None)
        and management_report.get("financial_account_data_consulted") in (False, 0)
    )
    return {
        "quality": {
            "verified": bool(quality_ok),
            "source": "private_quality_cron_stdout",
            "real_drafts_scored": quality["actual_private_drafts_scored"] if quality_ok else None,
        },
        "management": {
            "verified": bool(management_ok),
            "source": "private_management_cron_and_tenant_json",
            "drafts_validated": management_stdout["validated_private_drafts"] if management_ok else None,
        },
    }


def as_time(raw):
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, AttributeError, TypeError, OverflowError):
        return None


def freshness(record, field, ttl, now):
    dt = as_time((record or {}).get(field))
    if dt is None:
        return "unknown"
    age = (now - dt).total_seconds()
    if age < -60 or age > ttl:
        return "stale"
    return "recent"


def component(result, name, state, observed=None, kind="agent", metrics=None):
    result.append({"id": name, "state": state, "kind": kind,
                   "observed_utc": observed, "metrics": metrics or {}})


def evaluate(root, now=None):
    """Pure report evaluation. No QA or functional proof inferred from imports."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("A timezone-aware timestamp is required")
    if not private_dir(root):
        raise RuntimeError("MPW_PRIVATE_TENANT_ROOT_REQUIRED")
    reports = {key: checked_read(root, rel) for key, (rel, _, _) in SOURCES.items()}
    items = []
    for name in ("master_gen64", "gen65"):
        record = reports[name]
        field, ttl = SOURCES[name][1:]
        state = freshness(record, field, ttl, now)
        raw = (record or {}).get("status")
        if state == "recent":
            state = "healthy" if raw in ("active_private", "gen65_operational_private") else "unknown"
        component(items, name, state, (record or {}).get(field),
                  "master" if name == "master_gen64" else "agent")
    for group, labels, key in (("site_roles", ROLES, "code"),
                               ("robots_five", FIVE, "name"),
                               ("robots_six", SIX, "name")):
        report = reports[group] or {}
        field, ttl = SOURCES[group][1:]
        recent = freshness(report, field, ttl, now)
        source = report.get("runs" if group == "site_roles" else "roles")
        rows = {r.get(key): r for r in source if isinstance(r, dict) and isinstance(r.get(key), str)} if isinstance(source, list) else {}
        for name in labels:
            value = rows.get(name)
            raw = value.get("status") if value else None
            status = "unknown" if value is None else recent
            if status == "recent":
                status = "healthy" if raw in ("ok", "healthy", "success") else (
                    "failed" if raw in ("error", "failed") else "degraded" if raw in ("warning", "degraded") else "unknown")
            component(items, ("role_" if group == "site_roles" else "robot_") + name,
                      status, report.get(field), "agent" if group == "site_roles" else "robot")
    report = reports["modules77"] or {}
    field, ttl = SOURCES["modules77"][1:]
    recent = freshness(report, field, ttl, now)
    rows = report.get("per_module_capability_registry")
    rows = rows if isinstance(rows, list) else []
    module_hash_count = report.get("modules_hash_verified")
    module_hash_count = module_hash_count if type(module_hash_count) is int and 0 <= module_hash_count <= 77 else None
    module_status = []
    seen = set()
    for n in range(77):
        row = rows[n] if n < len(rows) and isinstance(rows[n], dict) else {}
        module_name = row.get("module")
        valid = isinstance(module_name, str) and bool(PART.fullmatch(module_name.replace("/", "_"))) and module_name not in seen
        name = module_name if valid else "missing_or_duplicate_" + str(n + 1)
        if valid:
            seen.add(name)
        imported = row.get("loaded") is True and valid
        status = "loaded_only" if imported and recent == "recent" else (
            recent if imported and recent == "stale" else "failed" if row.get("loaded") is False and valid else "unknown")
        component(items, "module_" + str(n + 1), status, report.get(field), "module",
                  {"module": name, "import_verified": imported, "function_verified": False})
        module_status.append(status)
    # Original worker outputs are now verified by their fixed private receipts,
    # rather than by scheduled Cron markers, log existence or name alone.
    workers = _worker_checks(root, now)
    component(items, "worker_quality",
              "healthy" if workers["quality"]["verified"] else "unknown",
              kind="agent", metrics=workers["quality"])
    component(items, "worker_management",
              "healthy" if workers["management"]["verified"] else "unknown",
              kind="agent", metrics=workers["management"])
    assert len(items) == 103, "EXPECTED_103_PRIVATE_COMPONENTS"
    counts = {k: sum(item["state"] == k for item in items)
              for k in ("healthy", "loaded_only", "stale", "degraded", "failed", "unknown")}
    probes = report.get("functional_probes_executed")
    probes = probes if type(probes) is int and 0 <= probes <= 77 else 0
    return {"schema": SCHEMA, "tenant": TENANT, "captured_utc": now.isoformat(),
            "master_authority": "master_gen64_observation_only",
            "autonomous_master_dispatch_verified": False,
            "evolution_generation_promoted": False,
            "generation_promotion_reason": "no_compared_code_artifacts_or_regression_proof",
            "components": items, "worker_execution_evidence": workers,
            "summary": {"total": 103, **counts},
            "module_hash_verified_count": module_hash_count,
            "module_import_count": sum(x == "loaded_only" for x in module_status),
            "module_independent_functional_proof_count": 0,
            "legacy_curated_functional_probes": probes,
            "product_produced_count_verified": None,
            "product_published_count_verified": None,
            "finance_actions_enabled": False, "auto_publish_enabled": False,
            "other_sites_touched": False}


def evidence_issue(old, item, now):
    name = item["id"]
    state = item["state"]
    fingerprint = hashlib.sha256((TENANT + ":" + name).encode()).hexdigest()[:24]
    prev = old.get(fingerprint, {}) if isinstance(old, dict) else {}
    if not isinstance(prev, dict):
        prev = {}
    needs_work = state in ("unknown", "stale", "failed", "degraded")
    first = prev.get("first_seen_utc") if isinstance(prev.get("first_seen_utc"), str) else now.isoformat()
    return fingerprint, {"id": fingerprint, "component": name, "observed_state": state,
            "work": "repair_and_retest" if needs_work else "resolved_or_import_only",
            "quality_passed": False if needs_work else None,
            "retry_attempts_verified": prev.get("retry_attempts_verified", 0),
            "first_seen_utc": first, "last_seen_utc": now.isoformat(),
            "preserved_for_rework": True,
            "resolution_evidence": None if needs_work else "current_report_no_longer_reports_defect"}


def evolve_ledger(report, previous, now):
    prior = previous.get("issues", {}) if isinstance(previous, dict) else {}
    if not isinstance(prior, dict) or len(prior) > 1000:
        raise RuntimeError("INVALID_EXISTING_LEDGER")
    merged = dict(prior)
    active = 0
    for item in report["components"]:
        key, issue = evidence_issue(merged, item, now)
        if issue["work"] == "repair_and_retest":
            active += 1
        if key in merged or issue["work"] == "repair_and_retest":
            merged[key] = issue
    return {"schema": SCHEMA, "tenant": TENANT, "updated_utc": now.isoformat(),
            "open_rework_items": active,
            "issues": merged, "task_executions_claimed": 0,
            "automatic_resubmission_authorized": False,
            "history_is_never_discarded_for_quality_failure": True}


def atomic_json(path, value):
    if path.is_symlink():
        raise RuntimeError("ONEPASS_OUTPUT_SYMLINK_REFUSED")
    raw = (json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n").encode()
    if len(raw) >= MAX_SIZE:
        raise RuntimeError("ONEPASS_REPORT_TOO_LARGE")
    fd, temp = tempfile.mkstemp(prefix=".mpw-onepass-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.lexists(temp):
            os.unlink(temp)


def run_once(root=PRIVATE, now=None):
    root = Path(root)
    if not private_dir(root) or not private_dir(root / EVO):
        raise RuntimeError("MISSING_PRIVATE_MPW_TENANT")
    if os.geteuid() != root.stat().st_uid:
        raise RuntimeError("UNEXPECTED_CPANEL_OWNER")
    own = root / EVO / OWN
    if own.is_symlink():
        raise RuntimeError("ONEPASS_SYMLINK_DIRECTORY")
    own.mkdir(mode=0o700, exist_ok=True)
    if not private_dir(own):
        raise RuntimeError("ONEPASS_WEAK_PERMISSIONS")
    lock = own / ".run.lock"
    fd = os.open(str(lock), os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stamp = now or datetime.now(timezone.utc)
        report = evaluate(root, stamp)
        old = checked_read(root, EVO + "/" + OWN + "/" + ISSUES) or {}
        ledger = evolve_ledger(report, old, stamp)
        report["open_rework_items"] = ledger["open_rework_items"]
        report["operational_cycle_executed"] = True
        report["production_claimed"] = False
        atomic_json(own / ISSUES, ledger)
        atomic_json(own / OUTPUT, report)
        return {"tenant": TENANT, "status": "real_evidence_audit_and_rework_ledger_updated",
                "component_count": report["summary"]["total"],
                "modules_imported_only": report["summary"]["loaded_only"],
                "open_rework_items": report["open_rework_items"],
                "master_dispatch_verified": False, "other_sites_modified": False}
    finally:
        os.close(fd)


if __name__ == "__main__":
    if sys.argv[1:] != ["--once"]:
        raise SystemExit("ONLY_ONEPASS_PRIVATE_MODE_ALLOWED")
    os.umask(0o077)
    print(json.dumps(run_once(), sort_keys=True))
