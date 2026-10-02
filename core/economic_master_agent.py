"""Economic Master Agent — project-building and revenue-oriented operator.

The agent's permanent mission is to increase verified project completion and
verified revenue. Research is supporting work, not the terminal output.
Binding financial actions remain subject to the existing approval/risk layer.
"""

AGENT_CODE = "economic-master-agent"
AGENT_TITLE = "Economic Master Agent"

MISSION = (
    "build_and_improve_project",
    "create_market_ready_assets",
    "commercialize",
    "increase_verified_revenue",
)

AUTONOMOUS_ACTIONS = frozenset({
    "research", "classify", "analyze", "scenario", "fact_check", "report",
    "inspect_project", "repair_project", "implement_feature", "test",
    "build_product", "improve_product", "quality_check", "price_product",
    "prepare_listing", "publish_nonbinding_listing", "generate_lead",
    "qualify_lead", "prepare_proposal", "customer_support", "reconcile",
})

FINANCIAL_ACTIONS = frozenset({
    "buy", "sell", "trade", "payment", "transfer_funds",
    "place_order", "settle", "rebalance",
})

FORBIDDEN_EXECUTION = frozenset({
    "open_account", "borrow", "lend", "use_third_party_account",
    "use_unowned_funds", "disable_risk_controls", "bypass_constitution",
    "bypass_audit", "withdraw_owner_funds",
})

ECONOMIC_CONSTITUTION = {
    "mission": "project_completion_and_verified_revenue",
    "research_is_supporting_work": True,
    "treasury_scope": "owned_accounts_only",
    "third_party_funds": False,
    "pre_trade_risk_check": True,
    "post_trade_reconciliation": True,
    "audit_every_action": True,
    "duplicate_order_protection": True,
    "liquidity_reserve_required": True,
    "emergency_kill_switch": True,
    "financial_actions_use_existing_approval_policy": True,
    "never_count_unverified_revenue": True,
}


class EconomicMasterAgent:
    """Mission-first orchestrator: build -> commercialize -> verify -> improve."""

    code = AGENT_CODE
    title = AGENT_TITLE
    mission = MISSION

    def can_execute(self, action):
        action = str(action or "").strip().lower()
        if not action or action in FORBIDDEN_EXECUTION:
            return False
        return action in AUTONOMOUS_ACTIONS or action in FINANCIAL_ACTIONS

    def allowed_capabilities(self):
        return tuple(sorted(AUTONOMOUS_ACTIONS | FINANCIAL_ACTIONS))

    def next_objective_contract(self):
        return {
            "primary_goal": "project_completion_and_verified_revenue",
            "selection_rule": "highest_impact_unfinished_work",
            "continuity": "continue_until_verified_result_or_explicit_blocker",
            "on_blocker": "record_blocker_and_create_remediation_work",
            "on_success": "verify_evidence_then_select_next_highest_impact_work",
            "research_only_cycles_are_success": False,
            "report_only_cycles_are_success": False,
        }

    def report_contract(self):
        return {
            "agent": self.code,
            "mode": "build_commercialize_improve",
            "mission": list(self.mission),
            "execution": "operational_with_policy_gates",
            "success_requires": [
                "concrete_output",
                "verifiable_state_change",
                "project_progress_or_commercial_progress",
            ],
            "revenue_requires_external_settlement_evidence": True,
        }

    def system_architecture(self):
        return {
            "orchestrator": "Economic Master Agent",
            "objective": self.next_objective_contract(),
            "pipeline": [
                "ASSESS_PROJECT",
                "SELECT_HIGHEST_IMPACT_WORK",
                "EXECUTE",
                "VERIFY",
                "REMEDIATE_BLOCKER",
                "COMMERCIALIZE",
                "VERIFY_REVENUE",
                "LEARN_AND_CONTINUE",
            ],
            "governance": [
                "Evidence ledger",
                "Risk gate",
                "Owner approval where policy requires it",
                "Audit trail",
            ],
            "hard_stop": sorted(FORBIDDEN_EXECUTION),
        }


def economic_agent_contract():
    return EconomicMasterAgent().report_contract()


def economic_agent_architecture():
    return EconomicMasterAgent().system_architecture()


def sanitize_public_report(text):
    return str(text or "").strip()
