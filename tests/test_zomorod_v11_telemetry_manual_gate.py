"""Static safety gates for V11 site-agent telemetry activation.

These checks are source-only: no connection, credential, workflow dispatch,
PHP cycle, database write, or production receipt is performed.
"""
from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/zomorod-v11-agent-hourly.yml"
)


def test_v11_diagnostics_requires_explicit_manual_dispatch():
    source = WORKFLOW.read_text(encoding="utf-8")
    events = source.split("permissions:", 1)[0]
    assert "\n  workflow_dispatch:" in events
    assert "\n  schedule:" not in events
    assert "\n  push:" not in events
    assert "\n  pull_request:" not in events
    assert "cron:" not in events


def test_v11_runtime_execution_remains_beneath_pinned_relay():
    source = WORKFLOW.read_text(encoding="utf-8")
    relay = source.index("- name: Prepare pinned cPanel relay")
    verified = source.index('echo "PINNED_RELAY=verified"')
    cycle = source.index("- name: Check all eleven isolated site agents")
    assert relay < verified < cycle
    assert "ProxyJump saeit-vps" in source
    assert "StrictHostKeyChecking yes" in source
    assert "IdentitiesOnly yes" in source
    assert "ForwardAgent no" in source
    assert "StrictHostKeyChecking no" not in source


def test_v11_agent_cycle_and_audit_guards_are_preserved():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "zmAgentCycle($db);" in source
    assert "count($out)!==11" in source
    assert "$after-$before !== count($out)" in source
    assert 'echo "SITE_AGENTS_EXECUTED="' in source
    assert "SITE_AGENTS_FAILED=" in source
    assert "- name: Remove runner SSH credentials" in source
    assert "if: always()" in source

RELEASE_WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/zomorod-site-agent-100-stage-release.yml"
)


def test_v11_manual_monitor_requires_owner_and_main():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "github.event_name == 'workflow_dispatch'" in source
    assert "github.ref == 'refs/heads/main'" in source
    assert "github.actor == 'mojtabarozegar11-ship-it'" in source
    assert "github.repository == 'mojtabarozegar11-ship-it/Saeit'" in source


def test_v12_live_release_does_not_trigger_on_main_push():
    source = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    events = source.split("permissions:", 1)[0]
    assert "\n  workflow_dispatch:" in events
    assert "\n  push:" not in events
    assert "\n  schedule:" not in events
    assert "\n  pull_request:" not in events


def test_v12_live_release_requires_owner_manual_main_context():
    source = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert "github.event_name == 'workflow_dispatch'" in source
    assert "github.ref == 'refs/heads/main'" in source
    assert "github.actor == 'mojtabarozegar11-ship-it'" in source
    assert "github.repository == 'mojtabarozegar11-ship-it/Saeit'" in source


def test_v12_release_retains_backup_cron_receipt_and_rollback():
    source = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    backup = source.index("- name: Check exact Zomorod-only previous PHP source")
    deploy = source.index("- name: Deploy ONLY site agent PHP")
    receipt = source.index("- name: Verify real site-local evidence creation")
    rollback = source.index("- name: Automatic rollback after failed acceptance gate")
    assert backup < deploy < receipt < rollback
    assert "StrictHostKeyChecking yes" in source
    assert "ProxyJump saeit-vps" in source
    assert "*/10 * * * *" in source
    assert "crontab -l | grep -Fq" in source
    assert "crontab \"$backup/crontab.before.txt\"" in source
