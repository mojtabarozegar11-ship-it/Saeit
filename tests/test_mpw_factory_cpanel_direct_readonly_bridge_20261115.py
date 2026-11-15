"""Regression contract for the owner's existing factory-VPS to cPanel route.

Source-only checks. Never open SSH, touch production services, send messages,
create invoices, make payments, or run a deployment from CI.
"""
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/cpanel-direct-command-bridge.yml"
BRIDGE = ROOT / "deploy/cpanel_direct_command.sh"
SANITIZER = ROOT / "scripts/mojplaywin_cpanel_readonly_inventory.py"
OWNER = "mojtabarozegar11-ship-it"
ISSUE_MARKER = "MPW-FACTORY-CPANEL-READONLY-20261115"


def _blob_sha(path):
    payload = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(payload)).encode("ascii") + bytes([0]) + payload).hexdigest()


def test_owner_only_existing_issue_dispatch_no_push_or_pr():
    raw = WORKFLOW.read_text(encoding="utf-8")
    header = raw.split("\npermissions:", 1)[0]
    assert "  workflow_dispatch:" in header
    assert "  issue_comment:\n    types: [created]" in header
    for forbidden in ("\n  push:", "\n  pull_request:", "\n  schedule:", "\n  repository_dispatch:"):
        assert forbidden not in header
    assert "permissions:\n  contents: read" in raw
    assert "runs-on: [self-hosted, factory-vps]" in raw
    for required in (
        "github.repository == 'mojtabarozegar11-ship-it/Saeit'",
        "github.ref == 'refs/heads/main'",
        "github.event_name == 'issue_comment'",
        "github.actor == '" + OWNER + "'",
        "github.event.issue.number == 1600",
        "!github.event.issue.pull_request",
        "github.event.comment.user.login == '" + OWNER + "'",
        "github.event.comment.author_association == 'OWNER'",
        "github.event.comment.body == '" + ISSUE_MARKER + "'",
    ):
        assert required in raw, required


def test_issue_comment_never_reaches_untrusted_manual_operation():
    raw = WORKFLOW.read_text(encoding="utf-8")
    manual = raw.split("      - name: Execute selected read-only cPanel operation", 1)[1]
    manual = manual.split("      - name: Inspect existing cPanel", 1)[0]
    observed = raw.split("      - name: Inspect existing cPanel", 1)[1]
    assert "if: github.event_name == 'workflow_dispatch'" in manual
    assert 'bash deploy/cpanel_direct_command.sh "${{ inputs.operation }}"' in manual
    assert "if: github.event_name == 'issue_comment'" in observed
    assert "inputs.operation" not in observed
    assert "FACTORY_VPS_RUNNER: \"1\"" in observed
    assert "persist-credentials: false" in raw


def test_live_observation_is_only_pinned_existing_readonly_allowlist():
    raw = WORKFLOW.read_text(encoding="utf-8")
    observed = raw.split("      - name: Inspect existing cPanel", 1)[1]
    for name in ("relay_preflight", "passenger_inventory"):
        assert "timeout 95s bash deploy/cpanel_direct_command.sh " + name in observed
        assert name in BRIDGE.read_text(encoding="utf-8")
    assert "bash deploy/cpanel_direct_command.sh relay_preflight" in observed
    assert "bash deploy/cpanel_direct_command.sh passenger_inventory" in observed
    assert "bash deploy/cpanel_direct_command.sh django_migrations" not in observed
    assert "bash deploy/cpanel_direct_command.sh django_check" not in observed
    for unsafe in ("sudo ", "chmod ", "chown ", "curl -X POST", "scp ", "rsync ", "restart.txt", "migrate", "collectstatic", "payment", "send_mail"):
        assert unsafe not in observed
    assert 'test "$(git hash-object -- deploy/cpanel_direct_command.sh)"' in observed
    assert 'test "$(git hash-object -- scripts/mojplaywin_cpanel_readonly_inventory.py)"' in observed


def test_reviewed_bridge_and_inventory_outputs_are_immutably_pinned():
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert _blob_sha(BRIDGE) == "1f01a2408e82101b1321a7cd682fe6714508586b"
    assert _blob_sha(SANITIZER) == "89a3ca61cf3919dd397b5cb2dd36194273f6ee98"
    assert _blob_sha(BRIDGE) in raw
    assert _blob_sha(SANITIZER) in raw
    parser = SANITIZER.read_text(encoding="utf-8")
    assert "secrets_or_full_app_root_paths_printed" in parser
    assert '"release_permitted": False' in parser
    assert '"production_isolation_proven": False' in parser
