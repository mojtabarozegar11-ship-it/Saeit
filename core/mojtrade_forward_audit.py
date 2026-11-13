"""Sole Mojtaba.bot.ai runtime's bounded, read-only forward watch audit."""
from __future__ import annotations

import os
from django.db.models import F

from .canonical_bot_identity import RUNTIME_CODES, resolve_single_active_agent
from .models import Agent, AgentTask
from .mojtrade_forward_metrics import MAX_HISTORY, assess_reviewed_history, ForwardEvidenceError


def master_forward_audit(payload):
    if os.getenv("MOJ_FACTORY_LOCAL_MODE") != "1":
        raise ForwardEvidenceError("MODEL_PRIVATE_MASTER_RUNTIME_ONLY")
    if not isinstance(payload, dict) or payload:
        # No caller-supplied prices, paths, fee overrides, orders or accounts.
        raise ForwardEvidenceError("MODEL_NO_CALLER_CONTROLLED_EVIDENCE")
    # Require exactly one active runtime, but keep historical completed receipts
    # from the inactive legacy identity after an evidenced canonical handoff.
    if resolve_single_active_agent(Agent) is None:
        raise ForwardEvidenceError("MODEL_ACTIVE_MASTER_REQUIRED")
    rows = list(AgentTask.objects.filter(
        agent__code__in=RUNTIME_CODES,
        status="completed",
        action_type="income_mojtrade_research_review",
        capability_code=F("action_type"),
        output_data__verified_effect=True,
    ).order_by("-updated_at", "-pk")[:MAX_HISTORY])
    history = []
    for row in rows:
        output = row.output_data
        evidence = output.get("evidence") if isinstance(output, dict) else None
        if not isinstance(evidence, dict) or evidence.get("kind") != "mojtrade_private_research_review":
            raise ForwardEvidenceError("MODEL_REVIEW_AUDIT_EVIDENCE_INVALID")
        history.append({
            "reviewed_at": row.updated_at.isoformat(),
            "review": evidence.get("value"),
        })
    report = assess_reviewed_history(history)
    return {
        "action_performed": (
            "Reconciled bounded archived master research reviews against later "
            "closed-hour USD reference closes using disclosed hypothetical costs."
        ),
        "verified_effect": True,  # Verified internal review, NOT market/financial success.
        "evidence": {"kind": "mojtrade_forward_research_model", "value": report},
        "research_only": True,
        "performance_verified": False,
        "verified_revenue": None,
        "orders": 0,
        "execution": "disabled",
        "publication_enabled": False,
        "next_action": "await_independently_attested_market_outcomes",
    }
