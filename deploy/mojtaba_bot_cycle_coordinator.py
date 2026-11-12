#!/usr/bin/env python3
"""mojtaba.bot.ai central five-cycle execution ledger.

This tool is a durable, evidence-gated coordinator. It never counts a report,
read-only inspection, duplicate action, or unverified claim as a successful
action. External side effects remain the responsibility of the authorised
worker and owner approval gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
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
    elif runs[rid]["cycle"] != cycle:
        raise SystemExit("run_id is already owned by a different cycle")
    return rid, runs[rid]


def evidence_ok(evidence: list[str]) -> bool:
    return bool(evidence) and all(x.strip() for x in evidence)

def artifact_identity(evidence: list[str]) -> tuple[str, str] | None:
    """Reject replay of identical path and content under a new commit."""
    try:
        fields = {}
        for item in evidence:
            key, value = item.split(":", 1)
            if key in fields:
                return None
            fields[key] = value
        if set(fields) != {"commit", "path", "sha256"}:
            return None
        path, digest = fields["path"], fields["sha256"]
        if not path or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            return None
        return (path, digest.lower())
    except (ValueError, TypeError, AttributeError):
        return None


def verified_git_artifact(kind: str, evidence: list[str], *, max_age_seconds: int | None = None) -> bool:
    """A delivered source/file must exist in this checked-out Git commit.

    This is not a journal-publication or payment adapter. Those require their
    own independently validated proofs, not arbitrary evidence strings.
    """
    if kind not in {"source_change", "deliverable_created"}:
        return False
    try:
        fields = {}
        for item in evidence:
            name, value = item.split(":", 1)
            if name in fields:
                return False
            fields[name] = value
        commit = fields.get("commit", "")
        rel = fields.get("path", "")
        digest = fields.get("sha256", "")
        if (set(fields) != {"commit", "path", "sha256"}
                or not re.fullmatch(r"[0-9a-fA-F]{40}", commit)
                or not re.fullmatch(r"[0-9a-fA-F]{64}", digest)
                or not rel):
            return False
        relative = Path(rel)
        if (relative.is_absolute() or rel != relative.as_posix()
                or any(part in ("..", ".", ".git") for part in relative.parts)
                or len(rel) > 512):
            return False
        checkout = Path.cwd().resolve()
        # Check that the named commit is in this locally checked-out history.
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
            cwd=checkout, capture_output=True, timeout=15,
        )
        if ancestor.returncode != 0:
            return False
        if max_age_seconds is not None:
            # Creation of old commits cannot be retroactively advertised as
            # fifty NEW actions in this hourly execution. Revalidation of
            # previously accepted receipts uses no age limit.
            authored = subprocess.run(
                ["git", "show", "-s", "--format=%ct", commit],
                cwd=checkout, capture_output=True, text=True, timeout=15,
            )
            if authored.returncode != 0:
                return False
            age = datetime.now(timezone.utc).timestamp() - int(authored.stdout.strip())
            if age < -300 or age > max_age_seconds:
                return False
        changed = subprocess.run(
            ["git", "show", "--format=", "--name-only", "--no-renames",
             commit, "--", relative.as_posix()],
            cwd=checkout, capture_output=True, text=True, timeout=15,
        )
        paths = set(changed.stdout.splitlines())
        if changed.returncode != 0 or relative.as_posix() not in paths:
            return False
        # Verify the bytes of the named immutable Git commit, NOT the HEAD
        # worktree. A later authorized revision cannot erase past delivery
        # evidence, and uncommitted local modifications cannot forge proof.
        git_ref = f"{commit}:{relative.as_posix()}"
        size = subprocess.run(
            ["git", "cat-file", "-s", git_ref],
            cwd=checkout, capture_output=True, text=True, timeout=15,
        )
        if size.returncode != 0 or int(size.stdout.strip()) > 64 * 1024 * 1024:
            return False
        blob = subprocess.run(
            ["git", "show", git_ref],
            cwd=checkout, capture_output=True, timeout=20,
        )
        return blob.returncode == 0 and hashlib.sha256(blob.stdout).hexdigest() == digest.lower()
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        return False


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
        if not verified_git_artifact(args.kind, evidence, max_age_seconds=75 * 60):
            raise SystemExit("success requires verified Git commit + path + sha256 proof")
    with locked_state(Path(args.state)) as state:
        rid, run = ensure_run(state, args.cycle, args.run_id)
        actions = run["actions"]
        # A blocked/failed/observed action may be retried next cycle. Only a
        # previously qualified SUCCESS permanently consumes that identity.
        if args.action_id in actions:
            raise SystemExit(f"duplicate action_id in same run: {args.action_id}")
        if any(
            past.get("actions", {}).get(args.action_id, {}).get("status") == SUCCESS
            for past in state["runs"].values()
        ):
            raise SystemExit(f"previously completed action_id refused: {args.action_id}")
        if args.status == SUCCESS:
            current_proof = artifact_identity(evidence)
            if current_proof is None:
                raise SystemExit("invalid artifact identity")
            if any(
                artifact_identity(past_action.get("evidence", [])) == current_proof
                for prior_run in state["runs"].values()
                for past_action in prior_run.get("actions", {}).values()
                if past_action.get("status") == SUCCESS
            ):
                raise SystemExit("duplicate successful artifact proof refused globally")
            if args.before.strip() == args.after.strip():
                raise SystemExit("success requires independently changed before/after")
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
        # Reconcile ALL lanes in chronological order: legacy observation-only
        # success, duplicate IDs, fake receipts and duplicate artifact proofs
        # never make the cycle complete. Immutable Git evidence survives later
        # edits, but cannot be double-counted globally.
        accepted_by_run = {}
        seen_ids = set()
        seen_proofs = set()
        proof_cache = {}
        for prior_id, prior in sorted(
                state["runs"].items(),
                key=lambda row: (row[1].get("started_at", ""), row[0])):
            qualified = 0
            for action_id, action in prior.get("actions", {}).items():
                if (action.get("status") != SUCCESS
                        or action.get("kind") not in {
                            "source_change", "deliverable_created"
                        }):
                    continue
                evidence = action.get("evidence")
                if not isinstance(evidence, list):
                    continue
                key = artifact_identity(evidence)
                if key is None or action_id in seen_ids or key in seen_proofs:
                    continue
                if key not in proof_cache:
                    proof_cache[key] = verified_git_artifact(
                        action.get("kind"), evidence
                    )
                if proof_cache[key]:
                    qualified += 1
                    seen_ids.add(action_id)
                    seen_proofs.add(key)
            accepted_by_run[prior_id] = qualified
        verified_success = accepted_by_run.get(rid, 0)
        result = {
            "run_id": rid,
            "cycle": run["cycle"],
            "target": TARGET,
            "recorded": len(actions),
            "success": verified_success,
            "unverified_legacy_success": counts[SUCCESS] - verified_success,
            "blocked": counts[BLOCKED],
            "observed": counts[OBSERVED],
            "failed": counts[FAILED],
            "remaining": max(TARGET - verified_success, 0),
            "complete": verified_success >= TARGET,
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
