#!/usr/bin/env python3
"""Remove only unapproved, WO-keyed private stage artifacts; never store/fulfillment.

Fails closed on unsafe filesystem topology, ambiguous order state, active writer,
unexpected cron content, missing invariant, or anything outside six stage roots.
The order list, all lifecycle records, warehouse, customer packs, and stores are
intentionally untouched.
"""
from __future__ import annotations

import argparse
import collections
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

HOME = Path("/home/githubops")
ROOT = HOME / "factory-runtime/private/autonomous-product-cycle"
AREA = ROOT / "production-instructions"
OPS = HOME / "factory-runtime/operations/production-instructions"
BACKUPS = HOME / "factory-runtime/operations/backups"
ORDER_RE = re.compile(r"WO-[0-9]{8}\Z")
WO_PREFIX = re.compile(r"^(WO-[0-9]{8})(?=$|[-.])")
PAUSE_MARKERS = (
    "SAEIT_STRICT_SERIAL_PRODUCT_TO_QC1000_20261025",
    "SAEIT_FACTORY_STAGE2_RESEARCH_V1",
    "SAEIT_FACTORY_STAGE34_AUTONOMOUS_HANDOFF_V1",
    "SAEIT_FACTORY_STAGE5_EVIDENCE_WORKBOOK_V1",
    "SAEIT_FACTORY_STAGE5_SUBSTANTIVE_REWORK_V1",
    "SAEIT_FACTORY_STAGE6_PREFLIGHT_REWORK_V1",
    "SAEIT_SCIENCE_REWORK_ALL_20261024",
    "SAEIT_FACTORY_STAGE2_SOURCE_DISCOVERY_V1",
    "SAEIT_AGRI200_AUTONOMOUS_CLOSED_LOOP_V1",
    "SAEIT_AGRI200_STRICT_QC1000_V1",
)
STAGE_NAMES = tuple("stage-%02d" % i for i in range(1, 7))
GUARDED_FIELDS = (
    "manufacturing_qa_passed", "warehouse_goods_created",
    "technical_product_release", "publication_approved",
    "public_distribution_allowed",
)


def check_folder(p: Path) -> None:
    if p.is_symlink() or not p.is_dir():
        raise RuntimeError("EXPECTED_PRIVATE_DIRECTORY:" + p.name)


def orders_and_protection() -> tuple[set[str], dict]:
    if os.geteuid() == 0 or os.getenv("USER") != "githubops":
        raise RuntimeError("MUST_RUN_AS_GITHUBOPS_NOT_ROOT")
    for p in (HOME, ROOT, AREA, OPS, BACKUPS, AREA / "orders"):
        check_folder(p)
    path = AREA / "orders"
    all_files = sorted(path.iterdir())
    if len(all_files) < 2000 or any(p.is_symlink() or not p.is_file()
                                  or not ORDER_RE.fullmatch(p.stem)
                                  or p.suffix != ".json" for p in all_files):
        raise RuntimeError("ORDER_SET_MISSING_OR_UNSAFE")
    eligible = set()
    kinds = collections.Counter()
    for p in all_files:
        if p.stat().st_size > 256_000:
            raise RuntimeError("WORK_ORDER_UNEXPECTED_SIZE")
        item = json.loads(p.read_text(encoding="utf-8"))
        if item.get("id") != p.stem or item.get("status") not in (
                "issued", "blocked_rework", "in_engineering", "completed_verified"):
            raise RuntimeError("WORK_ORDER_UNRECOGNIZED_STATE")
        kinds[str(item["status"])] += 1
        if item["status"] == "completed_verified":
            continue
        if any(item.get(field) is True for field in GUARDED_FIELDS):
            continue
        if item.get("requires_customer_order") is True:
            continue
        if (ROOT / "product-lifecycle/approved-finished-goods" / p.stem).exists():
            continue
        if (ROOT / "production-warehouse/finished" / p.stem).exists():
            continue
        eligible.add(p.stem)
    if not eligible:
        raise RuntimeError("NO_PROVABLY_INCOMPLETE_WORK_ORDERS")
    return eligible, {"order_files_preserved":len(all_files),
                      "order_statuses":dict(kinds),"incomplete_eligible":len(eligible)}


