"""C03 receipt-handoff contract. Everything uses disposable local Git repos."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from deploy import mojtaba_bot_cycle_receipt_bridge as bridge

ROOT = Path(__file__).resolve().parents[1]


def git(root, *args):
    p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


def setup_manifest(tmp_path, cycle="A", number=1):
    root = tmp_path / "test-checkout"
    root.mkdir()
    (root / "deploy").mkdir()
    for file in ("mojtaba_bot_cycle_worker.py", "mojtaba_bot_cycle_coordinator.py",
                 "mojtaba_bot_cycle_receipt_bridge.py"):
        shutil.copyfile(ROOT / "deploy" / file, root / "deploy" / file)
    git(root, "init")
    git(root, "config", "user.email", "qa@example.invalid")
    git(root, "config", "user.name", "C03 Local Test")
    candidates = []
    for i in range(number):
        relative = f"deliverables/qa/{cycle.lower()}-{i:03d}.txt"
        artifact = root / relative
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(f"Independent synthetic QA artifact {cycle}-{i}\n")
        candidates.append((relative, hashlib.sha256(artifact.read_bytes()).hexdigest()))
    git(root, "add", "deliverables")
    git(root, "commit", "-m", "create synthetic QA assets")
    sha = git(root, "rev-parse", "HEAD")
    actions = [
        {
            "action_id": f"{cycle}-QA-{i:03d}",
            "item": rel,
            "kind": "deliverable_created",
            "before": "absent", "change": "create synthetic QA file",
            "after": f"file created {i}",
            "evidence": ["commit:" + sha, "path:" + rel, "sha256:" + digest],
        } for i, (rel, digest) in enumerate(candidates)
    ]
    manifest = {
        "schema_version": "1.0", "engine": "mojtaba.bot.ai", "cycle": cycle,
        "run_id": cycle + "-C03-QA",
        "actions": actions,
    }
    manifest_rel = f"runtime/cycle_receipts/{cycle}/qa.json"
    file = root / manifest_rel
    file.parent.mkdir(parents=True)
    file.write_text(json.dumps(manifest))
    git(root, "add", manifest_rel)
    git(root, "commit", "-m", "commit QA handoff manifest")
    return root, manifest_rel, manifest, file


def test_reads_only_clean_committed_receipt_manifest(tmp_path, monkeypatch):
    root, path, manifest, _ = setup_manifest(tmp_path)
    monkeypatch.setattr(bridge, "ROOT", root)
    assert bridge.load_manifest("A", path) == manifest


def test_rejects_uncommitted_manifest_edits(tmp_path, monkeypatch):
    root, path, manifest, file = setup_manifest(tmp_path)
    monkeypatch.setattr(bridge, "ROOT", root)
    manifest["actions"][0]["after"] = "not committed"
    file.write_text(json.dumps(manifest))
    with pytest.raises(bridge.ManifestError,
                       match="receipt_manifest_differs_from_commit"):
        bridge.load_manifest("A", path)


def test_rejects_cross_lane_submission(tmp_path, monkeypatch):
    root, path, _, _ = setup_manifest(tmp_path)
    monkeypatch.setattr(bridge, "ROOT", root)
    with pytest.raises(bridge.ManifestError, match="path_not_allowed"):
        bridge.load_manifest("B", path)


def test_rejects_fake_receipt_kind_and_duplicate_artifact(tmp_path, monkeypatch):
    root, path, manifest, file = setup_manifest(tmp_path, number=2)
    monkeypatch.setattr(bridge, "ROOT", root)
    manifest["actions"][0]["kind"] = "verified_order"
    file.write_text(json.dumps(manifest))
    git(root, "add", path)
    git(root, "commit", "-m", "bad receipt kind")
    with pytest.raises(bridge.ManifestError, match="non_delivery_kind"):
        bridge.load_manifest("A", path)
    manifest["actions"][0]["kind"] = "deliverable_created"
    manifest["actions"][1]["evidence"] = list(manifest["actions"][0]["evidence"])
    file.write_text(json.dumps(manifest))
    git(root, "add", path)
    git(root, "commit", "-m", "duplicate artifact")
    with pytest.raises(bridge.ManifestError,
                       match="repeated_or_administrative_artifact"):
        bridge.load_manifest("A", path)


def test_rejects_receipt_report_as_deliverable(tmp_path, monkeypatch):
    root, path, manifest, file = setup_manifest(tmp_path)
    monkeypatch.setattr(bridge, "ROOT", root)
    manifest["actions"][0]["evidence"][1] = "path:runtime/cycle_receipts/A/qa.json"
    file.write_text(json.dumps(manifest))
    git(root, "add", path)
    git(root, "commit", "-m", "invalid admin artifact")
    with pytest.raises(bridge.ManifestError,
                       match="repeated_or_administrative_artifact"):
        bridge.load_manifest("A", path)


def test_real_bridge_calls_worker_and_wont_claim_one_as_fifty(tmp_path):
    root, relative, _, _ = setup_manifest(tmp_path)
    process = subprocess.run(
        [sys.executable, "deploy/mojtaba_bot_cycle_receipt_bridge.py",
         "--cycle", "A", "--manifest", relative, "--state", "state.json"],
        cwd=root, capture_output=True, text=True,
    )
    assert process.returncode == 2, process.stderr
    data = json.loads(process.stdout)
    assert data["run_id"] == "A-C03-QA"
    assert data["submitted_receipt_candidates"] == 1
    assert data["successful"] == 1
    assert data["complete"] is False
    assert data["cumulative_qualified_deliveries"] == 1


def test_bridge_fifty_distinct_committed_files_achieves_only_test_quota(tmp_path):
    root, relative, _, _ = setup_manifest(tmp_path, number=50)
    process = subprocess.run(
        [sys.executable, "deploy/mojtaba_bot_cycle_receipt_bridge.py",
         "--cycle", "A", "--manifest", relative, "--state", "state.json"],
        cwd=root, capture_output=True, text=True,
    )
    assert process.returncode == 0, process.stderr
    data = json.loads(process.stdout)
    assert data["successful"] == 50
    assert data["complete"] is True
    assert len(json.loads((root / "state.json").read_text())["runs"]) == 1
    replay = subprocess.run(
        [sys.executable, "deploy/mojtaba_bot_cycle_receipt_bridge.py",
         "--cycle", "A", "--manifest", relative, "--state", "state.json"],
        cwd=root, capture_output=True, text=True,
    )
    assert replay.returncode == 2
    assert json.loads(replay.stdout)["successful"] == 0
