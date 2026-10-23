#!/usr/bin/env python3
"""Bounded VPS-private factory supervisor acting under standing owner instruction.

Runs already installed stages 1, 2 literature evidence, 2 handoff, 3/4,
5, 6 technical preflight, and 5 revision in independent bounded steps. All internal decisions run without owner confirmation.
No independent human attestations, legal certifications, public release, site
updates, purchases, or disbursements can be issued by this supervisor.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SCHEMA = "saeit.factory.delegated-internal-autonomy.v2"
# Each stage is isolated: missing/failing prerequisites affect that stage only.
# Unrelated stages still run and can process valid work already in their inbox.
STEPS = (
    ("stage1", "stage1-handoff.py", ()),
    ("stage2_scout", "stage2-literature-scout.py", ("stage2",)),
    ("stage2", "stage2-research.py", ()),
    ("stage34", "stage34-autonomous-handoff.py", ()),
    ("stage5", "stage5-evidence-workbook.py", ("stage34",)),
    ("stage6", "stage6-preflight-rework.py", ("stage34", "stage5")),
    ("stage5_rework", "stage5-substantive-rework.py",
     ("stage34", "stage5", "stage6")),
)
COUNTERS = {
    "stage1_receipts": "stage-01/receipts",
    "stage2_source_evidence": "stage-02/source-evidence",
    "stage2_receipts": "stage-02/receipts",
    "stage3_receipts": "stage-03/receipts",
    "stage4_receipts": "stage-04/receipts",
    "stage5_drafts": "stage-05/completed-drafts",
    "stage6_preflights": "stage-06/technical-preflight",
    "stage5_revision_briefs": "stage-05/substantive-revision-manifests",
}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def regular(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("AUTONOMY_UNSAFE_EXECUTABLE:" + path.name)
    return path


def inventory(area):
    result = {}
    for key, subdir in COUNTERS.items():
        folder = area / subdir
        if folder.is_symlink():
            raise RuntimeError("AUTONOMY_UNSAFE_QUEUE:" + key)
        if not folder.is_dir():
            result[key] = 0
            continue
        result[key] = sum(
            p.is_file() and not p.is_symlink() and
            (p.name.startswith("AGRI-") if key == "stage2_source_evidence" else p.name.startswith("WO-")) and p.suffix == ".json"
            for p in folder.iterdir()
        )
    return result


def atomic_json(target, value):
    if target.is_symlink() or target.parent.is_symlink():
        raise RuntimeError("AUTONOMY_UNSAFE_STATUS_PATH")
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=str(target.parent),
        prefix=".owner-delegate-", delete=False
    ) as handle:
        temp = Path(handle.name)
        os.chmod(temp, 0o600)
        try:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    os.replace(temp, target)


def commands(ops, root, python, batch):
    paths = {key: ops / filename for key, filename, deps in STEPS}
    base = [str(python), "-B"]
    shared = ["--factory-private", str(root)]
    stage34 = ["--stage34-worker", str(paths["stage34"])]
    stage5 = ["--stage5-worker", str(paths["stage5"])]
    stage6 = ["--stage6-worker", str(paths["stage6"])]
    return (
        ("stage1", base + [str(paths["stage1"])] + shared +
         ["--batch", str(min(1000, max(600, batch * 3)))]),
        ("stage2_scout", base + [str(paths["stage2_scout"])] + shared +
         ["--stage2-program", str(paths["stage2"]), "--batch", str(min(12, batch)),
          "--workers", "1", "--query-burst", "1"]),
        ("stage2", base + [str(paths["stage2"])] + shared +
         ["--batch", str(max(300, batch))]),
        ("stage34", base + [str(paths["stage34"])] + shared +
         ["--batch", str(batch)]),
        ("stage5", base + [str(paths["stage5"])] + shared + stage34 +
         ["--batch", str(batch)]),
        ("stage6", base + [str(paths["stage6"])] + shared + stage34 +
         stage5 + ["--batch", str(batch)]),
        ("stage5_rework", base + [str(paths["stage5_rework"])] + shared +
         stage34 + stage5 + stage6 + ["--batch", str(batch)]),
    )


def execute(root, operations, python, batch=200, timeout=150):
    if not 1 <= batch <= 200 or not 10 <= timeout <= 300:
        raise RuntimeError("AUTONOMY_BOUNDED_RESOURCES_REQUIRED")
    root = Path(root).expanduser().resolve(strict=True)
    operations = Path(operations).expanduser().resolve(strict=True)
    # Virtualenv's python executable is commonly a symlink to its interpreter.
    python = Path(python).expanduser()
    if not python.is_file() or not os.access(python, os.X_OK):
        raise RuntimeError("AUTONOMY_PYTHON_NOT_EXECUTABLE")
    if not root.is_dir() or not operations.is_dir():
        raise RuntimeError("AUTONOMY_PRIVATE_FACTORY_MISSING")
    area = root / "production-instructions"
    if not area.is_dir() or area.is_symlink():
        raise RuntimeError("AUTONOMY_PRIVATE_INSTRUCTIONS_MISSING")
    steps = commands(operations, root, python, batch)
    lock = area / ".delegated-internal-autonomy.lock"
    if lock.is_symlink():
        raise RuntimeError("AUTONOMY_LOCK_SYMLINK")
    with lock.open("a+b") as guard:
        os.fchmod(guard.fileno(), 0o600)
        try:
            fcntl.flock(guard.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"schema": SCHEMA, "status": "already_running"}
        before = inventory(area)
        receipts = []
        names = {name: operations / filename for name, filename, deps in STEPS}
        dependencies = {name: (name,) + deps for name, filename, deps in STEPS}
        for stage, argv in steps:
            unavailable = []
            for dep in dependencies[stage]:
                target = names[dep]
                if target.is_symlink() or not target.is_file():
                    unavailable.append(dep)
            if unavailable:
                receipts.append({
                    "stage": stage, "executed": False, "exit_code": None,
                    "result_excerpt": "STAGE_DEPENDENCY_MISSING:" + ",".join(unavailable),
                    "passed": False,
                })
                continue
            try:
                proc = subprocess.run(
                    argv, shell=False, cwd=str(operations),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, timeout=timeout, check=False
                )
                receipts.append({
                    "stage": stage, "executed": True,
                    "exit_code": proc.returncode,
                    "result_excerpt": proc.stdout[-1200:],
                    "passed": proc.returncode == 0,
                })
            except (subprocess.TimeoutExpired, OSError) as exc:
                receipts.append({
                    "stage": stage, "executed": True, "exit_code": None,
                    "result_excerpt": type(exc).__name__ + ":" + str(exc)[:200],
                    "passed": False,
                })
        after = inventory(area)
        gains = {key: max(0, after[key] - before[key]) for key in COUNTERS}
        failures = [r["stage"] for r in receipts if not r["passed"]]
        status = "degraded" if failures else "advanced" if any(gains.values()) else "idle"
        previous_path = area / "delegated-internal-autonomy-status.json"
        previous = {}
        if previous_path.is_file() and not previous_path.is_symlink():
            try:
                previous = json.loads(previous_path.read_text(encoding="utf-8"))
                if not isinstance(previous, dict):
                    previous = {}
            except (OSError, ValueError):
                previous = {}
        prior_no_progress = previous.get("consecutive_zero_progress_cycles", 0)
        if type(prior_no_progress) is not int or prior_no_progress < 0:
            prior_no_progress = 0
        result = {
            "schema": SCHEMA, "status": status, "finished_at_utc": utcnow(),
            "operating_authority": {
                "principal": "factory_owner",
                "representative": "saeit-autonomous-factory-owner-delegate",
                "basis": "standing_owner_authorization_recorded_in_conversation",
                "scope": ["private_production", "internal_technical_checks",
                          "rework", "bounded_auto_retries", "internal_handoffs"],
                "repeat_owner_confirmation_required_for_internal_work": False,
                "independent_human_specialist_or_legal_proxy_claimed": False,
            },
            "workers": receipts, "failed_workers": failures,
            "independent_stage_execution": True,
            "worker_attempts_this_cycle": len(receipts),
            "worker_successes_this_cycle": sum(int(r["passed"]) for r in receipts),
            "consecutive_zero_progress_cycles": (
                0 if any(gains.values()) else prior_no_progress + 1
            ),
            "all_stages_are_eligible_for_next_cycle": True,
            "no_global_shutdown_on_single_worker_failure": True,
            "prior_verified_receipt_counts": before,
            "verified_receipt_counts": after,
            "new_private_receipts": gains,
            "next_action": (
                "repair_failed_worker_and_retry" if failures else
                "retry_missing_evidence_and_continue_all_stage_workers"
            ),
            "independent_specialist_review_auto_certified": False,
            "commercial_quality1000_certified": False,
            "public_distribution_authorized": False,
            "websites_modified": False,
        }
        atomic_json(area / "delegated-internal-autonomy-status.json", result)
        return result


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--factory-private", required=True)
    p.add_argument("--operations", required=True)
    p.add_argument("--python", required=True)
    p.add_argument("--batch", type=int, default=200)
    p.add_argument("--worker-timeout", type=int, default=150)
    args = p.parse_args(argv)
    result = execute(
        args.factory_private, args.operations, args.python,
        batch=args.batch, timeout=args.worker_timeout
    )
    print("FACTORY_DELEGATED_AUTONOMY=" + json.dumps(
        result, ensure_ascii=False, sort_keys=True
    ))
    return int(result["status"] == "degraded")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("FACTORY_DELEGATED_AUTONOMY_ERROR=" +
              type(exc).__name__ + ":" + str(exc)[:200], file=sys.stderr)
        sys.exit(1)
