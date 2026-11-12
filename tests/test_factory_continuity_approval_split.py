"""Offline invariants for scheduled VPS inventory vs authorized manual recovery.

No remote execution, GitHub dispatch, production files, or secrets.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/vps-factory-production-continuity.yml"
OBSERVER = ROOT / ".github/workflows/mojtaba-live-topology-readonly.yml"


def _job(name: str) -> str:
    source = WORKFLOW.read_text(encoding="utf-8").split("\njobs:\n", 1)[1]
    marker = f"  {name}:\n"
    assert source.count(marker) == 1
    rest = source.split(marker, 1)[1]
    return re.split(r"(?m)^  [a-z][a-z0-9-]*:$", rest, maxsplit=1)[0]


def test_schedule_is_delegated_to_existing_main_only_readonly_inventory():
    scheduled = _job("scheduled-readonly-observation")
    assert "github.event_name == 'schedule'" in scheduled
    assert "github.ref == 'refs/heads/main'" in scheduled
    assert "github.repository == 'mojtabarozegar11-ship-it/Saeit'" in scheduled
    assert "uses: ./.github/workflows/mojtaba-live-topology-readonly.yml" in scheduled
    assert "secrets: inherit" in scheduled
    observer = OBSERVER.read_text(encoding="utf-8")
    assert "  workflow_call:" in observer
    assert "github.ref == 'refs/heads/main'" in observer
    assert "runs-on: [self-hosted, factory-vps]" in observer
    assert "MOJTABA_DUAL_HOST_GATE=BLOCKED_INCOMPLETE" in observer
    assert "MOJTABA_DUAL_HOST_GATE=PASS_OBSERVATIONS_ONLY" in observer
    assert "StrictHostKeyChecking=yes" in observer


def test_factory_mutating_recovery_runs_only_with_two_owner_assertions():
    ensure = _job("ensure")
    assert "github.event_name == 'workflow_dispatch'" in ensure
    assert "github.ref == 'refs/heads/main'" in ensure
    assert "github.repository == 'mojtabarozegar11-ship-it/Saeit'" in ensure
    assert "inputs.recovery_authorized == true" in ensure
    assert "inputs.offhost_backup_verified == true" in ensure
    assert "runs-on: [self-hosted, factory-vps]" in ensure
    assert "github.event_name != 'push'" not in ensure
    assert "runs-on: ubuntu-latest" not in ensure
    assert "os.replace(temp, path)" in ensure
    assert 'nohup "$script"' in ensure
    assert "StrictHostKeyChecking=yes" in ensure


def test_unapproved_manual_event_fails_loudly_without_remote_execution():
    blocked = _job("blocked-unapproved-recovery")
    assert "github.event_name == 'workflow_dispatch'" in blocked
    assert "inputs.recovery_authorized != true" in blocked
    assert "inputs.offhost_backup_verified != true" in blocked
    assert "FACTORY_RECOVERY_GATE=BLOCKED_MISSING_OWNER_APPROVAL_OR_VERIFIED_BACKUP" in blocked
    assert "exit 1" in blocked
    assert "VPS_SSH_PRIVATE_KEY" not in blocked
    assert "ssh " not in blocked
    assert "sudo " not in blocked


def test_no_schedule_may_enter_mutating_job_and_legacy_safety_guards_remain():
    scheduled = _job("scheduled-readonly-observation")
    ensure = _job("ensure")
    assert "github.event_name == 'schedule'" in scheduled
    assert "github.event_name == 'schedule'" not in ensure
    assert "inputs.recovery_authorized == true" in ensure
    assert "inputs.offhost_backup_verified == true" in ensure
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert 'default: false' in workflow
    assert "pause-loop-low-disk:" in workflow
    assert "audit-readonly:" in workflow
    assert "FACTORY_AUTOSTART_BLOCKED_CAPACITY" in workflow
    assert "FACTORY_AUTOSTART_BLOCKED_RECOVERY_GATE" in workflow
