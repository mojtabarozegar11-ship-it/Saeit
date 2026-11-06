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
        status = data.get("runtime_health")
        if isinstance(status, dict):
            worker = {}
            if status.get("status") in ("ok", "needs_rework"):
                worker["status"] = status["status"]
            for key in ("expected_design_backlog_count", "fatal_design_failure_count"):
                value = status.get(key)
                if type(value) is int and value >= 0:
                    worker[key] = value
            if type(status.get("backlog_retained")) is bool:
                worker["backlog_retained"] = status["backlog_retained"]
            result["runtime_health"] = worker
        else:
            result["runtime_health"] = None
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


def quality_return_scope(private):
    """Separate current F01 rework from unrelated historical quality returns."""
    path = Path(private) / "production-state.json"
    if not path.exists() and not path.is_symlink():
        return {"state": "absent"}
    try:
        data = safe_json(path, 2_000_000)
        active = data.get("active_product_slot_recipes")
        section = data.get("quality_returns_to_production")
        candidates = data.get("quality_return_build_candidates")
        if (not isinstance(active, list) or not isinstance(section, dict)
                or not isinstance(section.get("orders"), list)
                or not isinstance(candidates, list)
                or any(not isinstance(x, str) or not RECIPE.fullmatch(x) for x in active)):
            return {"state": "invalid"}
        active_names = set(active)
        orders = section["orders"]
        if any(not isinstance(x, dict) or not isinstance(x.get("recipe"), str)
               for x in orders):
            return {"state": "invalid"}
        active_orders = sum(x["recipe"] in active_names for x in orders)
        statuses = collections.Counter()
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            if candidate.get("recipe") not in active_names:
                continue
            status = candidate.get("status")
            statuses[status if status in (
                "source_repair_still_required", "awaiting_independent_reinspection")
                else "other"] += 1
        return {
            "state": "valid",
            "total_open_quality_returns": len(orders),
            "active_product_count": len(active_names),
            "active_product_quality_returns": active_orders,
            "other_product_quality_returns": len(orders) - active_orders,
            "active_product_build_candidate_status_counts": dict(statuses),
            "invalid_order_count": section.get("invalid_orders"),
        }
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
        "single_product_runner": r"single-product-runtime/run-single-product-cycle[.]sh|SAEIT_SINGLE_PRODUCT_FACTORY_V1",
        "forty_family": r"factory[-_]40|family[-_]master|build50",
        "science_stage_workers": r"stage[2-6]|research-navigator|agri200|qc1000",
        "unreviewed_leech": r"leech",
    }
    return {k: sum(bool(re.search(regex, row, re.I)) for row in active)
            for k, regex in rules.items()}


def native_single_product_log_diagnostic(base):
    """Bounded, redacted evidence about a stalled cron; never emit log text."""
    log = Path(base) / "operations/single-product-cycle.log"
    if log.is_symlink():
        return {"state": "unsafe_symlink"}
    if not log.is_file():
        return {"state": "missing"}
    try:
        stat = log.stat()
        with log.open("rb") as stream:
            stream.seek(max(0, stat.st_size - 32768))
            tail = stream.read(32768).decode("utf-8", errors="replace")
        groups = {
            "python_traceback": r"Traceback \(most recent call last\)",
            "module_not_found": r"ModuleNotFoundError|ImportError",
            "file_missing": r"No such file or directory|FileNotFoundError",
            "permission_denied": r"Permission denied|PermissionError",
            "database_locked": r"database is locked|OperationalError",
            "timeout_or_killed": r"timed out|Terminated|Killed",
            "shell_failure": r"command not found|syntax error|unbound variable",
        }
        return {
            "state": "readable", "bytes": stat.st_size,
            "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            "tail_error_group_counts": {
                name: len(re.findall(pattern, tail, re.I))
                for name, pattern in groups.items()
            },
            "tail_line_count": len(tail.splitlines()),
        }
    except OSError:
        return {"state": "unreadable"}


def cron_recent_journal_diagnostic():
    """Aggregate the last ten minutes of cron's own journal; never print commands."""
    journal = command(["journalctl", "-t", "CRON", "--since", "10 minutes ago",
                       "--no-pager", "--output=cat"])
    if journal is None:
        return {"state": "unavailable"}
    if "No journal files were found" in journal or "No entries" in journal:
        return {"state": "empty_or_unavailable"}
    rows = journal.splitlines()[-3000:]
    return {
        "state": "readable",
        "recent_entry_count": len(rows),
        "githubops_job_count": sum("(githubops) CMD" in row for row in rows),
        "single_product_job_count": sum(
            "(githubops) CMD" in row and "single-product-runtime/" in row
            for row in rows
        ),
        "cron_job_error_count": sum(bool(re.search(
            r"BAD FILE MODE|BAD USERNAME|ERROR|RELOAD|No MTA installed", row,
            re.IGNORECASE)) for row in rows),
    }


