"""Safety regression checks for the explicit, read-only cPanel SEO provenance relay."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "deploy" / "cpanel_direct_command.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "cpanel-direct-command-bridge.yml"
PROBE = ROOT / "scripts" / "mpw_search_readonly_provenance.py"


def test_seo_provenance_is_manual_only():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "  workflow_dispatch:" in workflow
    assert "          - seo_provenance\n" in workflow
    assert "permissions:\n  contents: read\n" in workflow
    for unexpected in ("  push:", "  pull_request:", "  issue_comment:", "  schedule:"):
        assert unexpected not in workflow


def test_command_uses_existing_pinned_readonly_relay():
    bridge = BRIDGE.read_text(encoding="utf-8")
    assert "django_migrations|seo_provenance) ;;" in bridge
    assert "StrictHostKeyChecking yes" in bridge
    assert "ProxyJump saeit-vps" in bridge
    assert "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs" in bridge
    assert "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04" in bridge
    assert "  seo_provenance)\n" in bridge
    block = bridge.split("  seo_provenance)\n", 1)[1].split("    ;;", 1)[0]
    assert 'test -r scripts/mpw_search_readonly_provenance.py' in block
    assert 'timeout 60s ssh -T -F "$work/config" saeit-cpanel' in block
    assert "PYTHONDONTWRITEBYTECODE=1" in block
    assert "Saeit-staging/3.11/bin/python -B -" in block
    assert "< scripts/mpw_search_readonly_provenance.py" in block
    for forbidden in ("rsync ", "scp ", "pip install", "manage.py", "chmod ", "chown ", " rm ", "sudo "):
        assert forbidden not in block


def test_unsupported_operation_stops_before_key_requirements():
    process = subprocess.run(
        ["bash", str(BRIDGE), "seo_provenance_unapproved"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert process.returncode == 64
    assert "CPANEL_DIRECT_OPERATION_DENIED" in process.stderr



def test_invalid_vps_key_reports_safe_failure_stage(tmp_path):
    env = os.environ.copy()
    env.update({
        "RUNNER_TEMP": str(tmp_path),
        "VPS_KEY": "invalid-private-key-for-readonly-regression",
        "HOST_KEY": "invalid-cpanel-key-for-readonly-regression",
    })
    process = subprocess.run(
        ["bash", str(BRIDGE), "seo_provenance"],
        env=env, check=False, capture_output=True, text=True, timeout=10,
    )
    assert process.returncode != 0
    assert "CPANEL_BRIDGE_FAILURE_STAGE=vps_private_key_validation" in process.stderr
    assert env["VPS_KEY"] not in process.stdout + process.stderr
    assert env["HOST_KEY"] not in process.stdout + process.stderr


def test_relay_stages_differentiate_host_key_and_remote_failures():
    bridge = BRIDGE.read_text(encoding="utf-8")
    for stage in (
        "vps_private_key_validation", "cpanel_private_key_validation",
        "vps_host_keyscan", "vps_host_fingerprint",
        "vps_to_cpanel_keyscan", "cpanel_host_fingerprint",
        "seo_provenance_local_source", "seo_provenance_remote_readonly",
    ):
        assert f'bridge_stage="{stage}"' in bridge
    assert "CPANEL_BRIDGE_FAILURE_STAGE=%s EXIT=%s" in bridge
    assert "trap report_bridge_error ERR" in bridge
    assert "set -Eeuo pipefail" in bridge


def test_probe_contains_no_live_mutation_or_network_calls():
    source = PROBE.read_text(encoding="utf-8")
    assert "read_only" in source
    assert "path.read_bytes()" in source
    for forbidden in (
        "subprocess.", "requests.", "urllib.request", "os.system(",
        ".write_bytes(", ".write_text(", ".unlink(", ".rename(",
        "os.remove(", "os.makedirs(", "os.chmod(",
    ):
        assert forbidden not in source
