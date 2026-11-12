#!/usr/bin/env python3
"""Strict handoff from the five hourly tasks to mojtaba.bot.ai's evidence ledger.

Input is an existing, tracked, clean Git receipt manifest; this script does
NOT generate work. It refuses simulated/queued-only actions and never deploys,
sends mail, trades, charges money or exposes credentials.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

LANES = frozenset("ABCDE")
KINDS = {"source_change", "deliverable_created"}
ROOT = Path(__file__).resolve().parent.parent
BLOCKED_ARTIFACT_PREFIXES = (
    "runtime/", ".github/", "tests/", "quality/", "reports/",
    "docs/audit/", "deploy/mojtaba_bot_cycle_receipt_bridge.py",
)


class ManifestError(ValueError):
    pass


def git_bytes(*args: str) -> bytes:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, check=False, timeout=30
    )
    if result.returncode:
        raise ManifestError("receipt_manifest_not_committed_or_git_unavailable")
    return result.stdout


def load_manifest(cycle: str, relative: str) -> dict:
    allowed = re.fullmatch(
        rf"runtime/cycle_receipts/{cycle}/[A-Za-z0-9_.-]+\.json", relative
    )
    if not allowed or ".." in relative or len(relative) > 220:
        raise ManifestError("receipt_manifest_path_not_allowed")
    path = ROOT / relative
    if not path.is_file() or path.is_symlink():
        raise ManifestError("receipt_manifest_missing_or_symlink")
    raw = path.read_bytes()
    # Git HEAD must contain exactly the bytes read, blocking uncommitted edits.
    committed = git_bytes("show", f"HEAD:{relative}")
    if raw != committed:
        raise ManifestError("receipt_manifest_differs_from_commit")
    try:
        manifest = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ManifestError("receipt_manifest_invalid_json") from exc
    if not isinstance(manifest, dict):
        raise ManifestError("receipt_manifest_must_be_object")
    if set(manifest) != {"schema_version", "engine", "cycle", "run_id", "actions"}:
        raise ManifestError("receipt_manifest_unknown_or_missing_fields")
    if manifest["schema_version"] != "1.0" or manifest["engine"] != "mojtaba.bot.ai":
        raise ManifestError("receipt_manifest_version_or_engine_mismatch")
    if manifest["cycle"] != cycle:
        raise ManifestError("receipt_manifest_cycle_mismatch")
    rid = manifest["run_id"]
    if not isinstance(rid, str) or not re.fullmatch(
        rf"{cycle}-[a-zA-Z0-9_.-]{{1,110}}", rid
    ):
        raise ManifestError("receipt_manifest_invalid_run_id")
    actions = manifest["actions"]
    if not isinstance(actions, list) or not 1 <= len(actions) <= 50:
        raise ManifestError("receipt_manifest_requires_one_to_fifty_actions")
    used_ids = set()
    used_paths = set()
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            raise ManifestError(f"action_{index}_must_be_object")
        fields = {"action_id", "item", "kind", "before", "change", "after", "evidence"}
        if set(action) != fields:
            raise ManifestError(f"action_{index}_invalid_fields")
        aid = action["action_id"]
        if not isinstance(aid, str) or not re.fullmatch(
            rf"{cycle}-[a-zA-Z0-9_.-]{{1,125}}", aid
        ):
            raise ManifestError(f"action_{index}_invalid_id")
        if aid in used_ids:
            raise ManifestError("receipt_manifest_duplicate_action_id")
        used_ids.add(aid)
        if action["kind"] not in KINDS:
            raise ManifestError("receipt_manifest_non_delivery_kind")
        for field in ("item", "before", "change", "after"):
            v = action[field]
            if not isinstance(v, str) or not v.strip() or len(v) > 2048:
                raise ManifestError(f"action_{index}_invalid_{field}")
        if action["before"].strip() == action["after"].strip():
            raise ManifestError("receipt_manifest_unchanged_item")
        evidence = action["evidence"]
        if not isinstance(evidence, list) or len(evidence) != 3:
            raise ManifestError("receipt_manifest_invalid_evidence")
        evidence_dict = {}
        for proof in evidence:
            if not isinstance(proof, str) or ":" not in proof:
                raise ManifestError("receipt_manifest_invalid_evidence")
            key, value = proof.split(":", 1)
            if key in evidence_dict or not value:
                raise ManifestError("receipt_manifest_invalid_evidence")
            evidence_dict[key] = value
        if set(evidence_dict) != {"commit", "path", "sha256"}:
            raise ManifestError("receipt_manifest_non_git_proof")
        artifact = evidence_dict["path"]
        if (artifact.startswith(BLOCKED_ARTIFACT_PREFIXES)
                or artifact in used_paths):
            raise ManifestError("receipt_manifest_repeated_or_administrative_artifact")
        used_paths.add(artifact)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycle", required=True, choices=sorted(LANES))
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--state", default="runtime/central_cycle_state.json")
    args = parser.parse_args()
    try:
        manifest = load_manifest(args.cycle, args.manifest)
    except ManifestError as exc:
        print(json.dumps({"engine": "mojtaba.bot.ai", "cycle": args.cycle,
                          "complete": False, "error": str(exc)}))
        return 2
    with TemporaryDirectory(prefix="mojtaba-cycle-receipts-") as directory:
        queue_file = Path(directory) / "verified-evidence-candidates.json"
        queue_file.write_text(json.dumps(manifest["actions"]), encoding="utf-8")
        worker = ROOT / "deploy" / "mojtaba_bot_cycle_worker.py"
        result = subprocess.run(
            [sys.executable, str(worker), "--cycle", args.cycle,
             "--queue", str(queue_file), "--run-id", manifest["run_id"],
             "--state", args.state, "--max-actions", "50"],
            cwd=ROOT, capture_output=True, text=True,
        )
    try:
        report = json.loads(result.stdout)
    except ValueError:
        print(json.dumps({"engine": "mojtaba.bot.ai", "cycle": args.cycle,
                          "complete": False, "error": "worker_failed_without_json",
                          "stderr_tail": result.stderr[-500:]}))
        return 2
    report["receipt_manifest"] = args.manifest
    report["submitted_receipt_candidates"] = len(manifest["actions"])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # A 50/50 success can only be asserted by the central evidence worker.
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