def single_product_cron_wrapper_diagnostic(active):
    """Classify extra scheduler guards; never output cron source or arguments."""
    if active is None:
        return {"state": "unavailable"}
    rows = [r for r in active if "SAEIT_SINGLE_PRODUCT_FACTORY_V1" in r]
    if len(rows) != 1:
        return {"state": "missing_or_duplicate", "count": len(rows)}
    line = rows[0]
    runner = "/home/githubops/factory-runtime/operations/single-product-runtime/run-single-product-cycle.sh"
    timer = "/usr/bin/timeout 55s "
    log = "/home/githubops/factory-runtime/operations/single-product-cycle.log"
    start = line.find(timer)
    runner_at = line.find(runner)
    log_at = line.find(log)
    segment_lengths = (
        [start, runner_at - (start + len(timer)),
         log_at - (runner_at + len(runner)),
         len(line) - (log_at + len(log))]
        if start >= 0 and runner_at > start and log_at > runner_at else None
    )
    return {
        "state": "classified" if segment_lengths is not None else "unrecognized",
        "segment_lengths": segment_lengths,
        "extra_shell_and_count": line.count("&&"),
        "extra_shell_or_count": line.count("||"),
        "contains_test_guard": bool(re.search(r"\btest\b|\[.*\]", line)),
        "contains_flock": "flock" in line,
        "contains_shell_wrapper": "bash -c" in line or "sh -c" in line,
        "contains_paused_or_hold_guard": bool(re.search(r"PAUSE|HOLD|DISABLE|STOP", line, re.I)),
        "ends_expected_marker": line.endswith("# SAEIT_SINGLE_PRODUCT_FACTORY_V1"),
    }

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
    runner = BASE / "operations/single-product-runtime/run-single-product-cycle.sh"
    runner_info = {"present": False, "sha256": None, "executable": False}
    if runner.is_file() and not runner.is_symlink() and runner.stat().st_size < 100000:
        runner_info = {
            "present": True,
            "sha256": hashlib.sha256(runner.read_bytes()).hexdigest(),
            "executable": bool(runner.stat().st_mode & 0o111),
        }
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
        "single_product_cron_marker_count": (
            sum("SAEIT_SINGLE_PRODUCT_FACTORY_V1" in row for row in active)
            if active is not None else None),
        "native_single_product_runner": runner_info,
        "native_single_product_log": native_single_product_log_diagnostic(BASE),
        "cron_recent_journal": cron_recent_journal_diagnostic(),
        "single_product_cron_wrapper": single_product_cron_wrapper_diagnostic(active),
        "cron_service_state": (
            (lambda value: value if value in ("active\n", "inactive\n", "failed\n")
             else "unknown")(command(["systemctl", "is-active", "cron.service"]))
        ).strip(),
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
        "quality_return_scope": quality_return_scope(PRIVATE),
        "cron_production_channels": cron_production_channels(active),
    }


if __name__ == "__main__":
    print("FACTORY_OWNER_VPS_READONLY=" + json.dumps(inventory(), sort_keys=True))


# The disk-pressure extension is observational only and never modifies the VPS.
# It runs on request from the read-only workflow, with bounded subprocess time.
_DISK_LABELS = frozenset({
    "factory-runtime", "archives", "backup", "backups", "logs", "cache",
    "tmp", "data", ".cache", ".npm", ".local", "projects", "workspaces",
    "snapshots", ".config", ".pm2", ".docker", "venv", "virtualenv",
})


def _safe_child_label(path):
    name = path.name
    if name in _DISK_LABELS:
        return name
    return "other-" + hashlib.sha256(name.encode("utf8")).hexdigest()[:8]


def _du_largest_direct_children(directory, timeout_seconds):
    """Read-only bounded du, never emitting arbitrary paths or filenames."""
    if directory.is_symlink() or not directory.is_dir():
        return {"state": "unavailable"}
    try:
        run = subprocess.run(
            ["nice", "-n", "15", "du", "-x", "-B1", "--max-depth=1",
             str(directory)],
            capture_output=True, text=True, timeout=timeout_seconds,
            check=False)
    except subprocess.TimeoutExpired:
        return {"state": "timed_out", "timeout_seconds": timeout_seconds}
    except OSError:
        return {"state": "unavailable"}
    top = []
    for row in run.stdout.splitlines():
        if "\t" not in row:
            continue
        size, raw_path = row.split("\t", 1)
        if not size.isdecimal():
            continue
        path = Path(raw_path)
        if path == directory or path.parent != directory:
            continue
        top.append({"label": _safe_child_label(path), "bytes": int(size)})
    top.sort(key=lambda row: row["bytes"], reverse=True)
    return {"state": "complete" if run.returncode == 0 else "partial",
            "largest_direct_children": top[:15],
            "returned_child_count": len(top)}


def disk_pressure_map():
    """Bounded aggregate diagnostics; root or symlink surprises fail closed."""
    if os.geteuid() == 0 or BASE.is_symlink() or not BASE.is_dir():
        return {"state": "unsafe"}
    st = os.statvfs(BASE)
    return {
        "schema": "saeit.vps.disk-pressure-map.readonly.v1",
        "read_only": True, "server_written_bytes": 0,
        "filesystem_inode_total": st.f_files,
        "filesystem_inode_free": st.f_ffree,
        "home": _du_largest_direct_children(Path("/home/githubops"), 20),
        "factory": _du_largest_direct_children(BASE, 15),
        "system_logs": _du_largest_direct_children(Path("/var/log"), 8),
    }


if __name__ == "__main__":
    print("VPS_DISK_PRESSURE_READONLY=" + json.dumps(disk_pressure_map(), sort_keys=True))
