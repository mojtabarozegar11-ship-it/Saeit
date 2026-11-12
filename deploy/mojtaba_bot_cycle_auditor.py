#!/usr/bin/env python3
"""Read-only cross-lane audit of committed hourly action receipts.

All five lanes are reconciled against immutable Git content. Reports, queue
entries, fake payments, file-count padding and replays are excluded. The audit
does not trigger delivery, deploy, spending or production side effects.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy import mojtaba_bot_cycle_receipt_bridge as bridge
from deploy.mojtaba_bot_cycle_coordinator import verified_git_artifact

LANES = "ABCDE"
WINDOW_SECONDS = 75 * 60


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30
    )
    if result.returncode:
        raise RuntimeError("git_history_not_available")
    return result.stdout.strip()


def committed_manifest_paths() -> list[str]:
    return sorted(
        p for p in git("ls-files", "--", "runtime/cycle_receipts").splitlines()
        if re.fullmatch(
            r"runtime/cycle_receipts/[A-E]/[A-Za-z0-9_.-]+\.json", p
        )
    )


def audit() -> dict:
    candidate_manifests = committed_manifest_paths()
    manifests = []
    errors = []
    for relative in candidate_manifests:
        cycle = relative.split("/")[2]
        try:
            manifest = bridge.load_manifest(cycle, relative)
            manifest_commit_time = int(
                git("log", "-1", "--format=%ct", "HEAD", "--", relative)
            )
            manifests.append((manifest_commit_time, relative, manifest))
        except (bridge.ManifestError, ValueError, RuntimeError) as exc:
            errors.append({"manifest": relative, "error": str(exc)})
    manifests.sort(key=lambda x: (x[0], x[1]))
    seen_actions = set()
    seen_artifacts = set()
    lanes = {
        lane: {"target": 50, "latest_run_id": None, "latest_run_success": 0,
               "latest_run_submitted": 0, "latest_run_rejected": 0,
               "historical_verified_actions": 0, "runs": 0}
        for lane in LANES
    }
    for manifest_time, relative, manifest in manifests:
        cycle = manifest["cycle"]
        group = lanes[cycle]
        accepted = 0
        rejected = 0
        for action in manifest["actions"]:
            evidence = action["evidence"]
            fields = dict(item.split(":", 1) for item in evidence)
            artifact_key = (fields["path"], fields["sha256"].lower())
            identity = action["action_id"]
            if identity in seen_actions or artifact_key in seen_artifacts:
                rejected += 1
                continue
            try:
                commit_time = int(git("show", "-s", "--format=%ct", fields["commit"]))
            except (ValueError, RuntimeError):
                rejected += 1
                continue
            # New action must be created before, and close in time to, the
            # committed hourly receipt. Old sources cannot be backfilled.
            if not -300 <= manifest_time - commit_time <= WINDOW_SECONDS:
                rejected += 1
                continue
            if not verified_git_artifact(action["kind"], evidence):
                rejected += 1
                continue
            seen_actions.add(identity)
            seen_artifacts.add(artifact_key)
            accepted += 1
        group["runs"] += 1
        group["historical_verified_actions"] += accepted
        group["latest_run_id"] = manifest["run_id"]
        group["latest_run_success"] = accepted
        group["latest_run_submitted"] = len(manifest["actions"])
        group["latest_run_rejected"] = rejected
        group["last_manifest"] = relative
    for group in lanes.values():
        group["latest_run_missing"] = 50 - group["latest_run_success"]
        group["latest_run_percent"] = 100 * group["latest_run_success"] / 50
        group["complete"] = group["latest_run_success"] >= 50
    return {
        "engine": "mojtaba.bot.ai",
        "read_only": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_count": len(candidate_manifests),
        "valid_manifest_count": len(manifests),
        "manifest_errors": errors,
        "lanes": lanes,
        "complete_lanes": sum(x["complete"] for x in lanes.values()),
        "latest_round_verified_actions": sum(
            x["latest_run_success"] for x in lanes.values()
        ),
        "latest_round_target": 250,
        "latest_round_complete": all(x["complete"] for x in lanes.values()),
        "business_revenue": "not_verified_by_this_auditor",
        "live_publication": "not_verified_by_this_auditor",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--strict", action="store_true",
                   help="return nonzero for invalid manifests or incomplete 50/50")
    p.add_argument("--out", help="optional local JSON result path")
    args = p.parse_args()
    report = audit()
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    print(encoded)
    if args.out:
        dest = Path(args.out)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(encoded + "\n", encoding="utf-8")
    return 2 if args.strict and (
        report["manifest_errors"] or not report["latest_round_complete"]
    ) else 0


if __name__ == "__main__":
    raise SystemExit(main())
