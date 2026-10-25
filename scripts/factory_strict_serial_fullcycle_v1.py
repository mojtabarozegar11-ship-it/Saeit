#!/usr/bin/env python3
"""One private factory product per tick with fair rework rotation; fail-closed.

A blocked product keeps its authentic state and returns on the next queue round;
it never monopolizes the minute scheduler while independent review is pending.
A minute is scheduling cadence, not a promise of scientific completion.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

SCHEMA = "saeit.factory.strict-serial-fullcycle.v1"
ORDER = re.compile(r"WO-[0-9]{8}\Z")
RESERVE = 2 * 1024**3
STAGES = (
    ("primary_source", "sequential-scientific-casework-v1.py", ("--max-source-attempts", "2"), 9),
    ("source_discovery", "stage2-literature-scout-serial.py",
     ("--batch", "1", "--workers", "1", "--query-burst", "1"), 8),
    ("source_validation", "stage2-research-serial.py", ("--batch", "1"), 5),
    ("design_prototype", "stage34-autonomous-handoff-serial.py", ("--batch", "2"), 5),
    ("manuscript", "stage5-evidence-workbook-serial.py", ("--batch", "1"), 5),
    ("technical_preflight", "stage6-preflight-rework-serial.py", ("--batch", "1"), 5),
    ("candidate_build", "research-navigator-serial.py", ("--batch", "1"), 5),
    ("strict_qc", "agri200-strict-qc1000-serial.py", ("--batch", "1"), 5),
    ("specific_rework", "stage5-substantive-rework-serial.py", ("--batch", "1"), 5),
    ("v003_reauthor", "agri200-source-grounded-v003-serial.py", ("--batch", "1"), 5),
    ("v003_mechanical_qc", "agri200-source-grounded-v003-qc-serial.py", ("--batch", "1"), 5),
)
EXCLUSIVE_MARKERS = (
    "SAEIT_SEQUENTIAL_SCIENCE_CASEWORK_20261025",
    "SAEIT_AGRI200_AUTONOMOUS_CLOSED_LOOP_V1",
    "SAEIT_AGRI200_STRICT_QC1000_V1",
    "SAEIT_FACTORY_STAGE2_SOURCE_DISCOVERY_V1",
    "SAEIT_QC184_LICENSED_ALTERNATIVE_DISCOVERY_20261024",
    "SAEIT_QC_V003_DOCTORAL_DEPTH_GATE_20261024",
    "SAEIT_QC_V003_SCIENTIFIC_REVIEW_HANDOFF_20261024",
)
SHARED_MARKERS = {
    "SAEIT_FACTORY_STAGE2_RESEARCH_V1": "stage2-research-serial.py",
    "SAEIT_FACTORY_STAGE34_AUTONOMOUS_HANDOFF_V1": "stage34-autonomous-handoff-serial.py",
    "SAEIT_FACTORY_STAGE5_EVIDENCE_WORKBOOK_V1": "stage5-evidence-workbook-serial.py",
    "SAEIT_FACTORY_STAGE5_SUBSTANTIVE_REWORK_V1": "stage5-substantive-rework-serial.py",
    "SAEIT_FACTORY_STAGE6_PREFLIGHT_REWORK_V1": "stage6-preflight-rework-serial.py",
    "SAEIT_SCIENCE_REWORK_ALL_20261024": "systemwide-scientific-source-rework-serial.py",
}
SERIAL_MARKER = "SAEIT_STRICT_SERIAL_PRODUCT_TO_QC1000_20261025"


def verify_cron_partition(contents):
    active = [row for row in contents.splitlines() if row.strip()
              and not row.lstrip().startswith("#")]
    if sum(SERIAL_MARKER in row for row in active) != 1:
        raise RuntimeError("STRICT_SERIAL_SCHEDULER_MISSING_OR_DUPLICATE")
    for line in active:
        if any(marker in line for marker in EXCLUSIVE_MARKERS):
            raise RuntimeError("STRICT_SERIAL_COMPETING_OWNER_WORKER")
        for marker, filename in SHARED_MARKERS.items():
            if marker in line and (line.count("--exclude-owner-agri200") != 1
                                   or line.count("/"+filename) != 1):
                raise RuntimeError("STRICT_SERIAL_SHARED_WORKER_UNPARTITIONED:"+marker)


def assert_live_cron_partition():
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True,
                            timeout=5, check=True)
    verify_cron_partition(result.stdout)


def checked_json(path, limit=2_000_000):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise RuntimeError("UNSAFE_OR_MISSING_SERIAL_EVIDENCE")
    return json.loads(path.read_text("utf8"))


def atomic(path, document):
    if path.is_symlink() or not path.parent.is_dir() or path.parent.is_symlink():
        raise RuntimeError("UNSAFE_SERIAL_STATE")
    fd, temp = tempfile.mkstemp(prefix=".strict-serial-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf8") as stream:
            json.dump(document, stream, sort_keys=True, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def source_sha256(path):
    """Hash actual private input/worker bytes, never invent a product hash."""
    if path.is_symlink() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def output_sha256(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.encode("utf8")
    return hashlib.sha256(value).hexdigest()


def immutable_tick_receipt(area, document):
    """Persist source-bound, immutable *process* evidence before cursor advance.

    A successful process exit is NOT an artifact hash or QC1000 certification.
    Failure to persist the receipt prevents the product queue from advancing.
    """
    folder = area / "stage-06" / "strict-serial-tick-receipts-v1"
    if folder.is_symlink() or folder.parent.is_symlink():
        raise RuntimeError("STRICT_SERIAL_RECEIPT_PATH_UNSAFE")
    folder.mkdir(mode=0o700, exist_ok=True)
    if folder.is_symlink() or not folder.is_dir():
        raise RuntimeError("STRICT_SERIAL_RECEIPT_PATH_UNSAFE")
    filename = "tick-" + uuid.uuid4().hex + ".json"
    payload = (json.dumps(document, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":")) + "\n").encode("utf8")
    target = folder / filename
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            target.unlink()
        except OSError:
            pass
        raise
    return str(target.relative_to(area)), hashlib.sha256(payload).hexdigest()


def index_orders(area):
    data = checked_json(area / "owner-agri200-p0-index.json")
    orders = data.get("order_ids_ranked")
    if (data.get("topic_count") != 200 or not isinstance(orders, list)
            or len(orders) != 200 or len(set(orders)) != 200
            or any(not isinstance(x, str) or not ORDER.fullmatch(x) for x in orders)):
        raise RuntimeError("STRICT_SERIAL_INDEX_INVALID")
    return orders


def verified_intake(area, order):
    if not ORDER.fullmatch(order):
        raise RuntimeError("STRICT_SERIAL_BAD_WORK_ORDER")
    item = checked_json(area / "orders" / (order + ".json"), 250_000)
    if (item.get("id") != order
            or item.get("status") not in ("issued", "in_engineering", "blocked_rework", "completed_verified")
            or re.fullmatch(r"[0-9a-f]{64}", str(item.get("fingerprint", ""))) is None):
        raise RuntimeError("STRICT_SERIAL_STAGE1_WORK_ORDER_INVALID")
    return True


def intake_failure(area, order):
    """Return a precise private rework blocker; never silently drop an order."""
    try:
        verified_intake(area, order)
    except (OSError, RuntimeError, ValueError, TypeError, UnicodeError) as exc:
        return type(exc).__name__ + ":" + str(exc)[:120]
    return None


def selected_order(path, orders):
    if not path.exists() and not path.is_symlink():
        return orders[0], 0, 0
    d = checked_json(path, 8192)
    if (d.get("schema") == SCHEMA and d.get("all_complete") is True
            and d.get("active_order") is None and d.get("index") == len(orders)):
        return None, len(orders), 0
    if (d.get("schema") != SCHEMA or not isinstance(d.get("active_order"), str)
            or d["active_order"] not in orders
            or type(d.get("index")) is not int
            or d["index"] < 0 or d["index"] >= len(orders)
            or orders[d["index"]] != d["active_order"]
            or type(d.get("ticks")) is not int or d["ticks"] < 0):
        raise RuntimeError("STRICT_SERIAL_STATE_INVALID")
    return d["active_order"], d["index"], d["ticks"]


def load_governance(ops):
    path = ops.parent / "12-stage-governance/factory_12_stage_governance.py"
    if not path.is_file() or path.is_symlink():
        return None
    spec = importlib.util.spec_from_file_location("strict_serial_governance", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def certified_finished(root, order, governance=None):
    """Accept only the existing 12-stage gate's signed, version-bound stock."""
    house = root / "product-lifecycle/approved-finished-goods" / order
    receipt = house / "receipt.json"
    archive = house / "product.zip"
    if governance is None or not receipt.is_file() or not archive.is_file():
        return False
    try:
        if house.is_symlink() or archive.is_symlink() or receipt.is_symlink():
            return False
        record = governance.load_order(root, order)
        passport = governance.spec_path(root, order)
        meta = checked_json(receipt, 100_000)
        if (record.get("status") != "in_finished_goods_warehouse_not_distributed"
                or record.get("final_warehouse_id") != order
                or any(record["stage_status"].get(str(i)) != "passed" for i in range(1, 12))
                or meta.get("order") != order or meta.get("stage_gates_passed") != 10
                or meta.get("passport_sha256") != governance.sha(passport)
                or meta.get("artifact_sha256") != governance.sha(archive)):
            return False
        governance.verify_persisted_approvals(root, order, record)
        governance.verify_final_package_zip(archive)
        return True
    except (OSError, ValueError, TypeError, RuntimeError, KeyError):
        return False


