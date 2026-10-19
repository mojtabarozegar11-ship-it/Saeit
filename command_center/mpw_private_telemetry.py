"""Read-only MojPlayWin private agent telemetry; no shared-site mutation.

The collector is the ONLY writer, and writes a bounded history file beneath the
existing private MojPlayWin directory. Django uses snapshot() for staff views.
Absent, malformed or old reports NEVER become healthy by assumption.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile

TENANT = "mojplaywin-main"
BASE = Path("/home/zomorod2/.private_mojplaywin_main_agents")
EVO = "evolution_runtime_20261018"
HISTORY = "agent_dashboard_telemetry.json"
MAX_REPORT = 1_000_000
MAX_HISTORY = 96
ROLE_CODES = ("agriculture", "commerce", "content", "economic", "master",
              "media", "quality", "research", "security", "seo", "weather")
FIVE = ("main_route_observer", "editorial_integrity", "draft_fingerprint",
        "editorial_review_queue", "agent_runtime_watch")
SIX = ("seo_metadata", "reference_origin", "release_reconciliation",
       "public_content_security", "disk_capacity", "publication_worklist")
SOURCES = {
    "master": ("v91_verified_main_port_20261018/operator_state/heartbeat.json", "last_master_callback_utc"),
    "gen65": (EVO + "/gen65_operational_report.json", "observed_utc"),
    "roles": ("site_health_v11_port_20261018/last_scan.json", "observed_utc"),
    "five": (EVO + "/robots_execution_20261018.json", "observed_utc"),
    "six": (EVO + "/extended_robots_status_20261018.json", "observed_utc"),
    "modules": (EVO + "/all_77_modules_last_run.json", "observed_utc"),
    "quality": ("quality_review_agent_20261018/last_review.log", None),
    "management": ("management_intelligence_20261018/latest_company_operations.json", None),
}
ALLOWED = re.compile(r"^[a-zA-Z0-9_.-]{1,140}$")


def _private(directory):
    try:
        return directory.is_dir() and not directory.is_symlink() and not (directory.stat().st_mode & 0o077)
    except OSError:
        return False


def _read(root, relative, max_bytes=MAX_REPORT):
    """Read only a fixed relative path with no symlinks or group/world access."""
    path = root
    for component in Path(relative).parts:
        if component in (".", "..") or not ALLOWED.fullmatch(component):
            return None
        path = path / component
        if path.is_symlink():
            return None
    try:
        if (not path.is_file() or (path.stat().st_mode & 0o077)
                or path.stat().st_size <= 0 or path.stat().st_size > max_bytes):
            return None
        with path.open("rb") as handle:
            raw = handle.read(max_bytes + 1)
        if len(raw) > max_bytes:
            return None
        value = json.loads(raw)
        return value if isinstance(value, dict) and value.get("tenant") == TENANT else None
    except (OSError, UnicodeError, ValueError, TypeError):
        return None


def _date(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except ValueError:
        return None


def _status(raw_state, observed, now, ttl_seconds, present):
    if not present or observed is None:
        return "unknown"
    age = (now - observed).total_seconds()
    if age < -60 or age > ttl_seconds:
        return "stale"
    if raw_state in ("ok", "healthy", "success", "active_private",
                     "gen65_operational_private", "active_private_learning"):
        return "healthy"
    if raw_state == "loaded_only":
        return "loaded_only"
    if raw_state in ("warning", "degraded"):
        return "degraded"
    if raw_state in ("error", "failed"):
        return "failed"
    return "unknown"


def _safe_label(value, fallback):
    value = str(value or "")
    return value[:140] if ALLOWED.fullmatch(value) else fallback


def snapshot(root=BASE, now=None, with_history=True):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone aware date required")
    root = Path(root)
    if not _private(root):
        return {"tenant": TENANT, "captured_at": now.isoformat(),
                "source": "private_cpanel_unavailable", "items": [], "summary": {
                    "total": 0, "healthy": 0, "stale": 0, "unknown": 0},
                "history_available": False}
    reports = {key: _read(root, rel) if field else None
               for key, (rel, field) in SOURCES.items()}
    items = []

    def put(identifier, name, kind, report, timefield, state, ttl=7200, extra=None):
        report = report if isinstance(report, dict) else {}
        observed = _date(report.get(timefield)) if timefield else None
        items.append({"id": identifier, "name": name, "kind": kind,
                      "state": _status(state, observed, now, ttl, bool(report)),
                      "reported_at": observed.isoformat() if observed else None,
                      "source": "cpanel_private_report",
                      "metrics": extra or {}, "history": []})

    master = reports["master"]
    put("master_gen64", "Master Agent Gen64", "master", master,
        "last_master_callback_utc", (master or {}).get("status"), 7200)
    gen = reports["gen65"]
    put("agent_gen65", "Evolution Agent Gen65", "agent", gen,
        "observed_utc", (gen or {}).get("status"), 300,
        {"generation": (gen or {}).get("active_private_generation")})

    roles = reports["roles"] or {}
    role_source = roles.get("runs", [])
    role_rows = {r.get("code"): r for r in role_source
                 if isinstance(r, dict) and isinstance(r.get("code"), str)} if isinstance(role_source, list) else {}
    for name in ROLE_CODES:
        row = role_rows.get(name)
        put("role_" + name, "Site health: " + name, "agent",
            roles if row else None, "observed_utc",
            row.get("status") if row else None, 7200)

    for group, expected in (("five", FIVE), ("six", SIX)):
        record = reports[group] or {}
        group_source = record.get("roles", [])
        rows = {r.get("name"): r for r in group_source
                if isinstance(r, dict) and isinstance(r.get("name"), str)} if isinstance(group_source, list) else {}
        for name in expected:
            row = rows.get(name)
            put("robot_" + name, name, "robot", record if row else None,
                "observed_utc", row.get("status") if row else None, 7200,
                {"checks": row.get("checks")} if row and isinstance(row.get("checks"), int) else {})

    module_report = reports["modules"] or {}
    registry = module_report.get("per_module_capability_registry", [])
    if not isinstance(registry, list):
        registry = []
    # A successful Python import is NOT evidence of a functional execution.
    # Always report the entire expected 77-slot inventory, even when the
    # private report is missing, truncated, malformed or has duplicate names.
    # Per-module execution requires a separate independently verified receipt.
    seen = set()
    for idx in range(77):
        row = registry[idx] if idx < len(registry) and isinstance(registry[idx], dict) else None
        name = _safe_label((row or {}).get("module"), "module_" + str(idx + 1))
        if name in seen:
            row = None
            name = "module_" + str(idx + 1)
        seen.add(name)
        loaded = (row or {}).get("loaded")
        import_state = "loaded_only" if loaded is True else (
            "failed" if loaded is False else None)
        put("module_" + str(idx + 1), name, "module",
            module_report if row else None, "observed_utc", import_state,
            7200, {"role": "imported_library", "independent_process": False,
                   "import_verified": loaded is True,
                   "functional_execution_verified": False})

    # Two additional workers are present in private Cron, but their log formats
    # do not prove an execution status; surface them as unknown until instrumented.
    for slug, title in (("quality", "Quality Review Worker"),
                        ("management", "Economic Management Worker")):
        put("worker_" + slug, title, "agent", reports[slug], None, None)
    history_available = False
    if with_history:
        history = _read(root, EVO + "/" + HISTORY, 950_000) or {}
        timelines = history.get("points") or {}
        if isinstance(timelines, dict):
            for item in items:
                series = timelines.get(item["id"], [])
                if isinstance(series, list):
                    item["history"] = [
                        {"at": x["at"], "value": x["value"]}
                        for x in series[-MAX_HISTORY:]
                        if isinstance(x, dict) and _date(x.get("at")) is not None
                        and (x.get("value") is None or x.get("value") in (0, 1))
                    ]
                    history_available = history_available or bool(item["history"])
    counts = {name: sum(x["state"] == name for x in items)
              for name in ("healthy", "loaded_only", "stale", "unknown", "failed", "degraded")}
    # Distinct MPW-owned QA evidence, never an inferred product or generation.
    quality = _read(root,
        EVO + "/onepass_agent_quality/onepass_status.json", 200_000)
    evidence = {
        "source": "mpw_tenant_only_onepass_quality",
        "state": "unknown", "open_rework_items": None,
        "functional_modules_verified": None, "legacy_probes": None,
        "generation_promoted": None, "product_produced_verified": None,
        "product_published_verified": None,
    }
    if isinstance(quality, dict) and quality.get("schema") == "mpw.onepass.agent_quality.v1":
        captured = _date(quality.get("captured_utc"))
        if captured is not None and -60 <= (now - captured).total_seconds() <= 3600:
            value = quality.get("open_rework_items")
            modules = quality.get("module_independent_functional_proof_count")
            probes = quality.get("legacy_curated_functional_probes")
            if (type(value) is int and 0 <= value <= 103 and
                type(modules) is int and 0 <= modules <= 77 and
                type(probes) is int and 0 <= probes <= 77):
                evidence.update({
                    "state": "reported", "open_rework_items": value,
                    "functional_modules_verified": modules, "legacy_probes": probes,
                    "generation_promoted": quality.get("evolution_generation_promoted") is True,
                    "product_produced_verified": quality.get("product_produced_count_verified"),
                    "product_published_verified": quality.get("product_published_count_verified"),
                })
    if evidence["state"] == "reported":
        worker_receipts = quality.get("worker_execution_evidence")
        if isinstance(worker_receipts, dict):
            for slug in ("quality", "management"):
                entry = worker_receipts.get(slug)
                valid = (
                    isinstance(entry, dict)
                    and entry.get("verified") is True
                    and entry.get("source") == (
                        "private_quality_cron_stdout" if slug == "quality"
                        else "private_management_cron_and_tenant_json")
                )
                target = next((i for i in items if i["id"] == "worker_" + slug), None)
                if target is not None and valid:
                    target["state"] = "healthy"
                    target["reported_at"] = quality["captured_utc"]
                    target["metrics"] = {
                        "worker_receipt_verified": True,
                        "private_source": entry["source"],
                    }
        evidence["worker_execution_receipts_verified"] = sum(
            item["state"] == "healthy" for item in items
            if item["id"] in ("worker_quality", "worker_management")
        )
    counts = {name: sum(x["state"] == name for x in items)
              for name in ("healthy", "loaded_only", "stale", "unknown", "failed", "degraded")}
    return {"tenant": TENANT, "captured_at": now.isoformat(),
            "source": "private_cpanel_reports", "items": items,
            "summary": {"total": len(items), **counts}, "evidence": evidence,
            "history_available": history_available}


def collect(root=BASE, now=None):
    """Write only one private, bounded telemetry JSON on an existing cPanel root."""
    now = now or datetime.now(timezone.utc)
    root = Path(root)
    target_dir = root / EVO
    if not (_private(root) and _private(target_dir)):
        raise RuntimeError("UNSAFE_OR_MISSING_PRIVATE_MPW_ROOT")
    if os.geteuid() != root.stat().st_uid:
        raise RuntimeError("WRONG_PRIVATE_TENANT_USER")
    output = target_dir / HISTORY
    if output.is_symlink():
        raise RuntimeError("TELEMETRY_SYMLINK_BLOCKED")
    old = _read(root, EVO + "/" + HISTORY, 950_000) or {}
    points = old.get("points") if isinstance(old.get("points"), dict) else {}
    current = snapshot(root=root, now=now, with_history=False)
    if len(current["items"]) < 25:
        raise RuntimeError("INCOMPLETE_MONITOR_INVENTORY")
    stamp = now.isoformat()
    for item in current["items"]:
        identifier = item["id"]
        old_points = points.get(identifier, [])
        if not isinstance(old_points, list):
            old_points = []
        old_points = [x for x in old_points[-MAX_HISTORY:]
                      if isinstance(x, dict) and _date(x.get("at")) is not None
                      and (x.get("value") is None or x.get("value") in (0, 1))]
        value = 1 if item["state"] == "healthy" else (
            0 if item["state"] in ("degraded", "failed") else None)
        if not old_points or old_points[-1]["at"] != stamp:
            old_points.append({"at": stamp, "value": value})
        points[identifier] = old_points[-MAX_HISTORY:]
    # Drop any retired IDs and cap stored history; no credentials or raw reports.
    permitted = {x["id"] for x in current["items"]}
    points = {k: v for k, v in points.items() if k in permitted}
    payload = json.dumps({"tenant": TENANT, "collected_at": stamp,
                          "points": points}, separators=(",", ":"), sort_keys=True).encode()
    if len(payload) > 950_000:
        raise RuntimeError("TELEMETRY_TOO_LARGE")
    fd, temp = tempfile.mkstemp(prefix=".mpw-monitor-", dir=str(target_dir))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, output)
    finally:
        if os.path.lexists(temp):
            os.unlink(temp)
    return {"status": "private_history_updated", "observed": len(current["items"]),
            "history": str(output.name), "public_site_modified": False}


if __name__ == "__main__":
    if sys.argv[1:] != ["--collect"]:
        raise SystemExit("ONLY_PRIVATE_COLLECT_ALLOWED")
    print(json.dumps(collect(), sort_keys=True))
