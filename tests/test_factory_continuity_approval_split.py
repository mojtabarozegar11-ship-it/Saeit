"""Offline invariants for manual VPS audit, owner-approved recovery and pause.

No remote execution, GitHub dispatch, production changes, or secret accesses.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/vps-factory-production-continuity.yml"
HOURLY_HEALTH = ROOT / ".github/workflows/vps-direct-ssh-system-health-readonly-20261031.yml"


def _job(name: str) -> str:
    source = WORKFLOW.read_text(encoding="utf-8").split("\njobs:\n", 1)[1]
    marker = f"  {name}:\n"
    assert source.count(marker) == 1
    rest = source.split(marker, 1)[1]
    return re.split(r"(?m)^  [a-z][a-z0-9-]*:$", rest, maxsplit=1)[0]


def _on() -> str:
    return WORKFLOW.read_text(encoding="utf-8").split("\non:\n", 1)[1].split(
        "\npermissions:\n", 1
    )[0]


def test_legacy_continuity_is_manual_only_no_secret_bearing_schedules_or_pushes():
    on_block = _on()
    assert "  workflow_dispatch:" in on_block
    assert "  schedule:" not in on_block
    assert "  push:" not in on_block
    assert "  pull_request:" not in on_block
    assert "  workflow_call:" not in on_block
    assert "      operation:" in on_block
    for value in ("audit", "recover", "pause"):
        assert f"          - {value}" in on_block
    assert "        default: audit" in on_block
    assert "        default: false" in on_block
    assert "scheduled-readonly-observation:" not in WORKFLOW.read_text(encoding="utf-8")
    assert "secrets: inherit" not in WORKFLOW.read_text(encoding="utf-8")


def test_manual_audit_needs_no_recovery_consent_and_uses_proven_runner():
    audit = _job("audit-readonly")
    assert "github.event_name == 'workflow_dispatch'" in audit
    assert "inputs.operation == 'audit'" in audit
    assert "github.actor == 'mojtabarozegar11-ship-it'" in audit
    assert "github.ref == 'refs/heads/main'" in audit
    assert "github.repository == 'mojtabarozegar11-ship-it/Saeit'" in audit
    assert "runs-on: [self-hosted, factory-vps]" in audit
    assert "actions/checkout@v4" in audit
    assert "persist-credentials: false" in audit
    assert "StrictHostKeyChecking=yes" in audit
    assert "FACTORY_AUDIT_READ_ONLY=true" in audit
    assert 'kill -TERM' not in audit
    assert 'nohup ' not in audit
    assert "os.replace(temp, path)" not in audit


def test_both_mutating_operations_require_owner_actor_and_two_assertions():
    for operation, name in (("recover", "ensure"), ("pause", "pause-loop-low-disk")):
        job = _job(name)
        assert "github.event_name == 'workflow_dispatch'" in job
        assert "github.ref == 'refs/heads/main'" in job
        assert "github.repository == 'mojtabarozegar11-ship-it/Saeit'" in job
        assert "github.actor == 'mojtabarozegar11-ship-it'" in job
        assert f"inputs.operation == '{operation}'" in job
        assert "inputs.recovery_authorized == true" in job
        assert "inputs.offhost_backup_verified == true" in job
        assert "runs-on: [self-hosted, factory-vps]" in job
    assert "os.replace(temp, path)" in _job("ensure")
    assert 'nohup "$script"' in _job("ensure")
    assert 'kill -TERM "$pid"' in _job("pause-loop-low-disk")


def test_invalid_or_unapproved_mutating_manual_requests_fail_closed():
    blocked = _job("blocked-unapproved-recovery")
    assert "github.event_name == 'workflow_dispatch'" in blocked
    assert "inputs.operation != 'audit'" in blocked
    assert "inputs.operation != 'recover'" in blocked
    assert "inputs.operation != 'pause'" in blocked
    assert "github.actor != 'mojtabarozegar11-ship-it'" in blocked
    assert "inputs.recovery_authorized != true" in blocked
    assert "inputs.offhost_backup_verified != true" in blocked
    assert "FACTORY_RECOVERY_GATE=BLOCKED_MISSING_OWNER_APPROVAL_OR_VERIFIED_BACKUP" in blocked
    assert "exit 1" in blocked
    assert "VPS_SSH_PRIVATE_KEY" not in blocked
    assert "ssh " not in blocked
    assert "sudo " not in blocked


def test_other_existing_health_workflow_keeps_hourly_read_only_route():
    """Retiring a dangerous schedule must not remove the separate health probe."""
    source = HOURLY_HEALTH.read_text(encoding="utf-8")
    assert "  schedule:" in source
    assert "cron: '17 * * * *'" in source
    assert "runs-on: [self-hosted, factory-vps]" in source
    assert "StrictHostKeyChecking=yes" in source
    assert "github.ref == 'refs/heads/main'" in source
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "FACTORY_AUTOSTART_BLOCKED_CAPACITY" in workflow
    assert "FACTORY_AUTOSTART_BLOCKED_RECOVERY_GATE" in workflow


def test_nonowner_audit_is_blocked_before_any_private_runner_starts():
    """Read-only inventory still exposes private VPS, DB and cron metadata."""
    blocked = _job("blocked-unapproved-recovery")
    audit = _job("audit-readonly")
    condition = blocked.split('    if: "', 1)[1].split('"\n', 1)[0]
    assert "github.actor != 'mojtabarozegar11-ship-it'" in condition
    assert "|| github.actor != 'mojtabarozegar11-ship-it' ||" in condition
    assert "inputs.operation != 'audit' && (" in condition
    assert "inputs.recovery_authorized != true" in condition
    assert "inputs.offhost_backup_verified != true" in condition
    assert "github.actor == 'mojtabarozegar11-ship-it'" in audit
    assert "github.actor == 'mojtabarozegar11-ship-it'" in _job("ensure")
    assert "github.actor == 'mojtabarozegar11-ship-it'" in _job("pause-loop-low-disk")
    assert "VPS_SSH_PRIVATE_KEY" not in blocked
    assert "VPS_SSH_PRIVATE_KEY" in audit


def test_manual_audit_does_not_require_mutating_backup_approvals():
    audit = _job("audit-readonly")
    assert "inputs.recovery_authorized == true" not in audit
    assert "inputs.offhost_backup_verified == true" not in audit
    assert "inputs.operation == 'audit'" in audit
    assert "  schedule:" not in _on()
    assert "  push:" not in _on()
