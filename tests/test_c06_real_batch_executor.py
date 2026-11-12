"""C06 isolated execution proofs: 50 changes are 50 files, never 50 logs.

All generated files live in temporary test repos and are synthetic QA only.
No production work, deployment, payment or commercial delivery is implied.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1]
FILES = (
    "mojtaba_bot_cycle_batch_executor.py",
    "mojtaba_bot_cycle_coordinator.py",
    "mojtaba_bot_cycle_worker.py",
    "mojtaba_bot_cycle_receipt_bridge.py",
)


def run(root, *args):
    return subprocess.run(args, cwd=root, capture_output=True, text=True, timeout=240)


def git(root, *args):
    p = run(root, "git", *args)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


def checkout(tmp_path):
    root = tmp_path / "checkout"
    (root / "deploy").mkdir(parents=True)
    for name in FILES:
        shutil.copyfile(SRC / "deploy" / name, root / "deploy" / name)
    (root / "docs").mkdir()
    (root / "docs" / "source.md").write_text(
        "# QA source\nThis is noncommercial local provenance for the C06 test.\n"
    )
    git(root, "init")
    git(root, "config", "user.name", "C06 synthetic tests")
    git(root, "config", "user.email", "c06-test@example.invalid")
    git(root, "checkout", "-b", "work/c06-isolated-qa")
    git(root, "add", ".")
    git(root, "commit", "-m", "isolated QA source and no commercial content")
    return root


def job(i, cycle="A", *, target=None, content=None):
    prefix = {
        "A": "deliverables/books/",
        "B": "deliverables/research/",
        "C": "games/arrow-escape/",
        "D": "deliverables/products/",
        "E": "deliverables/command/",
    }[cycle]
    return {
        "action_id": f"{cycle}-C06-QA-{i:03d}",
        "path": target or f"{prefix}c06-qa-{i:03d}.md",
        "kind": "deliverable_created",
        "content": content or (
            "# Independent synthetic document " + str(i) + "\n"
            + "## Topic " + str(i) + "\n"
            + ("Unique QA-only source text for generated item "
               + str(i) + ". ") * 15
            + "\n## Limits\nAll numbers and topics here are artificial QA material. "
            + "This is never a licensed product, customer delivery or publication.\n"
        ),
        "before": "File was absent from the isolated source checkout",
        "change": "Create one independently named and varied local fixture artifact",
        "after": f"Git committed QA file {i} with distinct bytes and sections",
        "expected_sha256": None,
        "source_paths": ["docs/source.md"],
    }


def command(root, jobs_file, cycle, run_id, state, *, commit=False):
    a = [sys.executable, "deploy/mojtaba_bot_cycle_batch_executor.py",
         "--cycle", cycle, "--jobs", str(jobs_file), "--run-id", run_id,
         "--expected-branch", "work/c06-isolated-qa",
         "--state", str(state)]
    if commit:
        a.append("--commit-local")
    return run(root, *a)


def test_validate_only_makes_zero_changes_or_receipts(tmp_path):
    root = checkout(tmp_path)
    source = tmp_path / "jobs.json"
    source.write_text(json.dumps([job(i) for i in range(10)]))
    original_head = git(root, "rev-parse", "HEAD")
    proc = command(root, source, "A", "A-C06-DRY", tmp_path / "state.json")
    assert proc.returncode == 2, proc.stderr
    report = json.loads(proc.stdout)
    assert report["ready"] == 10
    assert report["committed"] == 0
    assert report["complete"] is False
    assert git(root, "rev-parse", "HEAD") == original_head
    assert not (root / "runtime").exists()


def test_fifty_real_git_changes_in_five_batches_and_one_manifest(tmp_path):
    root = checkout(tmp_path)
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps([job(i) for i in range(50)]))
    state = tmp_path / "ledger.json"
    result = command(root, jobs, "A", "A-C06-FIFTY-ISOLATED-QA", state, commit=True)
    assert result.returncode == 0, result.stderr + result.stdout[-700:]
    report = json.loads(result.stdout)
    assert report["processed"] == 50
    assert report["accepted"] == 50
    assert report["blocked"] == 0
    assert report["complete"] is True
    assert len(report["artifact_commits"]) == 5
    receipt = root / report["receipt_path"]
    manifest = json.loads(receipt.read_text())
    assert len(manifest["actions"]) == 50
    assert len(set(x["evidence"][1] for x in manifest["actions"])) == 50
    assert len(json.loads(state.read_text())["runs"]["A-C06-FIFTY-ISOLATED-QA"]["actions"]) == 50
    assert int(git(root, "rev-list", "--count", "HEAD")) == 7
    assert not git(root, "status", "--porcelain")
    replay = command(root, jobs, "A", "A-C06-FIFTY-ISOLATED-QA", state, commit=True)
    assert replay.returncode == 2
    assert json.loads(replay.stdout)["accepted"] == 0


@pytest.mark.parametrize("lane", list("ABCDE"))
def test_each_lane_accepts_its_own_substantive_local_fixture(tmp_path, lane):
    root = checkout(tmp_path)
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps([job(1, lane)]))
    state = tmp_path / "ledger.json"
    result = command(root, jobs, lane, lane + "-C06-QA-ONE", state, commit=True)
    assert result.returncode == 0 or result.returncode == 2, result.stderr
    response = json.loads(result.stdout)
    assert response["accepted"] == 1
    assert response["complete"] is False


def test_pending_legacy_queues_do_not_generate_fake_files(tmp_path):
    root = checkout(tmp_path)
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps([{
        "action_id": "A-OLD-QUEUE",
        "kind": "delivery_pending",
        "status": "queued_not_executed",
    }]))
    result = command(root, jobs, "A", "A-C06-PENDING", tmp_path / "state.json",
                     commit=True)
    assert result.returncode == 2
    assert "invalid job fields" in json.loads(result.stdout)["error"]
    assert not (root / "runtime").exists()


def test_duplicate_content_and_traversal_fail_closed(tmp_path):
    root = checkout(tmp_path)
    item = job(1)
    copied = job(2, content=item["content"])
    cases = (
        [item, copied],
        [dict(item, path="deliverables/books/../../.github/evil.yml")],
        [dict(item, path="deliverables/research/not-my-lane.md")],
        [dict(item, content="bad")],
        [dict(item, source_paths=["private/nonexistent.txt"])],
    )
    for i, case in enumerate(cases):
        jobs = tmp_path / f"jobs-{i}.json"
        jobs.write_text(json.dumps(case))
        before = git(root, "rev-parse", "HEAD")
        outcome = command(root, jobs, "A", "A-C06-BAD-" + str(i),
                          tmp_path / "state.json", commit=True)
        assert outcome.returncode == 2
        assert json.loads(outcome.stdout)["accepted"] == 0
        assert git(root, "rev-parse", "HEAD") == before


def test_no_write_if_unauthorized_branch_or_dirty_checkout(tmp_path):
    root = checkout(tmp_path)
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps([job(1)]))
    wrong = run(root, sys.executable, "deploy/mojtaba_bot_cycle_batch_executor.py",
                "--cycle", "A", "--jobs", str(jobs), "--run-id", "A-C06-WRONG",
                "--expected-branch", "main", "--state", str(tmp_path / "state.json"),
                "--commit-local")
    assert wrong.returncode == 2
    (root / "unexpected-private-note.txt").write_text("not to be changed")
    dirty = command(root, jobs, "A", "A-C06-DIRTY", tmp_path / "state.json",
                    commit=True)
    assert dirty.returncode == 2
    assert "dirty checkout" in json.loads(dirty.stdout)["error"]
    assert (root / "unexpected-private-note.txt").read_text() == "not to be changed"
