#!/usr/bin/env python3
"""Evidence-gated central worker for mojtaba.bot.ai.

The worker consumes an explicit JSON queue. It executes only the read-only
cPanel operations already approved in cpanel_direct_command.sh; all other
action kinds are recorded as blocked until a dedicated adapter and owner
approval gate exist. It never treats an empty queue as completed work.
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

ALLOWED_CPANEL = {"relay_preflight","cpanel_preflight","django_check","django_migrations"}
DELIVERABLE_KINDS = {"deliverable_created", "source_change", "verified_order", "verified_publication"}

def now():
    return datetime.now(timezone.utc).isoformat()

def record_action(args, item, status, evidence):
    cmd = [
        sys.executable, "deploy/mojtaba_bot_cycle_coordinator.py",
        "--state", args.state, "record",
        "--cycle", args.cycle,
        "--action-id", item["action_id"],
        "--item", item["item"],
        "--kind", item.get("kind", "unknown"),
        "--before", item.get("before", "unrecorded"),
        "--change", item.get("change", "worker execution"),
        "--after", item.get("after", "unverified"),
        "--status", status,
    ]
    for ref in evidence:
        cmd.extend(["--evidence", ref])
    subprocess.run(cmd, check=True, text=True, capture_output=True)


def run_repo_readonly(item):
    operation = item.get("operation")
    raw_path = item.get("path", "")
    if not isinstance(raw_path, str) or not raw_path or Path(raw_path).is_absolute():
        return False, ["invalid:repo_relative_path"], "repository-relative path is required"
    root = Path.cwd().resolve()
    path = (root / raw_path).resolve()
    if not path.is_relative_to(root):
        return False, ["invalid:path_outside_repo"], "path escapes repository checkout"
    if not path.is_file():
        return False, [f"missing:{path}"], "repository file is missing"
    if operation == "file_exists":
        return True, [f"file:{path}", f"bytes:{path.stat().st_size}"], "file exists"
    if operation == "sha256":
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return True, [f"file:{path}", f"sha256:{digest}"], "sha256 recorded"
    if operation == "json_validate":
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return False, [f"file:{raw_path}", "json:invalid"], "JSON failed validation"
        return True, [f"file:{raw_path}", "json:valid"], "JSON parsed successfully"
    return False, [f"unsupported:{operation}"], "repo operation not allowlisted"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cycle", required=True, choices=list("ABCDE"))
    p.add_argument("--queue", required=True)
    p.add_argument("--state", default="runtime/central_cycle_state.json")
    p.add_argument("--max-actions", type=int, default=50)
    args=p.parse_args()
    queue=json.loads(Path(args.queue).read_text(encoding="utf-8"))
    if not isinstance(queue, list):
        raise SystemExit("queue must be a JSON list")
    if len(queue) > args.max_actions:
        raise SystemExit("queue exceeds one-cycle limit")
    if not queue:
        raise SystemExit("EMPTY_QUEUE: no real action was executed")
    if not all(isinstance(x, dict) for x in queue):
        raise SystemExit("INVALID_QUEUE: every action must be an object")
    action_ids = [x.get("action_id") for x in queue]
    if len(action_ids) != len(set(action_ids)):
        raise SystemExit("DUPLICATE_QUEUE_ID: each action ID must be unique")
    results=[]
    for item in queue:
        aid=item.get("action_id")
        kind=item.get("kind")
        if not aid or not item.get("item"):
            results.append({"action_id":aid or "missing","status":"failed","reason":"missing identity"})
            continue
        if kind == "cpanel_readonly":
            operation=item.get("operation")
            if operation not in ALLOWED_CPANEL:
                results.append({"action_id":aid,"status":"blocked","reason":"operation not allowlisted"})
                continue
            proc=subprocess.run(["bash","deploy/cpanel_direct_command.sh",operation],
                                text=True,capture_output=True,timeout=120)
            evidence=item.get("evidence",[])
            evidence=evidence+[f"exit_code:{proc.returncode}"]
            status = "observed" if proc.returncode == 0 else "failed"
            record_action(args, item, status, evidence)
            results.append({"action_id":aid,"status":status,
                            "operation":operation,"evidence":evidence,
                            "output_tail":(proc.stdout+proc.stderr)[-1200:]})
        elif kind == "repo_readonly":
            ok, evidence, message = run_repo_readonly(item)
            status = "observed" if ok else "failed"
            record_action(args, item, status, evidence)
            results.append({"action_id":aid,"status":status,"operation":item.get("operation"),
                            "evidence":evidence,"message":message})
        else:
            evidence = item.get("evidence", [])
            record_action(args, item, "blocked", evidence)
            results.append({"action_id":aid,"status":"blocked",
                            "reason":"no approved adapter for action kind","kind":kind})
    successful=sum(x["status"]=="success" for x in results)
    observed=sum(x["status"]=="observed" for x in results)
    # Legacy inspection-only successes are excluded from deliverable progress.
    # Across runs, one action_id can contribute at most once.
    cumulative_success=0
    state_path=Path(args.state)
    if state_path.is_file():
        try:
            state=json.loads(state_path.read_text(encoding="utf-8"))
            accepted_ids={
                action_id
                for run in state.get("runs", {}).values()
                if run.get("cycle")==args.cycle
                for action_id, action in run.get("actions", {}).items()
                if action.get("status")=="success"
                and action.get("kind") in DELIVERABLE_KINDS
                and bool(action.get("evidence"))
            }
            cumulative_success=len(accepted_ids)
        except (OSError, ValueError, TypeError, AttributeError):
            cumulative_success=0
    report={"engine":"mojtaba.bot.ai","cycle":args.cycle,"started_at":now(),
            "queued":len(queue),"processed":len(results),"successful":successful,
            "observed":observed,"cumulative_qualified_deliveries":cumulative_success,
            "cumulative_successful":cumulative_success,"target":50,
            "complete":cumulative_success>=50,"results":results}
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if cumulative_success < 50:
        return 2
    return 0

if __name__=="__main__":
    sys.exit(main())
