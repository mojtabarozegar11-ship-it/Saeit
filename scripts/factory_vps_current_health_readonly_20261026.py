#!/usr/bin/env python3
"""Read-only, aggregate-only health evidence for the owner VPS factory."""
import collections
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

BASE = Path("/home/githubops/factory-runtime")
PRIVATE = BASE / "private/autonomous-product-cycle"
ORDERS = PRIVATE / "production-instructions/orders"
INDEX = PRIVATE / "production-instructions/owner-agri200-p0-index.json"
OPS = BASE / "operations/production-instructions"
LIMIT = 250000
ORDER_PATTERN = re.compile(r"WO-[0-9]{8}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")


def safe_json(path, maximum=LIMIT):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError("unsafe_or_missing")
    decoded = json.loads(path.read_text(encoding="utf8"))
    if not isinstance(decoded, dict):
        raise ValueError("invalid_json_object_root")
    return decoded


def command(args):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=7,
                           check=False)
        return p.stdout if p.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None



SLOT_SCHEMA = "saeit.factory.product-slots.v1"
RECIPE = re.compile(r"[a-z][a-z0-9_]{1,65}\Z")


def line41_diagnostic(private):
    """Prove the single slot's actual source state without running its workers."""
    current = private / "quality-excellence/product-flow/active-slots/current.json"
    if not current.exists() and not current.is_symlink():
        return {"slot_state": "absent"}
    try:
        state = safe_json(current, 500_000)
        active = state.get("active")
        waiting = state.get("waiting")
        exited = state.get("exited")
        if (state.get("schema") != SLOT_SCHEMA or not isinstance(active, list)
                or not isinstance(waiting, list) or not isinstance(exited, dict)):
            return {"slot_state": "invalid"}
        names = [x.get("recipe") for x in active if isinstance(x, dict)]
        if len(names) != len(active) or any(not isinstance(x, str)
                                            or not RECIPE.fullmatch(x) for x in names):
            return {"slot_state": "invalid"}
        details = []
        for name in names[:2]:
            source = private / "generated-product-recipes" / name
            receipt = source / "design_receipt.json"
            manifest = (private / "digital-products" / name
                        / "manufacturing_manifest.json")
            clearance = (private / "quality-excellence/signed-clearances"
                         / name / "current.json")
            review = (private / "quality-excellence/production-workorders"
                      / name / "current.json")
            info = {"recipe": name, "generated_source_exists": source.is_dir()
                    and not source.is_symlink(), "signed_clearance_present":
                    clearance.is_file() and not clearance.is_symlink(),
                    "quality_rework_order_present": review.is_file()
                    and not review.is_symlink()}
            for key, path in (("design", receipt), ("manifest", manifest)):
                try:
                    doc = safe_json(path)
                    if key == "design":
                        info["generator_capability_revision"] = doc.get(
                            "generator_capability_revision")
                        info["compiler_owned"] = doc.get("schema") == (
                            "saeit.factory.synthesis-receipt.v1")
                    else:
                        info["technical_qa_status"] = doc.get("qa_status")
                        info["professional_quality_approved"] = doc.get(
                            "professional_quality_approved")
                except (OSError, ValueError, TypeError):
                    info[key + "_readable"] = False
            details.append(info)
        return {"slot_state": "valid", "active_count": len(active),
                "waiting_count": len(waiting), "exited_count": len(exited),
                "active_details": details,
                "capacity": state.get("capacity"), "line_id": state.get("line_id")}
    except (OSError, ValueError, TypeError):
        return {"slot_state": "unreadable"}




def cycle_error_buckets(private):
    """Privacy-preserving roots of a live degraded manufacturing cycle."""
    path = private / "production-state.json"
    if not path.exists() and not path.is_symlink():
        return {"state": "absent"}
    try:
        data = safe_json(path, 2_000_000)
        if data.get("schema_version") != 1:
            return {"state": "invalid"}
        names = ("designer_failures", "research_failures",
                 "recipe_admission_failures", "quality_failures_this_cycle",
                 "source_recoveries", "source_evolutions",
                 "quality_return_build_candidates")
        result = {"state": "valid", "cycle_status": data.get("cycle_status")}
        for key in names:
            values = data.get(key)
            result[key + "_count"] = len(values) if isinstance(values, list) else None
        groups = collections.Counter()
        for row in data.get("designer_failures", []):
            if isinstance(row, dict):
                category = row.get("type")
                if isinstance(category, str) and re.fullmatch(r"[a-z_]{3,64}", category):
                    groups[category] += 1
                else:
                    groups["other"] += 1
        result["designer_failure_types"] = dict(groups)
        for name in ("product_candidates_processed", "registered_recipe_count",
                     "built_product_count", "source_evolution_attempted_count",
                     "genuinely_evolved_source_count", "manufacturing_failed_recipe_count",
                     "quality_returns_unresolved"):
            value = data.get(name)
            result[name] = value if type(value) is int and value >= 0 else None
        return result
    except (OSError, ValueError, TypeError, AttributeError):
        return {"state": "unreadable"}


