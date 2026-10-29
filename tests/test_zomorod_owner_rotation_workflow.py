"""Static safeguards for the one-use protected GitHub -> VPS -> cPanel action."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/zomorod-owner-sealed-rotation.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")


def test_owner_issue_number_and_exact_author_gate():
    assert "github.event.issue.number == 1600" in TEXT
    assert "github.event.comment.user.login == 'mojtabarozegar11-ship-it'" in TEXT
    assert "github.event.comment.author_association == 'OWNER'" in TEXT
    assert "github.ref == 'refs/heads/main'" in TEXT
    assert "event.get('action')!='created'" in TEXT
    assert "issue.get('pull_request')" in TEXT


def test_only_authenticated_pinned_30gb_hosts():
    assert "HostName 178.239.147.150" in TEXT
    assert "HostName 178.239.147.125" in TEXT
    assert "Port 1396" in TEXT
    assert "ProxyJump saeit-vps" in TEXT
    assert "StrictHostKeyChecking yes" in TEXT
    assert "PINNED_30GB_RELAY_AUTHENTICATED_ON_ATTEMPT" in TEXT
    assert 'test "$(id -un)" = "zomorod2"' in TEXT
    assert "UserKnownHostsFile $d/host.known" in TEXT


def test_never_store_password_in_repo_action_or_logs():
    assert "zomorod-owner-encrypted.txt" in TEXT
    assert "OWNER_OPERATION_SECRET=NEVER_LOGGED" in TEXT
    assert "OWNER_CREDENTIAL_ROTATION=SUCCESS" not in TEXT
    assert "secrets.VPS_SSH_PRIVATE_KEY" in TEXT
    assert "secrets.SAEIT_HOST_SSH_PRIVATE_KEY" in TEXT
    assert "set -x" not in TEXT
    assert "echo " + "$" + "{{ github.event.comment.body }}" not in TEXT


def test_private_only_and_exact_workflow_trigger():
    assert "on:\n  push:" in TEXT
    assert "issue_comment:\n    types: [created]" in TEXT
    assert "github.event_name == 'issue_comment'" in TEXT
    assert "ZMR-OWNER-ROTATE-INSPECT-V1" in TEXT
    assert "ZMR-OWNER-ROTATE-V1" in TEXT
    assert "/home/zomorod2/.private/zomorod-business/.owner-rotation-tools" in TEXT
    assert "chmod 600" in TEXT
    assert "python3 -B '$p' rotate" in TEXT
    assert "rm -rf" in TEXT


def test_checks_run_before_protected_remote_action():
    assert "needs: offline-safety" in TEXT
    assert "python3 scripts/test_zomorod_owner_password_rotate.py" in TEXT
    assert "tests/test_zomorod_owner_sealed_rotate.py" in TEXT
    assert "tests/test_zomorod_owner_rotation_workflow.py" in TEXT
    assert "NO_LIVE_CREDENTIAL_TESTED=TRUE" in TEXT
