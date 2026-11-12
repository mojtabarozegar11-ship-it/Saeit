"""C02 coordinator evidence and retry contract (local Git-only tests)."""
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COORD = ROOT / "deploy" / "mojtaba_bot_cycle_coordinator.py"


def git(repo, *parts):
    return subprocess.check_output(["git", *parts], cwd=repo, text=True).strip()


def workspace(tmp_path):
    repo = tmp_path / "gitrepo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.name", "C02 QA")
    git(repo, "config", "user.email", "qa@example.invalid")
    file = repo / "deliverables" / "item.txt"
    file.parent.mkdir()
    file.write_text("meaningful offline delivery content\n", encoding="utf-8")
    git(repo, "add", "deliverables/item.txt")
    git(repo, "commit", "-m", "create deliverable")
    commit = git(repo, "rev-parse", "HEAD")
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    return repo, commit, digest


def record(repo, *, run_id, action_id, status, kind="source_change",
           evidence=()):
    cmd = [
        sys.executable, str(COORD), "--state", str(repo / "state.json"),
        "record", "--cycle", "E", "--run-id", run_id,
        "--action-id", action_id, "--item", "item",
        "--kind", kind, "--before", "pending",
        "--change", "changed", "--after", "saved",
        "--status", status,
    ]
    for item in evidence:
        cmd.extend(["--evidence", item])
    return subprocess.run(cmd, cwd=repo, text=True, capture_output=True)


def test_committed_exact_file_proof_is_accepted_once(tmp_path):
    repo, commit, digest = workspace(tmp_path)
    evidence = ("commit:" + commit, "path:deliverables/item.txt", "sha256:" + digest)
    first = record(repo, run_id="E-R1", action_id="E-C02-REAL",
                   status="success", evidence=evidence)
    assert first.returncode == 0, first.stderr
    repeated = record(repo, run_id="E-R2", action_id="E-C02-REAL",
                      status="success", evidence=evidence)
    assert repeated.returncode != 0
    assert "previously completed" in repeated.stderr


def test_blocked_can_be_retried_in_new_run_without_false_success(tmp_path):
    repo, _, _ = workspace(tmp_path)
    first = record(repo, run_id="E-R1", action_id="E-C02-PENDING",
                   status="blocked", kind="delivery_pending")
    second = record(repo, run_id="E-R2", action_id="E-C02-PENDING",
                    status="blocked", kind="delivery_pending")
    same_run = record(repo, run_id="E-R2", action_id="E-C02-PENDING",
                      status="blocked", kind="delivery_pending")
    assert first.returncode == second.returncode == 0
    assert same_run.returncode != 0
    assert "duplicate action_id in same run" in same_run.stderr


@pytest.mark.parametrize("bad_proof", [
    ("commit:" + "0" * 40, "path:deliverables/item.txt", "sha256:fake"),
    ("commit:" + "0" * 40, "path:../../etc/passwd", "sha256:" + "0" * 64),
])
def test_fake_or_outside_repo_proof_is_rejected(tmp_path, bad_proof):
    repo, _, _ = workspace(tmp_path)
    failure = record(repo, run_id="E-R1", action_id="E-C02-FAKE",
                     status="success", evidence=bad_proof)
    assert failure.returncode != 0
    assert "verified Git commit" in failure.stderr


def test_received_payment_cannot_be_invented_with_text_evidence(tmp_path):
    repo, _, _ = workspace(tmp_path)
    failure = record(repo, run_id="E-R1", action_id="E-C02-SALE",
                     status="success", kind="verified_order",
                     evidence=("receipt:looks-paid",))
    assert failure.returncode != 0
    assert "verified Git commit" in failure.stderr


def test_sha_mismatch_rejected_even_with_real_commit(tmp_path):
    repo, commit, _ = workspace(tmp_path)
    failure = record(repo, run_id="E-R1", action_id="E-C02-WRONG-HASH",
                     status="success", evidence=(
                         "commit:" + commit, "path:deliverables/item.txt",
                         "sha256:" + "f" * 64,
                     ))
    assert failure.returncode != 0
    assert "verified Git commit" in failure.stderr


def test_older_valid_action_remains_verifiable_after_later_file_revision(tmp_path):
    repo, first_commit, first_digest = workspace(tmp_path)
    first = record(repo, run_id="E-IMMUTABLE-ONE", action_id="E-ITEM-ORIGINAL",
                   status="success", evidence=(
                       "commit:" + first_commit, "path:deliverables/item.txt",
                       "sha256:" + first_digest,
                   ))
    assert first.returncode == 0, first.stderr
    file = repo / "deliverables" / "item.txt"
    file.write_text("A new independently changed content revision\n",
                    encoding="utf-8")
    git(repo, "add", "deliverables/item.txt")
    git(repo, "commit", "-m", "second actual revision")
    second_commit = git(repo, "rev-parse", "HEAD")
    second_digest = hashlib.sha256(file.read_bytes()).hexdigest()
    from deploy.mojtaba_bot_cycle_coordinator import verified_git_artifact
    current = Path.cwd()
    import os
    try:
        os.chdir(repo)
        assert verified_git_artifact("source_change", [
            "commit:" + first_commit,
            "path:deliverables/item.txt",
            "sha256:" + first_digest,
        ])
    finally:
        os.chdir(current)
    second = record(repo, run_id="E-IMMUTABLE-TWO", action_id="E-ITEM-REVISED",
                    status="success", evidence=(
                        "commit:" + second_commit, "path:deliverables/item.txt",
                        "sha256:" + second_digest,
                    ))
    assert second.returncode == 0, second.stderr


