"""C02 regression tests: observation is not a shipped deliverable."""
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "deploy" / "mojtaba_bot_cycle_worker.py"
COORD = ROOT / "deploy" / "mojtaba_bot_cycle_coordinator.py"

def test_repo_readonly_does_not_count_as_delivery():
    with TemporaryDirectory() as d:
        q = Path(d) / "queue.json"
        state = Path(d) / "state.json"
        q.write_text(json.dumps([{
            "action_id": "TEST-C02-OBSERVE", "item": "schema check",
            "kind": "repo_readonly", "operation": "json_validate",
            "path": "runtime/unified_master_stage_v1.json",
            "before": "not inspected", "change": "parse JSON", "after": "inspected"
        }]), encoding="utf-8")
        p = subprocess.run([sys.executable, str(WORKER), "--cycle", "E",
                            "--queue", str(q), "--state", str(state)],
                           cwd=ROOT, text=True, capture_output=True)
        assert p.returncode == 2, p.stderr
        report = json.loads(p.stdout)
        assert report["observed"] == 1
        assert report["successful"] == 0
        assert report["cumulative_qualified_deliveries"] == 0
        assert report["complete"] is False

def test_legacy_sha_only_success_does_not_count():
    with TemporaryDirectory() as d:
        q = Path(d) / "queue.json"
        state = Path(d) / "state.json"
        state.write_text(json.dumps({"schema": 1, "runs": {
            "legacy": {"cycle": "E", "actions": {
                "LEGACY-SHA": {"status": "success", "kind": "repo_readonly",
                               "evidence": ["sha256:placeholder"]}
            }}
        }}), encoding="utf-8")
        q.write_text(json.dumps([{
            "action_id": "TEST-C02-NEW-OBSERVE", "item": "read file",
            "kind": "repo_readonly", "operation": "file_exists",
            "path": "runtime/unified_master_stage_v1.json",
            "before": "unknown", "change": "inspect", "after": "observed"
        }]), encoding="utf-8")
        p = subprocess.run([sys.executable, str(WORKER), "--cycle", "E",
                            "--queue", str(q), "--state", str(state)],
                           cwd=ROOT, text=True, capture_output=True)
        assert p.returncode == 2, p.stderr
        assert json.loads(p.stdout)["cumulative_qualified_deliveries"] == 0

def test_coordinator_refuses_readonly_success():
    with TemporaryDirectory() as d:
        p = subprocess.run([sys.executable, str(COORD), "--state",
                            str(Path(d) / "state.json"), "record",
                            "--cycle", "E", "--action-id", "X-01",
                            "--item", "inspection", "--kind", "repo_readonly",
                            "--before", "no", "--change", "inspect",
                            "--after", "inspected", "--status", "success",
                            "--evidence", "file:README.md"],
                           cwd=ROOT, capture_output=True, text=True)
        assert p.returncode != 0
        assert "cannot be successful" in p.stderr

def test_repository_path_cannot_escape_checkout():
    with TemporaryDirectory() as d:
        q = Path(d) / "queue.json"
        state = Path(d) / "state.json"
        q.write_text(json.dumps([{
            "action_id": "TEST-C02-PATH", "item": "external path",
            "kind": "repo_readonly", "operation": "sha256",
            "path": "../../etc/passwd", "before": "unknown",
            "change": "inspect", "after": "must not read"
        }]), encoding="utf-8")
        p = subprocess.run([sys.executable, str(WORKER), "--cycle", "A",
                            "--queue", str(q), "--state", str(state)],
                           cwd=ROOT, capture_output=True, text=True)
        assert p.returncode == 2, p.stderr
        result = json.loads(p.stdout)["results"][0]
        assert result["status"] == "failed"
        assert "path_outside_repo" in str(result["evidence"])

def test_old_qualifications_cannot_complete_new_cycle():
    with TemporaryDirectory() as d:
        q = Path(d) / "q.json"
        state = Path(d) / "state.json"
        old = {"OLD-" + str(i): {
            "kind": "source_change", "status": "success",
            "evidence": ["old:receipt"]} for i in range(55)}
        state.write_text(json.dumps({"schema": 1, "runs": {
            "old-run": {"cycle": "E", "actions": old}
        }}), encoding="utf-8")
        q.write_text(json.dumps([{
            "action_id": "E-TEST-NO-BACKFILL", "item": "inspect",
            "kind": "repo_readonly", "operation": "file_exists",
            "path": "runtime/unified_master_stage_v1.json",
            "before": "unverified", "change": "inspect", "after": "observed"
        }]), encoding="utf-8")
        p = subprocess.run([sys.executable, str(WORKER), "--cycle", "E",
                            "--queue", str(q), "--state", str(state)],
                           cwd=ROOT, capture_output=True, text=True)
        assert p.returncode == 2, p.stderr
        report = json.loads(p.stdout)
        assert report["stage_target_met"] is True
        assert report["cumulative_qualified_deliveries"] == 55
        assert report["successful"] == 0
        assert report["complete"] is False
