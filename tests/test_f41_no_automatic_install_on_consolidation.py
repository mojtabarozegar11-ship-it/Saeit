"""Prevent a source-only single-bot merge from installing F41 on the VPS."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/factory-f41-master-queue.yml"


def config():
    return yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_private_install_requires_separate_reviewed_owner_dispatch():
    data = config()
    install = data["jobs"]["private-vps-install"]
    expected = (
        "github.event_name == 'workflow_dispatch' && "
        "github.repository == 'mojtabarozegar11-ship-it/Saeit' && "
        "github.ref == 'refs/heads/main' && "
        "github.actor == 'mojtabarozegar11-ship-it' && "
        "inputs.owner_approved_private_install == true && "
        "inputs.expected_main_sha == github.sha"
    )
    assert " ".join(install["if"].split()) == expected
    inputs = data["on"]["workflow_dispatch"]["inputs"]
    assert inputs["owner_approved_private_install"]["type"] == "boolean"
    assert inputs["owner_approved_private_install"]["default"] == "false"
    assert inputs["expected_main_sha"]["required"] == "true"
    assert install["needs"] == ["private-quality"]


def test_source_only_checks_and_readonly_diagnostic_preserved():
    data = config()
    assert "main" in data["on"]["push"]["branches"]
    assert "main" in data["on"]["pull_request"]["branches"]
    assert "core/management/commands/seed_online_income_agents.py" in data["on"]["push"]["paths"]
    quality = data["jobs"]["private-quality"]
    assert "if" not in quality
    assert "secrets." not in str(quality)
    diag = data["jobs"]["read-only-vps-preflight"]
    assert diag["if"] == "github.event_name == 'push' && github.ref == 'refs/heads/diagnostic/f41-queue-preflight-20261022'"
    assert "StrictHostKeyChecking=yes" in str(diag)
