"""The existing factory VPS cPanel command bridge must not return false green."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "deploy/cpanel_direct_command.sh"
WORKFLOW = ROOT / ".github/workflows/cpanel-direct-command-bridge.yml"


def test_selfhosted_migration_operation_actually_runs_showmigrations():
    src = BRIDGE.read_text()
    local = src.split('if [[ "${FACTORY_VPS_RUNNER:-0}" == "1" ]]; then', 1)[1]
    local = local.split("  exit 0\nfi", 1)[0]
    assert "    django_migrations)" in local
    assert "CPANEL_DJANGO_MIGRATIONS=READ_ONLY_PLAN" in local
    assert "manage.py showmigrations --plan" in local


def test_migration_operation_must_never_apply_migrations():
    src = BRIDGE.read_text()
    assert "manage.py migrate " not in src
    assert "manage.py makemigrations" not in src
    assert src.count("manage.py showmigrations --plan") >= 2


def test_factory_bridge_still_requires_manual_owner_main():
    src = WORKFLOW.read_text()
    assert "workflow_dispatch:" in src
    assert "github.ref == 'refs/heads/main'" in src
    assert "runs-on: [self-hosted, factory-vps]" in src
    assert "\n  push:" not in src
    assert "\n  pull_request:" not in src
