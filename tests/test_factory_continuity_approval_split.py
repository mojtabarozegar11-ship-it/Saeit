"""Offline invariants for manual VPS audit, owner-approved recovery and pause.

No remote execution, GitHub dispatch, production changes, or secret accesses.
"""
import re
import subprocess
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
    assert "FACTORY_RECOVERY_GATE=BLOCKED_UNAUTHORIZED_OR_REPLAY_OR_MISSING_APPROVAL" in blocked
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


def test_all_private_jobs_block_reruns_and_nonowner_triggering_actor():
    """GitHub re-runs retain the original github.actor permissions.

    A collaborator may re-run the original owner's job. All VPS-connected
    jobs must therefore check actual triggering_actor and run_attempt.
    """
    workflow = WORKFLOW.read_text(encoding="utf-8")
    blocker = _job("blocked-unapproved-recovery")
    assert "github.triggering_actor != 'mojtabarozegar11-ship-it'" in blocker
    assert "github.run_attempt != '1'" in blocker
    assert "BLOCKED_UNAUTHORIZED_OR_REPLAY_OR_MISSING_APPROVAL" in blocker
    for name in ("audit-readonly", "ensure", "pause-loop-low-disk"):
        job = _job(name)
        assert "github.actor == 'mojtabarozegar11-ship-it'" in job
        assert "github.triggering_actor == 'mojtabarozegar11-ship-it'" in job
        assert "github.run_attempt == '1'" in job
        assert "github.ref == 'refs/heads/main'" in job
        assert "github.event_name == 'workflow_dispatch'" in job
    assert "  schedule:" not in _on()
    assert "  push:" not in _on()
    assert "  pull_request:" not in _on()


def test_replay_blocker_is_on_hosted_runner_without_private_credentials():
    blocker = _job("blocked-unapproved-recovery")
    assert "runs-on: ubuntu-24.04" in blocker
    assert "FACTORY_RECOVERY_GATE=BLOCKED_UNAUTHORIZED_OR_REPLAY_OR_MISSING_APPROVAL" in blocker
    assert "exit 1" in blocker
    assert "secrets." not in blocker
    assert "VPS_SSH_PRIVATE_KEY" not in blocker
    assert "ssh " not in blocker
    assert "sudo " not in blocker


def _cron_block() -> str:
    """Extract the exact production Bash Cron audit without any SSH wrapper."""
    source = WORKFLOW.read_text(encoding="utf-8")
    marker = "          # Report only active lines from this verified githubops user's"
    end = '          ops="$root/operations"'
    assert source.count(marker) == 1
    assert source.count(end) == 3
    return source.split(marker, 1)[1].split(end, 1)[0]


def _exercise_cron_audit(cron_shell_function: str) -> subprocess.CompletedProcess:
    shell = "set -euo pipefail\n" + cron_shell_function + "\n" + _cron_block()
    return subprocess.run(
        ["bash", "-c", shell], capture_output=True, text=True,
        timeout=5, check=False,
    )


def test_manual_cron_audit_classifies_active_only_and_hides_commands():
    mock = (
        'crontab() { printf "%s\n" '
        '"* * * * * /secret/master --token NEVER_PRINT # SAEIT_MASTER_AGENT_V1" '
        '"# * * * * * /secret/disabled # SAEIT_FACTORY_EVERY_MINUTE_V1" '
        '"  # * * * * * /secret/disabled # SAEIT_MASTER_AGENT_V1" '
        '"1 * * * * /secret/worker # leech" '
        '"0 1 * * * /secret/other"; }'
    )
    result = _exercise_cron_audit(mock)
    assert result.returncode == 0, result.stderr
    assert "FACTORY_AUDIT_CRON_READ=observed" in result.stdout
    assert "FACTORY_AUDIT_CRON_ACTIVE_LINES=3" in result.stdout
    assert "FACTORY_AUDIT_CRON_MASTER_TAGS=1" in result.stdout
    assert "FACTORY_AUDIT_CRON_LEECH_TAGS=1" in result.stdout
    assert "FACTORY_AUDIT_CRON_OTHER_LINES=2" in result.stdout
    assert "/secret/" not in result.stdout
    assert "NEVER_PRINT" not in result.stdout


def test_manual_cron_audit_accepts_only_expected_no_crontab():
    empty = _exercise_cron_audit('crontab() { printf ""; return 0; }')
    assert empty.returncode == 0
    assert "FACTORY_AUDIT_CRON_READ=observed" in empty.stdout
    assert "FACTORY_AUDIT_CRON_ACTIVE_LINES=0" in empty.stdout

    missing = _exercise_cron_audit(
        'crontab() { printf "no crontab for githubops\n" >&2; return 1; }'
    )
    assert missing.returncode == 0, missing.stderr
    assert "FACTORY_AUDIT_CRON_READ=none_installed" in missing.stdout
    assert "FACTORY_AUDIT_CRON_MASTER_TAGS=0" in missing.stdout


def test_manual_cron_audit_fails_closed_on_denial_or_ambiguous_stderr():
    for stub in (
        'crontab() { printf "permission denied\n" >&2; return 1; }',
        'crontab() { printf "no crontab for githubops\nextra warning\n" >&2; return 1; }',
        'crontab() { printf "no crontab for githubops\n" >&2; return 2; }',
    ):
        result = _exercise_cron_audit(stub)
        assert result.returncode != 0
        assert "FACTORY_AUDIT_CRON_READ=unavailable_fail_closed" in result.stdout
        assert "permission denied" not in result.stdout
        assert "extra warning" not in result.stdout
        assert "/secret/" not in result.stdout
