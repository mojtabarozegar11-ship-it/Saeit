"""General Manager operating policy for Zomorod Melal agentic business system.

This module defines the mandatory business lifecycle and evidence gates.  It is
intentionally dependency-free so orchestration code can import it safely.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Tuple


class BusinessStage(str, Enum):
    RESEARCH = "research"
    VALIDATION = "validation"
    MVP = "mvp"
    ACQUISITION = "acquisition"
    ORDER = "order"
    PAYMENT = "payment"
    DELIVERY = "delivery"
    PROFITABILITY = "profitability"
    SCALE = "scale"


@dataclass(frozen=True)
class StageGate:
    required_evidence: Tuple[str, ...]
    owner_approval: bool = False


GATES: Dict[BusinessStage, StageGate] = {
    BusinessStage.RESEARCH: StageGate(("customer_problem", "market_evidence", "competitor_evidence")),
    BusinessStage.VALIDATION: StageGate(("offer", "price_test", "real_demand_signal")),
    BusinessStage.MVP: StageGate(("working_offer", "delivery_process", "cost_estimate")),
    BusinessStage.ACQUISITION: StageGate(("real_visitor_or_lead", "channel_attribution")),
    BusinessStage.ORDER: StageGate(("customer_identity_or_session", "order_id", "order_value")),
    BusinessStage.PAYMENT: StageGate(("payment_reference", "amount_received", "settlement_status")),
    BusinessStage.DELIVERY: StageGate(("delivery_evidence", "customer_outcome")),
    BusinessStage.PROFITABILITY: StageGate(("collected_cash", "direct_cost", "net_contribution")),
    BusinessStage.SCALE: StageGate(("repeatable_collected_cash", "positive_unit_economics", "risk_review"), owner_approval=True),
}

# Sensitive actions are never autonomous.
OWNER_APPROVAL_ACTIONS = frozenset({
    "spend_money", "withdraw_money", "change_payment_destination",
    "sign_contract", "identity_verification", "publish_legal_commitment",
    "delete_financial_records", "scale_budget",
})

# Economic success is deliberately strict: impressions, leads and even orders
# are funnel metrics, not revenue.
ECONOMIC_SUCCESS_METRIC = "verified_collected_cash"

GENERAL_MANAGER_DUTIES = (
    "set measurable mission and collected-cash target",
    "delegate research and require source/evidence traceability",
    "discover and deduplicate legal online revenue opportunities",
    "validate customer, market, competitor, channel, price, cost and risk",
    "rank experiments by evidence, cost, reversibility and time-to-cash",
    "run the smallest viable experiment before scaling",
    "build and verify MVP and delivery workflow",
    "acquire real users/leads and measure conversion",
    "verify order, payment settlement and delivered value independently",
    "calculate unit economics from collected cash rather than projections",
    "diagnose failed stages and repair/retry or stop them",
    "scale only repeatable profitable flows after required approval",
    "maintain audit trail, KPIs, security, legal and financial controls",
    "continuously learn from experiments without rewriting historical evidence",
)


def can_advance(stage: BusinessStage, evidence: Dict[str, object], owner_approved: bool = False):
    """Return (allowed, missing) for a stage gate."""
    gate = GATES[stage]
    missing = tuple(key for key in gate.required_evidence if not evidence.get(key))
    if gate.owner_approval and not owner_approved:
        missing += ("owner_approval",)
    return not missing, missing


def requires_owner_approval(action: str) -> bool:
    return action in OWNER_APPROVAL_ACTIONS


def economic_success(evidence: Dict[str, object]) -> bool:
    """Success only when settled/collected money is independently evidenced."""
    try:
        amount = float(evidence.get("amount_received", 0) or 0)
    except (TypeError, ValueError):
        return False
    return bool(
        amount > 0
        and evidence.get("payment_reference")
        and evidence.get("settlement_status") in {"settled", "collected"}
    )
