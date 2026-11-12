#!/usr/bin/env python3
"""C06: execute 1–50 already authored, distinct, authorized source jobs.

Makes actual Git changes in five batches of ten, records ONE immutable
manifest and passes it through the central ledger. It cannot write content
by itself: each job must supply original substantive content. It never
publishes to a site, sends mail, trades, pays, or pushes to a remote.

Default mode is validate-only. --commit-local requires a reviewed private
checkout or explicitly approved public-branch content and a clean Git tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

from mojtaba_bot_cycle_coordinator import verified_git_artifact

ROOT = Path(__file__).resolve().parents[1]
LANES = "ABCDE"
TARGET = 50
BATCH_SIZE = 10
ALLOWED = {
    "A": ("deliverables/books/", "deliverables/mojplaywin/"),
    "B": ("deliverables/research/",),
    "C": ("games/",),
    "D": ("product_recipes/", "deliverables/products/"),
    "E": ("deploy/mojtaba_bot_", "deliverables/command/"),
}
REJECTED_PATH_PARTS = {".git", "..", ".", "__pycache__", ".github", "secrets"}
ALLOWED_SUFFIXES = {".md", ".py", ".js", ".json", ".txt"}
SECRETS_PATTERN = re.compile(
    r"(?i)(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"\b(?:sk-proj|ghp|github_pat)_[A-Za-z0-9_-]{15,}\b)"
)


class ExecutionError(ValueError):
    pass


def git(*args: str) -> bytes:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, timeout=30
    )
    if result.returncode:
        raise ExecutionError(
            "git command refused: " + " ".join(args[:2]) +
            " " + result.stderr.decode("utf-8", errors="replace")[-200:]
        )
    return result.stdout


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def exact_repo_path(relative: str, *, must_exist: bool) -> Path:
    if (not isinstance(relative, str) or not relative
            or len(relative) > 240 or "\\" in relative
            or relative.startswith("/") or "//" in relative):
        raise ExecutionError("invalid repository path")
    p = Path(relative)
    if any(part in REJECTED_PATH_PARTS or part.startswith(".") for part in p.parts):
        raise ExecutionError("hidden, traversal, or internal paths forbidden")
    destination = ROOT / p
    if not destination.resolve().is_relative_to(ROOT.resolve()):
        raise ExecutionError("path escapes authorized checkout")
    if destination.is_symlink():
        raise ExecutionError("symlink target refused")
    if must_exist and not destination.is_file():
        raise ExecutionError("required source file absent")
    if not must_exist and destination.exists() and not destination.is_file():
        raise ExecutionError("target must be an ordinary file")
    return destination


def check_markdown(content: str) -> None:
    if len(content) < 500 or not content.lstrip().startswith("# "):
        raise ExecutionError("content too short or missing document title")
    if sum(line.startswith("## ") for line in content.splitlines()) < 2:
        raise ExecutionError("markdown requires at least two substantive sections")


def validate_jobs(cycle: str, jobs: object) -> list[dict]:
    if not isinstance(jobs, list) or not 1 <= len(jobs) <= TARGET:
        raise ExecutionError("1–50 distinct authored jobs required")
    actions = []
    seen_ids, seen_paths, seen_contents = set(), set(), set()
    fields = {"action_id", "path", "content", "kind", "before", "change",
              "after", "expected_sha256", "source_paths"}
    for index, item in enumerate(jobs):
        if not isinstance(item, dict) or set(item) != fields:
            raise ExecutionError("invalid job fields at " + str(index))
        aid = item["action_id"]
        if not isinstance(aid, str) or not re.fullmatch(
                cycle + r"-[A-Za-z0-9_.-]{1,125}", aid):
            raise ExecutionError("invalid lane-specific action ID")
        relative = item["path"]
        if not isinstance(relative, str) or not relative.startswith(ALLOWED[cycle]):
            raise ExecutionError("target outside authorized lane")
        dest = exact_repo_path(relative, must_exist=False)
        if dest.suffix not in ALLOWED_SUFFIXES:
            raise ExecutionError("unsupported file format")
        if relative in seen_paths or aid in seen_ids:
            raise ExecutionError("duplicate action ID or target")
        seen_paths.add(relative)
        seen_ids.add(aid)
        content = item["content"]
        if not isinstance(content, str) or not 200 <= len(content) <= 250_000:
            raise ExecutionError("authored content must be substantive and bounded")
        if "\x00" in content or SECRETS_PATTERN.search(content):
            raise ExecutionError("content contains null or possible secrets")
        if dest.suffix == ".md":
            check_markdown(content)
        if dest.suffix == ".json":
            try:
                json.loads(content)
            except ValueError as exc:
                raise ExecutionError("invalid JSON artifact") from exc
        # Identical bytes under different names never fill the quota.
        produced = content.encode("utf-8")
        fingerprint = sha(produced)
        if fingerprint in seen_contents:
            raise ExecutionError("same-content clone refused")
        seen_contents.add(fingerprint)
        existing = dest.read_bytes() if dest.is_file() else None
        expected = item["expected_sha256"]
        if existing is None:
            if expected is not None:
                raise ExecutionError("new artifact must have null baseline SHA")
        elif (not isinstance(expected, str)
              or sha(existing) != expected.lower()
              or existing == produced):
            raise ExecutionError("stale baseline or no meaningful change")
        for field in ("before", "change", "after"):
            value = item[field]
            if not isinstance(value, str) or not 12 <= len(value.strip()) <= 2000:
                raise ExecutionError("missing substantive change explanation")
        if item["before"].strip() == item["after"].strip():
            raise ExecutionError("before/after identical")
        sources = item["source_paths"]
        if not isinstance(sources, list) or not sources or len(sources) > 12:
            raise ExecutionError("existing provenance/source files required")
        for source in sources:
            source_path = exact_repo_path(source, must_exist=True)
            if source_path.is_symlink():
                raise ExecutionError("symlink source refused")
            if not git("ls-files", "--error-unmatch", "--", source):
                raise ExecutionError("source must be tracked")
        actions.append({
            **item, "digest": fingerprint, "bytes": produced,
        })
    return actions


def verify_local_context(expected_branch: str) -> None:
    actual_branch = git("symbolic-ref", "--short", "HEAD").decode().strip()
    if actual_branch != expected_branch or not actual_branch.startswith("work/"):
        raise ExecutionError("write requires exact authorized work/ branch")
    if git("status", "--porcelain"):
        raise ExecutionError("dirty checkout; refuse to modify other work")
    # This executor never changes the default branch or an upstream remote.
    if git("rev-parse", "--is-inside-work-tree").strip() != b"true":
        raise ExecutionError("not a Git checkout")


def static_quality_checks(batch: list[dict]) -> None:
    # Syntax is necessary, not sufficient, for genuine professional quality.
    # No arbitrary shell commands from job JSON are executed.
    for item in batch:
        path = ROOT / item["path"]
        if path.suffix == ".py":
            try:
                compile(path.read_bytes(), str(path), "exec")
            except SyntaxError as exc:
                raise ExecutionError("Python syntax invalid: " + item["path"]) from exc
        elif path.suffix == ".js":
            try:
                result = subprocess.run(
                    ["node", "--check", str(path)],
                    cwd=ROOT, capture_output=True, timeout=15
                )
            except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                raise ExecutionError("node syntax checker unavailable") from exc
            if result.returncode:
                raise ExecutionError("JavaScript syntax invalid: " + item["path"])
        elif path.suffix == ".json":
            json.loads(path.read_text(encoding="utf-8"))
        elif path.suffix == ".md":
            check_markdown(path.read_text(encoding="utf-8"))


def commit_batch(cycle: str, run_id: str, number: int,
                 batch: list[dict]) -> tuple[str, list[dict]]:
    for item in batch:
        output = ROOT / item["path"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(item["bytes"])
    static_quality_checks(batch)
    paths = [item["path"] for item in batch]
    git("add", "--", *paths)
    git("commit", "-m", "C06 " + cycle + " real deliverables " +
        run_id + " batch " + str(number) + "/5")
    commit = git("rev-parse", "HEAD").decode().strip()
    receipts = []
    for item in batch:
        evidence = ["commit:" + commit, "path:" + item["path"],
                    "sha256:" + item["digest"]]
        if not verified_git_artifact(item["kind"], evidence,
                                    max_age_seconds=75 * 60):
            raise ExecutionError("Git receipt failed after actual commit")
        receipts.append({
            "action_id": item["action_id"],
            "item": item["path"],
            "kind": item["kind"],
            "before": item["before"], "change": item["change"],
            "after": item["after"],
            "evidence": evidence,
        })
    return commit, receipts


def execute(cycle: str, run_id: str, candidates: list[dict],
            *, commit_local: bool, expected_branch: str,
            state_path: str) -> dict:
    verify_local_context(expected_branch)
    actions = validate_jobs(cycle, candidates)
    if not re.fullmatch(cycle + r"-[A-Za-z0-9_.-]{1,110}", run_id):
        raise ExecutionError("invalid new run ID")
    manifest_path = ("runtime/cycle_receipts/" + cycle +
                     "/" + run_id + ".json")
    if (ROOT / manifest_path).exists():
        raise ExecutionError("run manifest already exists; replay refused")
    if not commit_local:
        return {"cycle": cycle, "run_id": run_id, "mode": "validate_only",
                "ready": len(actions), "target": TARGET, "committed": 0,
                "complete": False}
    all_receipts, commits = [], []
    for start in range(0, len(actions), BATCH_SIZE):
        chunk = actions[start:start + BATCH_SIZE]
        commit, receipts = commit_batch(
            cycle, run_id, 1 + start // BATCH_SIZE, chunk
        )
        commits.append(commit)
        all_receipts.extend(receipts)
    manifest = {
        "schema_version": "1.0", "engine": "mojtaba.bot.ai",
        "cycle": cycle, "run_id": run_id, "actions": all_receipts,
    }
    dest = ROOT / manifest_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    git("add", "--", manifest_path)
    git("commit", "-m", "C06 " + cycle + " immutable receipts for " + run_id)
    # Validate every recorded action against the central evidence ledger.
    receipt_bridge = ROOT / "deploy" / "mojtaba_bot_cycle_receipt_bridge.py"
    proc = subprocess.run(
        [sys.executable, str(receipt_bridge), "--cycle", cycle,
         "--manifest", manifest_path, "--state", state_path],
        cwd=ROOT, capture_output=True, text=True, timeout=180
    )
    try:
        result = json.loads(proc.stdout)
    except ValueError as exc:
        raise ExecutionError("bridge did not return a JSON audit") from exc
    accepted = result.get("successful", 0)
    return {
        "cycle": cycle, "run_id": run_id, "mode": "local_committed",
        "processed": len(actions), "artifact_commits": commits,
        "receipt_path": manifest_path,
        "accepted": accepted,
        "blocked": len(actions) - accepted,
        "target": TARGET, "complete": accepted == TARGET,
        "receipt_bridge_exit": proc.returncode,
        "note": "Local branch only. No remote push, live deploy, sale or publication.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycle", required=True, choices=list(LANES))
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-branch", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--commit-local", action="store_true",
                        help="write only to locally checked-out authorized work/ branch")
    args = parser.parse_args()
    try:
        payload = json.loads(Path(args.jobs).read_text(encoding="utf-8"))
        result = execute(
            args.cycle, args.run_id, payload, commit_local=args.commit_local,
            expected_branch=args.expected_branch, state_path=args.state,
        )
    except (ExecutionError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result = {"cycle": args.cycle, "complete": False,
                  "accepted": 0, "error": str(exc)}
        print(json.dumps(result, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("complete") else 2


if __name__ == "__main__":
    raise SystemExit(main())