def production_heartbeat(private):
    """Return only a schema-checked subset of real cycle counters and timestamps."""
    path = private / "production-health.json"
    if not path.exists() and not path.is_symlink():
        return {"state": "absent"}
    try:
        health = safe_json(path, 250000)
        if health.get("schema") != "saeit.factory.production-health.v1":
            return {"state": "invalid"}
        fields = ("last_cycle_finished_at_utc", "last_healthy_cycle_at_utc",
                  "cycle_status", "completed_cycles",
                  "consecutive_zero_new_cycles", "consecutive_degraded_cycles",
                  "new_or_updated_artifacts_this_cycle",
                  "new_distinct_product_ids_this_cycle",
                  "updated_existing_product_versions_this_cycle",
                  "zero_new_products_reason_code",
                  "independent_quality_returns_pending",
                  "commercial_quality_certified")
        result = {"state": "valid"}
        for field in fields:
            value = health.get(field)
            if value is None or type(value) in (int, bool) or (
                    isinstance(value, str) and len(value) <= 90):
                result[field] = value
            else:
                result[field] = "INVALID_FIELD"
        return result
    except (OSError, ValueError, TypeError):
        return {"state": "unreadable"}


def cron_production_channels(active):
    """Redacted scheduler classification; no command lines or tokens escape."""
    if active is None:
        return None
    rules = {
        "autonomous_cycle": r"autonomous-product-runtime|factory_vps_product_cycle|SAEIT_AUTONOMOUS_PRODUCTS_V2|SAEIT_FACTORY_EVERY_MINUTE_V1",
        "forty_family": r"factory[-_]40|family[-_]master|build50",
        "science_stage_workers": r"stage[2-6]|research-navigator|agri200|qc1000",
        "unreviewed_leech": r"leech",
    }
    return {k: sum(bool(re.search(regex, row, re.I)) for row in active)
            for k, regex in rules.items()}

