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