def test_uncommitted_working_tree_change_does_not_forge_original_proof(tmp_path):
    repo, original_commit, _ = workspace(tmp_path)
    file = repo / "deliverables" / "item.txt"
    file.write_text("uncommitted replacement\n", encoding="utf-8")
    fraudulent_digest = hashlib.sha256(file.read_bytes()).hexdigest()
    failure = record(repo, run_id="E-UNCOMMITTED", action_id="E-FORGED-BYTES",
                     status="success", evidence=(
                         "commit:" + original_commit,
                         "path:deliverables/item.txt",
                         "sha256:" + fraudulent_digest,
                     ))
    assert failure.returncode != 0
    assert "verified Git commit" in failure.stderr


def test_old_unrecorded_commits_cannot_claim_new_hourly_action(tmp_path):
    import os
    repo, _, digest = workspace(tmp_path)
    old_date = "2024-01-01T00:00:00+00:00"
    env = dict(os.environ, GIT_AUTHOR_DATE=old_date, GIT_COMMITTER_DATE=old_date)
    amended = subprocess.run(
        ["git", "commit", "--amend", "--no-edit", "--date", old_date],
        cwd=repo, env=env, capture_output=True, text=True,
    )
    assert amended.returncode == 0, amended.stderr
    old_commit = git(repo, "rev-parse", "HEAD")
    proof = ["commit:" + old_commit, "path:deliverables/item.txt", "sha256:" + digest]
    from deploy.mojtaba_bot_cycle_coordinator import verified_git_artifact
    current = Path.cwd()
    try:
        os.chdir(repo)
        assert verified_git_artifact("source_change", proof)
        assert not verified_git_artifact(
            "source_change", proof, max_age_seconds=75 * 60
        )
    finally:
        os.chdir(current)
    rejected = record(repo, run_id="E-STALE-01", action_id="E-STALE-CLAIM",
                      status="success", evidence=proof)
    assert rejected.returncode != 0
    assert "verified Git commit" in rejected.stderr


def test_coordinator_summary_rejects_fifty_fake_legacy_successes(tmp_path):
    import json
    repo, _, _ = workspace(tmp_path)
    state = {"schema": 1, "runs": {
        "E-LEGACY-FAKE": {
            "cycle": "E", "target": 50, "started_at": "2024-01-01T00:00:00Z",
            "closed_at": None,
            "actions": {
                f"E-LEGACY-{i}": {
                    "status": "success", "kind": "repo_readonly",
                    "evidence": ["sha256:fake"]
                } for i in range(55)
            },
        }
    }}
    (repo / "state.json").write_text(json.dumps(state), encoding="utf-8")
    p = execute_summary = subprocess.run(
        [sys.executable, str(COORD), "--state", str(repo / "state.json"),
         "summary", "--cycle", "E", "--run-id", "E-LEGACY-FAKE"],
        cwd=repo, text=True, capture_output=True,
    )
    assert execute_summary.returncode == 0, p.stderr
    report = json.loads(p.stdout)
    assert report["recorded"] == 55
    assert report["success"] == 0
    assert report["unverified_legacy_success"] == 55
    assert report["complete"] is False


def test_coordinator_summary_counts_one_verified_change(tmp_path):
    import json
    repo, commit, digest = workspace(tmp_path)
    outcome = record(repo, run_id="E-NEW", action_id="E-SINGLE-REAL",
                     status="success", evidence=(
                         "commit:" + commit,
                         "path:deliverables/item.txt",
                         "sha256:" + digest,
                     ))
    assert outcome.returncode == 0, outcome.stderr
    summary = subprocess.run(
        [sys.executable, str(COORD), "--state", str(repo / "state.json"),
         "summary", "--cycle", "E", "--run-id", "E-NEW"],
        cwd=repo, capture_output=True, text=True,
    )
    assert summary.returncode == 0, summary.stderr
    actual = json.loads(summary.stdout)
    assert actual["success"] == 1
    assert actual["remaining"] == 49
    assert actual["complete"] is False


def test_restored_identical_file_under_new_commit_is_not_new_action(tmp_path):
    """Same bytes restored in later commit must not pass as another delivery."""
    repo, original_commit, digest = workspace(tmp_path)
    evidence = (
        "commit:" + original_commit,
        "path:deliverables/item.txt",
        "sha256:" + digest,
    )
    accepted = record(repo, run_id="E-REPLAY-FIRST", action_id="E-REPLAY-001",
                      status="success", evidence=evidence)
    assert accepted.returncode == 0, accepted.stderr
    target = repo / "deliverables" / "item.txt"
    original = target.read_bytes()
    target.write_text("temporarily changed meaningful content\n")
    git(repo, "add", "deliverables/item.txt")
    git(repo, "commit", "-m", "intermediate distinct version")
    target.write_bytes(original)
    git(repo, "add", "deliverables/item.txt")
    git(repo, "commit", "-m", "restore exact original bytes")
    restored = git(repo, "rev-parse", "HEAD")
    rejected = record(repo, run_id="B-REPLAY-SECOND", action_id="B-REPLAY-002",
                      status="success", evidence=(
                          "commit:" + restored,
                          "path:deliverables/item.txt",
                          "sha256:" + digest,
                      ))
    assert rejected.returncode != 0
    assert "duplicate successful artifact proof" in rejected.stderr
