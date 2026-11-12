#!/usr/bin/env python3
"""mojtaba.bot.ai central five-cycle execution ledger.

This tool is a durable, evidence-gated coordinator. It never counts a report,
read-only inspection, duplicate action, or unverified claim as a successful
action. External side effects remain the responsibility of the authorised
worker and owner approval gates.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

CYCLES = ("A", "B", "C", "D", "E")
TARGET = 50
SUCCESS = "success"
BLOCKED = "blocked"
FAILED = "failed"
OBSERVED = "observed"
# Only value-creating, independently accepted work may count toward the target.
DELIVERABLE_KINDS = {"deliverable_created", "source_change", "verified_order", "verified_publication"}
VALID = {SUCCESS, BLOCKED, FAILED, OBSERVED}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_state() -> dict:
    return {"schema": 1, "engine": "mojtaba.bot.ai", "runs": {}}


@contextmanager
def locked_state(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(path.suffix + ".lock")
    lock.touch(mode=0o600, exist_ok=True)
    import fcntl
    with lock.open("r+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        if path.exists():
            state = json.loads(path.read_text(encoding="utf-8"))
        else:
            state = default_state()
        yield state
        fd, temp_name = tempfile.mkstemp(prefix=".cycle-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                json.dump(state, out, ensure_ascii=False, indent=2, sort_keys=True)
                out.write("\n")
                out.flush()
                os.fsync(out.fileno())
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        fcntl.flock(handle, fcntl.LOCK_UN)


def run_id(cycle: str) -> str:
    return f"{cycle}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def ensure_run(state: dict, cycle: str, requested: str | None) -> tuple[str, dict]:
    if cycle not in CYCLES:
        raise SystemExit(f"invalid cycle: {cycle}; use A, B, C, D or E")
    rid = requested or run_id(cycle)
    runs = state["runs"]
    if rid not in runs:
        runs[rid] = {
            "cycle": cycle,
            "target": TARGET,
            "started_at": now(),
            "closed_at": None,
            "actions": {},
        }
    return rid, runs[rid]


def evidence_ok(evidence: list[str]) -> bool:
    return bool(evidence) and all(x.strip() for x in evidence)


def cmd_start(args: argparse.Namespace) -> None:
    with locked_state(Path(args.state)) as state:
        rid, run = ensure_run(state, args.cycle, args.run_id)
        print(json.dumps({"run_id": rid, "cycle": run["cycle"], "target": TARGET}, ensure_ascii=False))


def cmd_record(args: argparse.Namespace) -> None:
    evidence = [x for x in args.evidence if x.strip()]
    if args.status not in VALID:
        raise SystemExit(f"invalid status: {args.status}")
    if args.status == SUCCESS:
        if args.kind not in DELIVERABLE_KINDS:
            raise SystemExit("inspection/unsupported kind cannot be successful delivery")
        if not evidence_ok(evidence):
            raise SystemExit("success requires at least one non-empty evidence reference")
    with locked_state(Path(args.state)) as state:
        rid, run = ensure_run(state, args.cycle, args.run_id)
        actions = run["actions"]
        if any(args.action_id in past.get("actions", {}) for past in state["runs"].values()):
            raise SystemExit(f"duplicate action_id refused globally: {args.action_id}")
        actions[args.action_id] = {
            "item": args.item,
            "kind": args.kind,
            "status": args.status,
            "before": args.before,
            "change": args.change,
            "after": args.after,
            "evidence": evidence,
            "recorded_at": now(),
        }
        print(json.dumps({"run_id": rid, "action_id": args.action_id, "status": args.status}, ensure_ascii=False))


def cmd_summary(args: argparse.Namespace) -> None:
    path = Path(args.state)
    with locked_state(path) as state:
        candidates = []
        for rid, run in state["runs"].items():
            if args.run_id and rid == args.run_id:
                candidates = [(rid, run)]
            elif not args.run_id and run["cycle"] == args.cycle:
                candidates.append((rid, run))
        if not candidates:
            raise SystemExit("run not found")
        rid, run = sorted(candidates, key=lambda pair: pair[1]["started_at"])[-1]
        actions = list(run["actions"].values())
        counts = {status: sum(a["status"] == status for a in actions) for status in VALID}
        result = {
            "run_id": rid,
            "cycle": run["cycle"],
            "target": TARGET,
            "recorded": len(actions),
            "success": counts[SUCCESS],
            "blocked": counts[BLOCKED],
            "failed": counts[FAILED],
            "remaining": max(TARGET - counts[SUCCESS], 0),
            "complete": counts[SUCCESS] == TARGET,
            "closed_at": run["closed_at"],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--state", default="runtime/central_cycle_state.json")
    sub = p.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("--cycle", required=True)
    start.add_argument("--run-id")
    start.set_defaults(func=cmd_start)

    rec = sub.add_parser("record")
    rec.add_argument("--cycle", required=True)
    rec.add_argument("--run-id")
    rec.add_argument("--action-id", required=True)
    rec.add_argument("--item", required=True)
    rec.add_argument("--kind", required=True)
    rec.add_argument("--before", required=True)
    rec.add_argument("--change", required=True)
    rec.add_argument("--after", required=True)
    rec.add_argument("--status", choices=sorted(VALID), required=True)
    rec.add_argument("--evidence", action="append", default=[])
    rec.set_defaults(func=cmd_record)

    summ = sub.add_parser("summary")
    summ.add_argument("--cycle", required=True)
    summ.add_argument("--run-id")
    summ.set_defaults(func=cmd_summary)
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
