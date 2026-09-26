"""Economic Master Agent — economic scientist and bounded autonomous operator.

The public surface is reporting-only. The private execution core is policy-first:
it may operate only through explicitly owned treasury/account adapters and only
inside a pre-authorized Economic Constitution. Credentials and balances never
belong in public reports or source code.
"""

AGENT_CODE = "economic-master-agent"
AGENT_TITLE = "Economic Master Agent"

REPORT_PIPELINE = (
    "RESEARCH",
    "SOURCES",
    "CLASSIFY",
    "ANALYZE",
    "SCENARIO",
    "FACT_CHECK",
    "REVIEW",
    "REPORT",
    "OWNER_APPROVAL",
    "PUBLISH",
)

ECONOMIC_DOMAINS = (
    "Iran Economy",
    "Global Economy",
    "Agriculture & Food Economy",
    "Industry & Production",
    "Trade & Supply Chains",
    "Energy & Resources",
    "Technology & Digital Economy",
    "Financial Systems & Markets",
    "Policy & Regulation",
    "Geopolitical Economic Risk",
)

AUTONOMOUS_ACTIONS = frozenset({
    "research", "classify", "analyze", "scenario", "fact_check",
    "report", "rebalance", "buy", "sell", "trade", "payment",
    "transfer_funds", "place_order", "settle", "reconcile",
})

FORBIDDEN_EXECUTION = frozenset({
    "open_account", "borrow", "lend", "external_write",
    "use_third_party_account", "use_unowned_funds", "disable_risk_controls",
    "bypass_constitution", "bypass_audit", "withdraw_owner_funds",
})

ECONOMIC_CONSTITUTION = {
    "treasury_scope": "owned_accounts_only",
    "third_party_funds": False,
    "pre_trade_risk_check": True,
    "post_trade_reconciliation": True,
    "audit_every_action": True,
    "duplicate_order_protection": True,
    "liquidity_reserve_required": True,
    "emergency_kill_switch": True,
    "out_of_policy_requires_owner_approval": True,
    "public_execution_details": False,
}

PUBLIC_REPORT_RULES = (
    "report_only",
    "no_public_numeric_financial_figures",
    "source_required",
    "fact_analysis_separation",
    "uncertainty_explicit",
    "no_fabricated_sources",
    "owner_approval_before_publish",
    "full_audit_trace",
)

class EconomicMasterAgent:
    """Policy-first economic intelligence orchestrator."""

    code = AGENT_CODE
    title = AGENT_TITLE
    domains = ECONOMIC_DOMAINS
    pipeline = REPORT_PIPELINE
    public_rules = PUBLIC_REPORT_RULES

    def can_execute(self, action):
        """Allow only non-transactional intelligence actions until execution adapters are explicitly enabled."""
        action = str(action or "").strip().lower()
        intelligence_actions = {
            "research", "classify", "analyze", "scenario", "fact_check", "report",
        }
        return action in intelligence_actions and action not in FORBIDDEN_EXECUTION

    def allowed_capabilities(self):
        return (
            "economic_research",
            "source_collection",
            "economic_classification",
            "comparative_analysis",
            "scenario_analysis",
            "risk_mapping",
            "fact_checking",
            "report_drafting",
            "report_quality_review",
            "owner_approval_request",
        )

    def report_contract(self):
        return {
            "agent": self.code,
            "mode": "research_and_reporting",
            "domains": list(self.domains),
            "pipeline": list(self.pipeline),
            "public_rules": list(self.public_rules),
            "execution": "non_transactional",
        }

    def trade_email_contract(self):
        return {
            "channel": "company_trade_mailbox",
            "purpose": "international_trade_correspondence",
            "outbox_first": True,
            "idempotency": True,
            "audit": True,
            "real_send_default": False,
            "owner_approval_for_binding_commitments": True,
        }

    def system_architecture(self):
        return {
            "orchestrator": "Economic Master Agent",
            "workers": [
                "Iran Economy Worker", "Global Economy Worker",
                "Agriculture Worker", "Industry Worker",
                "Trade & Supply Chain Worker", "Energy Worker",
                "Technology Economy Worker", "Policy Worker",
                "Risk & Scenario Worker", "Fact Check Worker",
                "Report Editor Worker", "International Trade Worker",
                "China Trade Worker", "Country Trade Workers",
                "Trade Compliance Worker", "Trade Correspondence Worker",
            ],
            "governance": [
                "Source provenance", "Evidence ledger",
                "Fact/analysis separation", "Uncertainty gate",
                "Owner approval", "Audit trail",
            ],
            "trade_email": self.trade_email_contract(),
            "hard_stop": sorted(FORBIDDEN_EXECUTION),
        }


def economic_agent_contract():
    return EconomicMasterAgent().report_contract()


def economic_agent_architecture():
    return EconomicMasterAgent().system_architecture()


def sanitize_public_report(text):
    """Keep the public layer narrative; numeric values are not a publish target."""
    return str(text or "").strip()
