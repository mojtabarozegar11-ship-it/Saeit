"""Static safety contract for the single-bot consolidation gate.

The test is intentionally fail-closed: it protects the boundary until live
host inventory and owner-approved handoff receipts exist.
"""

import json
from pathlib import Path


REPO = Path(__file__).parents[1]
MANIFEST = REPO / "runtime" / "mojtaba_bot_disposition_sources_v1.json"
WORKFLOW = REPO / ".github" / "workflows" / "mojtaba-live-topology-readonly.yml"


def test_only_canonical_bot_identity_is_allowed():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["canonical_bot_id"] == "mojtaba.bot.ai"
    gates = data["completion_gates"]
    assert gates["unique_public_bot_identity"] == "mojtaba.bot.ai"


def test_live_consolidation_cannot_be_claimed_without_evidence():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    gates = data["completion_gates"]
    assert gates["external_process_inventory_attested"] is False
    assert gates["handoffs_verified"] is False
    assert gates["duplicated_executors_retired"] is False
    assert gates["irreversible_deletion_authorized"] is False
    assert gates["legacy_retirement_performed"] is False
    assert gates["legacy_deletion_performed"] is False


def test_topology_workflow_is_manual_read_only_and_non_destructive():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "workflow_call:" in workflow
    assert "schedule:" not in workflow
    assert "push:" not in workflow
    assert "pull_request:" not in workflow
    assert "automatic_deactivation_authorized" in workflow
    assert "retirement_authorized" in workflow
    assert "permissions:\n  contents: read" in workflow
