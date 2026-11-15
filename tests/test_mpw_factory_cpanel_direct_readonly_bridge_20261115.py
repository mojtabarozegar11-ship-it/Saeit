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
    observed = observed.split("      - name: Audit current MojPlayWin", 1)[0]
    assert "if: github.event_name == 'workflow_dispatch'" in manual
    assert 'bash deploy/cpanel_direct_command.sh "${{ inputs.operation }}"' in manual
    assert "if: >-" in observed
    assert "github.event_name == 'issue_comment'" in observed
    assert "github.event.comment.body == 'MPW-FACTORY-CPANEL-READONLY-20261115'" in observed
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
    assert _blob_sha(BRIDGE) == "e9614221871614981e4974760217093b58fa0a3f"
    assert _blob_sha(SANITIZER) == "89a3ca61cf3919dd397b5cb2dd36194273f6ee98"
    assert _blob_sha(BRIDGE) in raw
    assert _blob_sha(SANITIZER) in raw
    parser = SANITIZER.read_text(encoding="utf-8")
    assert "secrets_or_full_app_root_paths_printed" in parser
    assert '"release_permitted": False' in parser
    assert '"production_isolation_proven": False' in parser


def test_second_exact_owner_marker_is_scoped_to_readonly_runtime():
    raw = WORKFLOW.read_text(encoding="utf-8")
    marker = "MPW-FACTORY-CPANEL-RUNTIME-READONLY-20261115"
    assert raw.count("github.event.comment.body == '" + marker + "'") == 2
    runtime_step = raw.split("      - name: Audit current MojPlayWin Passenger", 1)[1]
    assert "if: >-" in runtime_step
    assert "github.event_name == 'issue_comment'" in runtime_step
    assert "github.event.comment.body == '" + marker + "'" in runtime_step
    assert "FACTORY_VPS_RUNNER: \"1\"" in runtime_step
    assert "timeout 130s bash deploy/cpanel_direct_command.sh mpw_runtime_readonly" in runtime_step
    assert "0e4d22460ee62ebf9f89c94a6fecf6f9a14531c2" in runtime_step
    for forbidden in ("sudo ", "rsync ", "scp ", "curl -X POST", "restart.txt", "manage.py migrate", "send_mail"):
        assert forbidden not in runtime_step


def test_new_runtime_helper_never_accepts_public_runner_or_unreviewed_script():
    bridge = BRIDGE.read_text(encoding="utf-8")
    source = ROOT / "scripts/mpw_public_passenger_runtime_readonly_20261102.py"
    assert _blob_sha(source) == "0e4d22460ee62ebf9f89c94a6fecf6f9a14531c2"
    assert "mpw_runtime_readonly)" in bridge
    assert '"$operation" == "mpw_runtime_readonly"' in bridge
    assert '"$operation" == "mpw_backup_readiness_readonly"' in bridge
    assert 'FACTORY_VPS_RUNNER:-0' in bridge
    assert "MPW_RUNTIME_REQUIRES_LOCAL_FACTORY_VPS" in bridge
    assert 'test "$(git hash-object -- "$script")"' in bridge
    assert 'PYTHONDONTWRITEBYTECODE=1' in bridge
    assert 'python -B - inspect' in bridge
    assert '"release_permitted": False' in source.read_text(encoding="utf-8")


def test_backup_capacity_owner_marker_is_bounded_and_no_write():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    marker = "MPW-FACTORY-BACKUP-READINESS-READONLY-20261115"
    assert workflow.count("github.event.comment.body == '" + marker + "'") == 2
    header = workflow.split("\npermissions:", 1)[0]
    assert "  issue_comment:\n    types: [created]" in header
    assert "  workflow_dispatch:" in header
    for forbidden in ("\n  push:", "\n  schedule:", "\n  pull_request:"):
        assert forbidden not in header
    step = workflow.split("      - name: Audit scoped cPanel backup prerequisites", 1)[1]
    assert "github.event_name == 'issue_comment'" in step
    assert "github.event.comment.body == '" + marker + "'" in step
    assert 'FACTORY_VPS_RUNNER: "1"' in step
    assert "bash deploy/cpanel_direct_command.sh mpw_backup_readiness_readonly" in step
    assert "python3 -B scripts/mojplaywin_isolated_restore_capabilities_readonly.py" in step
    for forbidden in ("sudo ", "scp ", "rsync ", "tar -xf", "pip install", "docker run",
                      "mariadb-install-db ", "manage.py migrate", "restart.txt", "curl -X POST",
                      "send_mail", "chmod ", "chown "):
        assert forbidden not in step


def test_backup_readiness_script_and_vps_capability_are_source_pinned():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    helper = BRIDGE.read_text(encoding="utf-8")
    backup = ROOT / "scripts/mojplaywin_backup_restore_readiness_readonly.py"
    capability = ROOT / "scripts/mojplaywin_isolated_restore_capabilities_readonly.py"
    assert _blob_sha(backup) == "9fe37626a0d58ae7f2ab8fb4a9206342e997a6be"
    assert _blob_sha(capability) == "70dcf0fabd4c581a41c6d01438c25faaa75df6bd"
    assert _blob_sha(backup) in workflow and _blob_sha(backup) in helper
    assert _blob_sha(capability) in workflow
    assert _blob_sha(BRIDGE) == "e9614221871614981e4974760217093b58fa0a3f"
    assert _blob_sha(BRIDGE) in workflow
    assert "mpw_backup_readiness_readonly)" in helper
    assert '"$operation" == "mpw_backup_readiness_readonly"' in helper
    assert 'FACTORY_VPS_RUNNER:-0' in helper
    assert 'PYTHONDONTWRITEBYTECODE=1' in helper
    assert 'python -B -' in helper
    assert '"release_permitted": False' in backup.read_text()
    assert '"isolated_restore_performed":False' in capability.read_text()
