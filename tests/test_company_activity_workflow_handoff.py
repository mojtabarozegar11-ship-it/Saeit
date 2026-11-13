"""Source-contract guard for the site's canonical-agent handoff boundary.

This checks the checked-in workflow's exact status-code handling. End-to-end
remote deployment and production scheduler behavior still require live evidence.
"""
from pathlib import Path


def test_known_handoff_blockers_do_not_starve_knowledge_cycle():
    workflow = Path(".github/workflows/zomorod-site-agent-cycle.yml").read_text(
        encoding="utf-8"
    )
    conditional = 'if activity_output="$("$python_path" manage.py company_activity_agent_cycle 2>&1)"; then'
    assert conditional in workflow
    assert "MOJTABA_CANONICAL_AGENT_NOT_PROVISIONED" in workflow
    assert "COMPANY_ACTIVITY_LEGACY_HANDOFF_REQUIRED" in workflow
    assert "SITE_AGENT_COMPANY_MODULE=blocked_pending_single_bot_handoff" in workflow
    knowledge = 'queue_output="$("$python_path" manage.py knowledge_agent_cycle)"'
    assert knowledge in workflow
    assert workflow.index(conditional) < workflow.index(knowledge)
    assert "SITE_AGENT_COMPANY_MODULE=unexpected_error" in workflow