def next_uncertified_order(root, orders, index, governance):
    """Round-robin over work orders, skipping only independently verified stock.

    Missing governance never authorizes a skip. Every candidate is rechecked
    to prevent a stale cursor silently dropping uncertified products.
    """
    for offset in range(1, len(orders) + 1):
        candidate = (index + offset) % len(orders)
        if not certified_finished(root, orders[candidate], governance):
            return orders[candidate], candidate
    return None, len(orders)


def worker_args(root, ops, order, stage):
    name, file, args, _ = stage
    script = ops / file
    if not script.is_file() or script.is_symlink():
        raise RuntimeError("STRICT_SERIAL_WORKER_UNAVAILABLE:" + name)
    py = ops.parent.parent / ".venv/bin/python"
    if not py.is_file() or not os.access(py, os.X_OK):
        raise RuntimeError("STRICT_SERIAL_VENV_MISSING")
    command = [str(py), "-B", str(script), "--factory-private", str(root)]
    p = lambda value: str(ops / value)
    if name == "primary_source":
        command += ["--only-order-file", order + "--r001.json"]
    elif name == "source_discovery":
        command += ["--stage2-program", p("stage2-research-serial.py")]
    elif name == "manuscript":
        command += ["--stage34-worker", p("stage34-autonomous-handoff-serial.py")]
    elif name in ("technical_preflight", "candidate_build", "strict_qc"):
        command += ["--stage34-worker", p("stage34-autonomous-handoff-serial.py"),
                    "--stage5-worker", p("stage5-evidence-workbook-serial.py")]
    elif name == "specific_rework":
        command += ["--stage34-worker", p("stage34-autonomous-handoff-serial.py"),
                    "--stage5-worker", p("stage5-evidence-workbook-serial.py"),
                    "--stage6-worker", p("stage6-preflight-rework-serial.py")]
    elif name == "v003_reauthor":
        command += ["--stage34-worker", p("stage34-autonomous-handoff-serial.py"),
                    "--stage5-worker", p("stage5-evidence-workbook-serial.py"),
                    "--candidate-worker", p("research-navigator-serial.py")]
    elif name == "v003_mechanical_qc":
        command += ["--stage34-worker", p("stage34-autonomous-handoff-serial.py")]
    if name == "strict_qc":
        command += ["--criteria", p("agri200-strict-qc-catalog.json")]
    if name != "primary_source":
        command += ["--only-order-id", order]
    return command + list(args)


