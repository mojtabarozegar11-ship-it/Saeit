"""Real Git receipts count, synthetic fixtures never count as production."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import mojtaba_bot_cycle_auditor as auditor
from deploy import mojtaba_bot_cycle_receipt_bridge as bridge
from test_c03_cycle_receipt_bridge import setup_manifest, git


def prepare(monkeypatch, root):
    monkeypatch.setattr(auditor, "ROOT", root)
    monkeypatch.setattr(bridge, "ROOT", root)
    monkeypatch.chdir(root)


def test_zero_manifests_means_zero_success_and_zero_sales(tmp_path, monkeypatch):
    repo = tmp_path / "checkout"
    repo.mkdir()
    git(repo, "init")
    prepare(monkeypatch, repo)
    result = auditor.audit()
    assert result["latest_round_verified_actions"] == 0
    assert result["latest_round_complete"] is False
    assert result["business_revenue"] == "not_verified_by_this_auditor"
    assert all(not lane["complete"] for lane in result["lanes"].values())


def test_one_real_committed_qa_receipt_is_one_of_fifty(tmp_path, monkeypatch):
    repo, relative, _, _ = setup_manifest(tmp_path, cycle="A")
    prepare(monkeypatch, repo)
    r = auditor.audit()
    assert r["manifest_count"] == 1
    assert r["lanes"]["A"]["latest_run_success"] == 1
    assert r["lanes"]["A"]["latest_run_missing"] == 49
    assert r["latest_round_verified_actions"] == 1
    assert r["latest_round_complete"] is False


def test_fifty_synthetic_files_are_correctly_counted_only_in_qa(tmp_path, monkeypatch):
    repo, _, _, _ = setup_manifest(tmp_path, cycle="D", number=50)
    prepare(monkeypatch, repo)
    r = auditor.audit()
    assert r["lanes"]["D"]["complete"] is True
    assert r["lanes"]["D"]["latest_run_success"] == 50
    assert r["latest_round_verified_actions"] == 50
    assert r["complete_lanes"] == 1
    assert r["latest_round_complete"] is False


def test_dirty_manifest_excluded_not_silently_counted(tmp_path, monkeypatch):
    repo, _, manifest, file = setup_manifest(tmp_path, cycle="B")
    manifest["actions"][0]["after"] = "changed without commit"
    file.write_text(json.dumps(manifest))
    prepare(monkeypatch, repo)
    r = auditor.audit()
    assert r["manifest_count"] == 1
    assert r["valid_manifest_count"] == 0
    assert len(r["manifest_errors"]) == 1
    assert r["latest_round_verified_actions"] == 0


def test_cross_lane_copy_of_same_artifact_does_not_double_count(tmp_path, monkeypatch):
    repo, _, manifest, _ = setup_manifest(tmp_path, cycle="A")
    copied = dict(manifest)
    copied["cycle"] = "B"
    copied["run_id"] = "B-C03-QA"
    copied["actions"] = [dict(manifest["actions"][0],
                              action_id="B-C03-COPIED-001")]
    b_path = repo / "runtime/cycle_receipts/B/B-copy.json"
    b_path.parent.mkdir(parents=True, exist_ok=True)
    b_path.write_text(json.dumps(copied))
    git(repo, "add", "runtime/cycle_receipts/B/B-copy.json")
    git(repo, "commit", "-m", "attempt duplicate artifact across lanes")
    prepare(monkeypatch, repo)
    audit = auditor.audit()
    assert audit["latest_round_verified_actions"] == 1
    assert audit["lanes"]["B"]["latest_run_success"] == 0
    assert audit["lanes"]["B"]["latest_run_rejected"] == 1
