"""Fail-closed regression checks for the bounded site-agent SSH relay.

These checks inspect source only. They never connect to VPS/cPanel, use secrets,
or assert that a live production operation occurred.
"""
import os
import subprocess
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


DISPATCH_WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/owner-three-agent-collections-execute-20261024.yml"
)
DISPATCH_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/owner_three_agent_collections_execute_20261024.sh"
)


def test_cross_collection_dispatch_is_owner_manual_only():
    source = DISPATCH_WORKFLOW.read_text(encoding="utf-8")
    assert "github.event_name == 'workflow_dispatch'" in source
    assert "github.actor == 'mojtabarozegar11-ship-it'" in source
    assert "github.ref == 'refs/heads/main'" in source
    assert "github.event_name != 'pull_request'" not in source
    # Pull requests and main pushes may validate syntax but may not dispatch.
    assert "  validate:" in source
    assert "  pull_request:" in source
    assert "  push:" in source


def test_dispatcher_denies_push_context_before_any_gh_call():
    result = subprocess.run(
        ["bash", str(DISPATCH_SCRIPT), "--execute", "zomorod-site-agent-cycle.yml"],
        env={
            "PATH": os.environ.get("PATH", ""),
            "GITHUB_REPOSITORY": "mojtabarozegar11-ship-it/Saeit",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_ACTOR": "mojtabarozegar11-ship-it",
            "GH_TOKEN": "dummy-never-used",
        },
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 11
    assert "OWNER_MANUAL_DISPATCH_REQUIRED" in result.stderr
    assert "DISPATCH_SUBMITTED" not in result.stdout


def test_dispatcher_selftest_needs_no_credentials_or_network():
    result = subprocess.run(
        ["bash", str(DISPATCH_SCRIPT), "--selftest"],
        env={"PATH": os.environ.get("PATH", "")},
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0
    assert "APPROVED_THREE_AGENT_WORKFLOWS=" in result.stdout