def enumerate_stage_artifacts(eligible: set[str]):
    files = set()
    dirs = set()
    skipped = collections.Counter()
    for stage_name in STAGE_NAMES:
        stage = AREA / stage_name
        check_folder(stage)
        for base, child_dirs, names in os.walk(stage, topdown=True, followlinks=False):
            parent = Path(base)
            if parent.is_symlink():
                raise RuntimeError("UNSAFE_SYMLINK_STAGE")
            child_dirs.sort()
            names.sort()
            for entry in child_dirs + names:
                p = parent / entry
                if p.is_symlink():
                    raise RuntimeError("UNSAFE_SYMLINK_STAGE_ENTRY")
                if not (p.is_dir() or p.is_file()):
                    raise RuntimeError("UNSAFE_SPECIAL_STAGE_ENTRY")
            matched_ids = []
            for c in parent.relative_to(stage).parts:
                match = WO_PREFIX.match(c)
                if match: matched_ids.append(match.group(1))
            if len(set(matched_ids)) > 1:
                raise RuntimeError("CROSS_ORDER_NESTED_ARTIFACT")
            family_order = matched_ids[-1] if matched_ids else None
            for name in names:
                p = parent / name
                match = WO_PREFIX.match(name)
                target = family_order or (match.group(1) if match else None)
                if target not in eligible:
                    if target: skipped["protected_or_not_eligible"] += 1
                    continue
                if p.stat().st_nlink != 1:
                    raise RuntimeError("HARDLINKED_PRIVATE_ARTIFACT")
                files.add(p)
            if family_order in eligible:
                dirs.add(parent)
            for name in child_dirs:
                match = WO_PREFIX.match(name)
                if match and match.group(1) in eligible:
                    dirs.add(parent / name)
    ordered_files = sorted(files, key=lambda x:(len(x.parts),str(x)), reverse=True)
    ordered_dirs = sorted(dirs, key=lambda x:(len(x.parts),str(x)), reverse=True)
    return ordered_files, ordered_dirs, dict(skipped)


def fingerprint_orders():
    h = hashlib.sha256()
    for p in sorted((AREA / "orders").iterdir()):
        h.update(p.name.encode())
        h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def cron_freeze(run_id: str):
    if not re.fullmatch(r"[0-9]{5,15}-[0-9]{1,3}", run_id):
        raise RuntimeError("INVALID_GITHUB_RUN_ID")
    before = subprocess.run(["crontab", "-l"], capture_output=True, text=True,
                            timeout=8, check=True).stdout
    if "SAEIT_STRICT_SERIAL_PRODUCT_TO_QC1000_20261025" not in before:
        raise RuntimeError("EXPECTED_STRICT_SERIAL_SCHEDULER_MISSING")
    if sum("SAEIT_STRICT_SERIAL_PRODUCT_TO_QC1000_20261025" in line
           and not line.lstrip().startswith("#")
           for line in before.splitlines()) != 1:
        raise RuntimeError("UNEXPECTED_FACTORY_SCHEDULER")
    result = []
    paused = collections.Counter()
    for line in before.splitlines():
        if line.lstrip().startswith("#"):
            result.append(line)
            continue
        matching = [m for m in PAUSE_MARKERS if m in line]
        if matching:
            if not ("factory-runtime/operations/production-instructions/" in line):
                raise RuntimeError("UNRECOGNIZED_PRODUCER_PATH")
            if len(matching) != 1:
                raise RuntimeError("AMBIGUOUS_PRODUCER_CRON")
            paused[matching[0]] += 1
            result.append("# PAUSED_FOR_INCOMPLETE_WO_PURGE_20261025 " + line)
        else:
            result.append(line)
    if paused["SAEIT_STRICT_SERIAL_PRODUCT_TO_QC1000_20261025"] != 1:
        raise RuntimeError("STRICT_SERIAL_WOULD_NOT_STOP")
    backup = BACKUPS / ("incomplete-wo-purge-" + run_id + ".cron")
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("BACKUP_PATH_ALREADY_EXISTS")
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write(before)
        out.flush()
        os.fsync(out.fileno())
    fd, tmp = tempfile.mkstemp(prefix=".incomplete-cron-", dir=str(OPS))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write("\n".join(result) + "\n")
        subprocess.run(["crontab",tmp],timeout=8,check=True)
        after = subprocess.run(["crontab","-l"],capture_output=True,
                               text=True,timeout=8,check=True).stdout
        if after != "\n".join(result)+"\n":
            raise RuntimeError("CRONTAB_POSTWRITE_MISMATCH")
    except Exception:
        subprocess.run(["crontab",str(backup)],timeout=8,check=False)
        raise
    finally:
        os.unlink(tmp)
    return backup, dict(paused)


