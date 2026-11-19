"""Check the exact F41 release guard without a new runtime dependency."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/factory-f41-master-queue.yml"


def section(source, name, indent):
    # Fail closed on missing/duplicate sibling keys; check exact known format.
    prefix = " " * indent
    start = list(re.finditer(r"(?m)^" + prefix + re.escape(name) + r":(?:[ \t]*[^\n]*)?$", source))
    assert len(start) == 1, name
    tail = source[start[0].end():]
    sibling = re.search(r"(?m)^" + prefix + r"[A-Za-z_][\w-]*:", tail)
    return tail[:sibling.start()] if sibling else tail


def test_private_install_requires_separate_reviewed_owner_dispatch():
    source = WORKFLOW.read_text(encoding="utf-8")
    jobs = section(source, "jobs", 0)
    install = section(jobs, "private-vps-install", 2)
    condition = re.findall(r"(?m)^    if: >-\n((?:      [^\n]+\n)+)", install)
    assert len(condition) == 1
    expected = (
        "github.event_name == 'workflow_dispatch' && "
        "github.repository == 'mojtabarozegar11-ship-it/Saeit' && "
        "github.ref == 'refs/heads/main' && "
        "github.actor == 'mojtabarozegar11-ship-it' && "
        "inputs.owner_approved_private_install == true && "
        "inputs.expected_main_sha == github.sha"
    )
    assert " ".join(condition[0].split()) == expected
    assert len(re.findall(r"(?m)^    if:", install)) == 1
    dispatch = section(section(source, "on", 0), "workflow_dispatch", 2)
    inputs = section(dispatch, "inputs", 4)
    approved = section(inputs, "owner_approved_private_install", 6)
    sha = section(inputs, "expected_main_sha", 6)
    assert "        type: boolean\n" in approved
    assert "        default: false\n" in approved
    assert "        required: true\n" in sha
    assert "    needs: [private-quality]\n" in install


def test_source_only_checks_and_readonly_diagnostic_preserved():
    source = WORKFLOW.read_text(encoding="utf-8")
    events = section(source, "on", 0)
    push = section(events, "push", 2)
    pr = section(events, "pull_request", 2)
    assert "    branches: [main," in push
    assert "    branches: [main]\n" in pr
    assert "      - core/management/commands/seed_online_income_agents.py\n" in push
    jobs = section(source, "jobs", 0)
    quality = section(jobs, "private-quality", 2)
    assert not re.search(r"(?m)^    if:", quality)
    assert "secrets." not in quality
    diagnostic = section(jobs, "read-only-vps-preflight", 2)
    assert "    if: github.event_name == 'push' && github.ref == 'refs/heads/diagnostic/f41-queue-preflight-20261022'\n" in diagnostic
    assert "StrictHostKeyChecking=yes" in diagnostic
