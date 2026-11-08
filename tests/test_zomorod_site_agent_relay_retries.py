"""Fail-closed regression checks for the bounded site-agent SSH relay.

These checks inspect source only. They never connect to VPS/cPanel, use secrets,
or assert that a live production operation occurred.
"""
from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/zomorod-site-agent-cycle.yml"
)


def test_transient_retries_have_separate_bounded_diagnostics():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert source.count("for attempt in 1 2 3; do") == 2
    assert "SITE_AGENT_RELAY=VPS_HOST_KEY_UNREACHABLE" in source
    assert "SITE_AGENT_RELAY=VPS_TO_CPANEL_UNREACHABLE_OR_UNAUTHENTICATED" in source
    assert 'timeout 28s ssh -F "$d/config" saeit-vps' in source
    assert 'if test "$attempt" -lt 3; then sleep 2; fi' in source


def test_host_identity_and_secret_protections_remain_fail_closed():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "SITE_AGENT_RELAY=VPS_HOST_KEY_MISMATCH" in source
    assert "SITE_AGENT_RELAY=CPANEL_HOST_KEY_MISMATCH" in source
    assert "StrictHostKeyChecking yes" in source
    assert "IdentitiesOnly yes" in source
    assert "ProxyJump saeit-vps" in source
    assert "ForwardAgent no" in source
    assert "StrictHostKeyChecking no" not in source
    assert "ssh-keygen -lf" in source
    assert "|| true" in source  # Never relax fingerprint comparison.


def test_agent_stages_cannot_run_before_verified_relay():
    source = WORKFLOW.read_text(encoding="utf-8")
    prepare = source.index("- name: Prepare the pinned cPanel relay")
    sentinel = source.index('echo "PINNED_CPANEL_RELAY=verified"')
    verify = source.index("- name: Verify the exact Zomorod app and runtime")
    cycle = source.index("- name: Run one bounded, approval-gated site cycle")
    assert prepare < sentinel < verify < cycle


def test_blocked_relay_requires_explicit_manual_dispatch():
    source = WORKFLOW.read_text(encoding="utf-8")
    events = source.split("permissions:", 1)[0]
    assert "  workflow_dispatch:" in events
    assert "  schedule:" not in events
    assert "  push:" not in events