def acquire_worker_locks():
    locations = [OPS/".strict-serial-fullcycle.lock",
                 AREA/".stage34-worker.lock", AREA/".stage5-worker.lock",
                 AREA/".stage6-preflight.lock",
                 AREA/".research-navigator-build.lock",
                 AREA/".strict-qc1000.lock",
                 AREA/"stage-02/.worker.lock"]
    handles = []
    try:
        for p in locations:
            if p.is_symlink(): raise RuntimeError("WORKER_LOCK_SYMLINK")
            fd = os.open(p, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(fd)
                raise RuntimeError("WORKER_STILL_RUNNING")
            handles.append(fd)
        return handles
    except Exception:
        for fd in handles: os.close(fd)
        raise


def execute(apply: bool, run_id: str) -> dict:
    eligible, info = orders_and_protection()
    before = fingerprint_orders()
    cron_backup = None
    locked = []
    files_deleted = False
    try:
        if apply:
            cron_backup, paused = cron_freeze(run_id)
            locked = acquire_worker_locks()
        else:
            paused = {}
        files, dirs, skipped = enumerate_stage_artifacts(eligible)
        bytes_total = sum(p.stat().st_size for p in files)
        info.update({"mode":"APPLY" if apply else "DRY_RUN",
                     "candidate_private_artifact_files":len(files),
                     "candidate_private_order_directories":len(dirs),
                     "candidate_file_bytes":bytes_total,
                     "skipped":skipped,
                     "paused_cron_markers":paused,
                     "sites_modified":False,
                     "customer_packs_modified":False,
                     "warehouse_modified":False,
                     "order_files_modified":False})
        if apply:
            files_deleted = bool(files)
            for p in files:
                p.unlink()
            for p in dirs:
                try: p.rmdir()
                except OSError: pass  # Non-WO material prevents removal; never force.
            if any(p.exists() for p in files):
                raise RuntimeError("STAGE_FILES_NOT_FULLY_REMOVED")
            info["deleted_private_artifact_files"] = len(files)
            info["removed_private_artifact_bytes"] = bytes_total
            info["cron_backup_preserved"] = cron_backup.name
        if fingerprint_orders() != before:
            raise RuntimeError("ORDER_FILES_CHANGED_DURING_CLEANUP")
        return info
    except Exception:
        # No attempt to recreate already deleted files. Keep writers paused
        # after any destructive phase; otherwise restore prior cron if no data changed.
        if cron_backup is not None and not files_deleted:
            subprocess.run(["crontab",str(cron_backup)],check=False,timeout=8)
        raise
    finally:
        for fd in locked: os.close(fd)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--apply",action="store_true")
    a.add_argument("--run-id",default="00000-1")
    args=a.parse_args()
    outcome=execute(args.apply,args.run_id)
    print("INCOMPLETE_WO_PURGE_RESULT=" +
          json.dumps(outcome,ensure_ascii=False,sort_keys=True), flush=True)


if __name__=="__main__":
    try: main()
    except Exception as e:
        print("INCOMPLETE_WO_PURGE_FAILED="+str(type(e).__name__)+":"+str(e)[:180],
              file=sys.stderr,flush=True)
        sys.exit(1)
