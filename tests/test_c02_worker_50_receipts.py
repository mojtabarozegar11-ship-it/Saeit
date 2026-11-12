"""Proof of coordinator/worker capacity, never claimed as commercial output.

This suite builds a disposable Git repository with 50 distinct synthetic files.
Passing proves accounting semantics, NOT that 50 real products were delivered.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def execute(*args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def isolated_git_workspace(tmp_path, total=50):
    root = tmp_path / "checkout"
    root.mkdir()
    deploy = root / "deploy"
    deploy.mkdir()
    for name in ("mojtaba_bot_cycle_worker.py", "mojtaba_bot_cycle_coordinator.py"):
        shutil.copyfile(ROOT / "deploy" / name, deploy / name)
    for argv in (
        ("git", "init"),
        ("git", "config", "user.email", "qa@example.invalid"),
        ("git", "config", "user.name", "C02 Test Only"),
    ):
        p = execute(*argv, cwd=root)
        assert p.returncode == 0, p.stderr
    queue = []
    for i in range(total):
        rel = f"deliverables/qa-only/item-{i:03d}.txt"
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"Distinct offline QA material {i:03d}\n", encoding="utf-8")
        queue.append({
            "action_id": f"E-QA-ONLY-{i:03d}",
            "kind": "deliverable_created", "item": rel,
            "before": "file absent", "change": f"create QA file {i:03d}",
            "after": f"committed QA file {i:03d}",
            "evidence": [],
        })
    assert execute("git", "add", "deliverables", cwd=root).returncode == 0
    done = execute("git", "commit", "-m", "50 synthetic files for ledger test only", cwd=root)
    assert done.returncode == 0, done.stderr
    commit = execute("git", "rev-parse", "HEAD", cwd=root).stdout.strip()
    for item in queue:
        target = root / item["item"]
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        item["evidence"] = [
            "commit:" + commit, "path:" + item["item"], "sha256:" + digest
        ]
    file = root / "queue.json"
    file.write_text(json.dumps(queue), encoding="utf-8")
    return root, file, queue


def call_worker(root, queue, run):
    return execute(sys.executable, "deploy/mojtaba_bot_cycle_worker.py",
                   "--cycle", "E", "--run-id", run,
                   "--queue", str(queue), "--state", "state.json", cwd=root)


def test_one_run_gets_exactly_fifty_real_proven_files(tmp_path):
    root, queue, _ = isolated_git_workspace(tmp_path)
    result = call_worker(root, queue, "E-C02-QA-ONE")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["run_id"] == "E-C02-QA-ONE"
    assert data["successful"] == 50
    assert data["complete"] is True
    assert data["cumulative_qualified_deliveries"] == 50
    assert all(row.get("recorded") for row in data["results"])
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    assert list(state["runs"]) == ["E-C02-QA-ONE"]
    assert len(state["runs"]["E-C02-QA-ONE"]["actions"]) == 50


def test_same_fifty_artifacts_cannot_be_recounted_in_later_hour(tmp_path):
    root, queue, _ = isolated_git_workspace(tmp_path)
    first = call_worker(root, queue, "E-C02-QA-ONE")
    assert first.returncode == 0, first.stderr
    second = call_worker(root, queue, "E-C02-QA-TWO")
    assert second.returncode == 2, second.stderr
    data = json.loads(second.stdout)
    assert data["successful"] == 0
    assert data["complete"] is False
    assert data["cumulative_qualified_deliveries"] == 50


def test_fifty_different_ids_for_one_artifact_count_only_once(tmp_path):
    root, queue_path, items = isolated_git_workspace(tmp_path, total=1)
    repeated = []
    for i in range(50):
        row = dict(items[0])
        row["action_id"] = f"E-QA-CLONE-{i:03d}"
        repeated.append(row)
    queue_path.write_text(json.dumps(repeated), encoding="utf-8")
    attempt = call_worker(root, queue_path, "E-C02-DUPLICATE-PROOF")
    assert attempt.returncode == 2, attempt.stderr
    report = json.loads(attempt.stdout)
    assert report["successful"] == 1
    assert report["complete"] is False
    assert report["cumulative_qualified_deliveries"] == 1


def test_fifty_unexecuted_queue_items_cannot_achieve_target(tmp_path):
    root, queue_path, items = isolated_git_workspace(tmp_path, total=1)
    pending = []
    for i in range(50):
        row = dict(items[0])
        row["action_id"] = f"E-QA-PENDING-{i:03d}"
        row["kind"] = "delivery_pending"
        pending.append(row)
    queue_path.write_text(json.dumps(pending), encoding="utf-8")
    result = call_worker(root, queue_path, "E-C02-PENDING")
    assert result.returncode == 2, result.stderr
    report = json.loads(result.stdout)
    assert report["successful"] == 0
    assert report["complete"] is False