def tick(factory_private, operations, *, dry_run=False, runner=None,
         disk_usage=shutil.disk_usage, monotonic=time.monotonic, budget=51,
         require_scheduler_scope=False):
    root = Path(factory_private)
    ops = Path(operations)
    area = root / "production-instructions"
    if any(p.is_symlink() or not p.is_dir() for p in (root, ops, area)):
        raise RuntimeError("STRICT_SERIAL_ROOT_UNSAFE")
    orders = index_orders(area)
    if require_scheduler_scope:
        assert_live_cron_partition()
    state = area / "stage-06/strict-serial-active-v1.json"
    order, index, ticks = selected_order(state, orders)
    governance = load_governance(ops)
    if order is None:
        if not all(certified_finished(root, item, governance) for item in orders):
            raise RuntimeError("STRICT_SERIAL_QUEUE_COMPLETION_UNVERIFIED")
        return {"schema":SCHEMA, "all_complete":True, "stages_executed":0,
                "sites_modified":False, "publications":0}
    # Do not reject a broken intake before acquiring the per-tick lock:
    # that would freeze the same selected order on every future minute.
    # Dry-run remains read-only and surfaces the exact integrity blocker.
    if dry_run:
        problem = intake_failure(area, order)
        return {"schema":SCHEMA, "active_order":order, "tick_number":ticks,
                "certified":problem is None and certified_finished(root, order, governance),
                "intake_blocker":problem,
                "storage_hold":disk_usage(root).free < RESERVE,
                "stages_executed":0, "sites_modified":False}
    lock = ops / ".strict-serial-fullcycle.lock"
    if lock.is_symlink():
        raise RuntimeError("STRICT_SERIAL_LOCK_UNSAFE")
    descriptor = os.open(str(lock), os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"schema":SCHEMA, "already_running":True, "stages_executed":0}
        # Re-read after locking: even a second scheduler cannot roll forward.
        order, index, ticks = selected_order(state, orders)
        if order is None:
            if not all(certified_finished(root, item, governance) for item in orders):
                raise RuntimeError("STRICT_SERIAL_QUEUE_COMPLETION_UNVERIFIED")
            return {"schema":SCHEMA, "all_complete":True, "stages_executed":0,
                    "publications":0}
        problem = intake_failure(area, order)
        began = monotonic()
        actual_began = time.perf_counter()
        process_evidence = {}
        # A corrupt/missing work-order cannot be certified by this worker.
        certified = problem is None and certified_finished(root, order, governance)
        results = {}
        hold = disk_usage(root).free < RESERVE
        if problem is not None:
            results["intake"] = "BLOCKED_" + problem
            for stage in STAGES:
                results[stage[0]] = "SKIPPED_INVALID_INTAKE"
        if not certified and problem is None:
            for stage in STAGES:
                label = stage[0]
                # A primary-source acquisition can download new files too.
                # Recheck before EVERY stage, not just once at tick start: a
                # prior worker may consume the last free bytes in this tick.
                if disk_usage(root).free < RESERVE:
                    hold = True
                if hold:
                    results[label] = "STORAGE_RESERVE_HOLD"
                    continue
                remaining = budget - (monotonic() - began)
                if remaining < 2:
                    results[label] = "DEFERRED_TO_NEXT_MINUTE"
                    continue
                try:
                    command = worker_args(root, ops, order, stage)
                    source_before = source_sha256(ops / stage[1])
                    process_began = time.perf_counter()
                    try:
                        completed = (runner or subprocess.run)(
                            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=max(1, min(stage[3], remaining-1)), check=False)
                    finally:
                        process_evidence.setdefault(label, {})["elapsed_ms"] = max(
                            0, round((time.perf_counter() - process_began) * 1000))
                    process_evidence[label].update({
                        "worker_sha256_before": source_before,
                        "stdout_sha256": output_sha256(getattr(completed, "stdout", None)),
                        "stderr_sha256": output_sha256(getattr(completed, "stderr", None)),
                        "exit_code": completed.returncode,
                    })
                    results[label] = ("EXECUTED" if completed.returncode == 0
                                      else "BLOCKED_WORKER_EXIT_" + str(completed.returncode))
                except subprocess.TimeoutExpired:
                    results[label] = "DEFERRED_TIMEOUT"
                except (OSError, RuntimeError, ValueError) as exc:
                    results[label] = "BLOCKED_" + type(exc).__name__ + ":" + str(exc)[:80]
            certified = certified_finished(root, order, governance)
        # Exactly one selected order per tick. Unfinished work is revisited
        # after other orders have had a fair chance to progress.
        next_order, next_index = next_uncertified_order(root, orders, index, governance)
        all_complete = next_order is None
        decision = "CERTIFIED_AND_EXIT" if certified else "RETURN_TO_PRODUCTION"
        blocked = [label for label, status in results.items() if status != "EXECUTED"]
        if not certified and not blocked:
            blocked = ["independent_scientific_review_or_authentic_rework"]
        # Persist a verifiable receipt for the one selected product, including
        # skipped/blocked stages. No stage is represented as independently passed.
        stage_receipts = {}
        for label, filename, _, _ in STAGES:
            evidence = dict(process_evidence.get(label, {}))
            evidence.update({
                "process_status": results.get(label, "SKIPPED_ALREADY_CERTIFIED"),
                "worker_sha256_after": source_sha256(ops / filename),
                "artifact_sha256": None,  # no validated version-specific artifact
            })
            before = evidence.get("worker_sha256_before")
            after = evidence["worker_sha256_after"]
            evidence["worker_source_changed"] = (before is not None and
                                                  before != after)
            stage_receipts[label] = evidence
        receipt_document = {
            "schema": "saeit.factory.strict-serial-tick-receipt.v1",
            "recorded_utc": datetime.now(timezone.utc).isoformat(),
            "order_id": order,
            "order_intake_sha256": source_sha256(area / "orders" / (order + ".json")),
            "product_version_before": None,
            "product_version_after": None,
            "product_version_evidence": "NOT_PROVEN",
            "decision": decision,
            "rework_blockers": blocked,
            "intake_blocker": problem,
            "stage_receipts": stage_receipts,
            "runtime_ms": max(0, round((time.perf_counter() - actual_began) * 1000)),
            "independent_qa1000_receipt_sha256": None,
            "commercial_release": False,
        }
        receipt_file, receipt_sha256 = immutable_tick_receipt(area, receipt_document)
        atomic(state, {"schema":SCHEMA, "active_order":next_order,
                       "last_tick_receipt_file": receipt_file,
                       "last_tick_receipt_sha256": receipt_sha256,
                       "index":next_index, "ticks":0,  # reset per-order tick counter on rotation
                       "all_complete":all_complete,
                       "last_order":order, "last_order_certified":certified,
                       "last_decision":decision, "last_blockers":blocked,
                       "intake_blocker":problem,
                       "rework_stage_owner":"intake_integrity" if problem else ("independent_quality_review" if not certified else None),
                       "required_next_version":"AUTHENTIC_REWORK_VERSION" if not certified else None,
                       "last_cycle_utc":datetime.now(timezone.utc).isoformat(),
                       "stage_results":results, "storage_hold":hold,
                       "independent_approval_required":True,
                       "commercial_release":False, "sites_modified":False})
        return {"schema":SCHEMA, "processed_order":order,
                "active_order_after_cycle":next_order,
                "decision":decision, "rework_blockers":blocked,
                "tick_receipt_file":receipt_file,
                "tick_receipt_sha256":receipt_sha256,
                "runtime_ms":receipt_document["runtime_ms"],
                "intake_blocker":problem,
                "rework_stage_owner":"intake_integrity" if problem else ("independent_quality_review" if not certified else None),
                "required_next_version":"AUTHENTIC_REWORK_VERSION" if not certified else None,
                "certified_to_private_finished_goods":certified,
                "stages_executed":sum(v=="EXECUTED" for v in results.values()),
                "stage_results":results, "storage_hold":hold, "tick_number":ticks+1,
                "publications":0, "automatic_quality_approvals":0}
    finally:
        os.close(descriptor)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--factory-private", required=True)
    p.add_argument("--operations", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--require-scheduler-scope", action="store_true")
    args = p.parse_args()
    try:
        print(json.dumps(tick(args.factory_private,args.operations,dry_run=args.dry_run,
                              require_scheduler_scope=args.require_scheduler_scope),
                         ensure_ascii=False, sort_keys=True), flush=True)
    except Exception as exc:
        print("STRICT_SERIAL_CYCLE_ERROR="+type(exc).__name__+":"+str(exc)[:160], file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