def inventory():
    if os.geteuid() == 0 or any(p.is_symlink() or not p.is_dir()
                                for p in (BASE, PRIVATE, OPS, ORDERS)):
        raise RuntimeError("UNSAFE_OR_MISSING_FACTORY_ROOT")
    usage = shutil.disk_usage(PRIVATE)
    cron = command(["crontab", "-l"])
    active = ([line for line in cron.splitlines()
               if line.strip() and not line.lstrip().startswith("#")]
              if cron is not None else None)
    tags = (
        "SAEIT_STRICT_SERIAL_PRODUCT_TO_QC1000_20261025",
        "SAEIT_AGRI200_AUTONOMOUS_CLOSED_LOOP_V1",
        "SAEIT_AUTONOMOUS_PRODUCTS_V2",
        "SAEIT_FACTORY_EVERY_MINUTE_V1",
        "SAEIT_PRODUCTION_WAREHOUSE_V1",
    )
    timers = command(["systemctl", "list-timers", "--all", "--no-legend",
                      "--no-pager"])
    processes = command(["ps", "-eo", "args="])
    ids = []
    try:
        idx = safe_json(INDEX, 100000)
        listed = idx.get("order_ids_ranked")
        if isinstance(listed, list) and len(listed) <= 2000:
            ids = [v for v in listed if isinstance(v, str)
                   and ORDER_PATTERN.fullmatch(v)]
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    valid, missing, invalid = 0, 0, 0
    for ident in ids:
        path = ORDERS / (ident + ".json")
        if not path.exists() and not path.is_symlink():
            missing += 1
            continue
        try:
            doc = safe_json(path)
            if (doc.get("id") != ident or
                    doc.get("status") not in
                    ("issued", "in_engineering", "blocked_rework", "completed_verified") or
                    not HEX.fullmatch(str(doc.get("fingerprint", "")))):
                raise ValueError("invalid")
            valid += 1
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            invalid += 1
    order_status = collections.Counter()
    order_origins = collections.Counter()
    known_origins = {"site-topic-snapshot", "mojplaywin-site-qa-return",
                     "owner_requested_education700_p0"}
    unsafe = 0
    for path in ORDERS.iterdir():
        if path.suffix != ".json":
            continue
        try:
            doc = safe_json(path)
            status = doc.get("status")
            order_status[status if isinstance(status, str) else "UNSET"] += 1
            origin = doc.get("origin")
            order_origins[origin if isinstance(origin, str) and origin in known_origins else "other"] += 1
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            unsafe += 1
    serial = OPS / "strict-serial-fullcycle-v1.py"
    sha = None
    if serial.is_file() and not serial.is_symlink() and serial.stat().st_size < 200000:
        sha = hashlib.sha256(serial.read_bytes()).hexdigest()
    state = PRIVATE / "production-instructions/stage-06/strict-serial-active-v1.json"
    state_summary = {"present": state.is_file() and not state.is_symlink()}
    if state_summary["present"]:
        try:
            value = safe_json(state, 100000)
            state_summary.update({
                "last_cycle_utc": value.get("last_cycle_utc"),
                "all_complete": value.get("all_complete"),
                "last_order_certified": value.get("last_order_certified"),
            })
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            state_summary["read_error"] = True
    finished = PRIVATE / "product-lifecycle/approved-finished-goods"
    approved_archive_dirs = 0
    if finished.is_dir() and not finished.is_symlink():
        approved_archive_dirs = sum(1 for folder in finished.iterdir()
                                    if folder.is_dir() and not folder.is_symlink()
                                    and (folder / "product.zip").is_file()
                                    and (folder / "receipt.json").is_file())
    qa_root = PRIVATE / "design-intake/mpw-live-three-sku-qa"
    sku_copies = {}
    for ident in (72, 225, 879):
        location = qa_root / "copies" / str(ident)
        sku_copies[str(ident)] = (sum(1 for x in location.iterdir()
                                      if x.is_file() and not x.is_symlink())
                                  if location.is_dir() and not location.is_symlink() else 0)
    return {
        "schema": "saeit.factory.owner-vps-current-health.v1",
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True, "server_written_bytes": 0,
        "disk_total_gib": round(usage.total / 2**30, 3),
        "disk_free_gib": round(usage.free / 2**30, 3),
        "cron_readable": active is not None,
        "cron_active_count": len(active) if active is not None else None,
        "cron_marker_counts": ({tag: sum(tag in row for row in active)
                                for tag in tags} if active is not None else None),
        "leech_cron_like_count": (sum(bool(re.search("leech|WO-26102501", row, re.I))
                                      for row in active) if active is not None else None),
        "systemd_timers_readable": timers is not None,
        "related_timer_count": (sum(bool(re.search("factory|agri200|qc1000|strict.serial",
                                                    row, re.I)) for row in timers.splitlines())
                                if timers is not None else None),
        "process_inventory_readable": processes is not None,
        "related_process_count": (sum(bool(re.search("factory|agri200|strict.serial",
                                                     row, re.I)) for row in processes.splitlines())
                                  if processes is not None else None),
        "agri_index_entries": len(ids),
        "agri_existing_valid": valid, "agri_missing": missing, "agri_invalid": invalid,
        "current_order_file_status_counts": dict(order_status),
        "current_order_origin_counts": dict(order_origins),
        "current_order_unsafe": unsafe,
        "serial_worker_deployed_sha256": sha,
        "serial_tick": state_summary,
        "finished_archive_directories_with_receipts": approved_archive_dirs,
        "existing_three_sku_private_copies": sku_copies,
        "line41": line41_diagnostic(PRIVATE),
        "production_heartbeat": production_heartbeat(PRIVATE),
        "cycle_error_buckets": cycle_error_buckets(PRIVATE),
        "cron_production_channels": cron_production_channels(active),
    }


if __name__ == "__main__":
    print("FACTORY_OWNER_VPS_READONLY=" + json.dumps(inventory(), sort_keys=True))
