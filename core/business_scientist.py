"""Virtual chief economist and business-science operating role.

This role applies evidence-based management to the connected business records.
It proposes a measurable next experiment; it does not invent credentials or
exercise financial, legal, publication, or production-release authority.
"""
from typing import Mapping

from core.business_management import review_business


BUSINESS_SCIENTIST_PROFILE = {
    "code": "business-scientist-professor",
    "title": "Virtual Chief Economist and Business Scientist",
    "mandate": (
        "Improve verified customer outcomes and sustainable contribution "
        "across Zomorod Melal and MojPlayWin by diagnosing constraints, "
        "testing growth hypotheses, and learning from measured results."
    ),
    "disciplines": [
        "strategy and competitive positioning",
        "customer discovery and demand validation",
        "marketing and sales conversion",
        "product and service design",
        "production quality and delivery",
        "finance and unit economics",
        "technology and operating reliability",
        "people, roles, and incentives",
        "risk, security, and compliance",
        "measurement and organizational learning",
    ],
    "authority": {
        "automatic": "read-only analysis and reversible internal diagnostics",
        "approval_required": (
            "spend, payments, contracts, personal data use, production release, "
            "external publication, irreversible changes, legal or regulated decisions"
        ),
    },
}


def build_business_science_plan(metrics: Mapping[str, dict]) -> dict:
    """Return one evidence-linked next experiment and explicit scale gates."""
    review = review_business(metrics)
    findings = review["findings"]
    lead = findings[0] if findings else None

    if lead:
        experiment = {
            "constraint": lead["code"],
            "department": lead["department"],
            "hypothesis": (
                f"Resolving the observed constraint '{lead['code']}' will improve "
                "a verified customer outcome or sustainable contribution."
            ),
            "first_action": lead["action"],
            "primary_measure": _measure_for(lead["department"]),
            "baseline": "unknown_until_a_timestamped_baseline_is_connected",
            "decision_rule": (
                "Compare a dated baseline with a dated post-action result; "
                "retain the change only when the primary measure improves "
                "without breaching its guardrail."
            ),
            "guardrail": _guardrail_for(lead["department"]),
            "execution": lead["execution"],
        }
    else:
        experiment = {
            "constraint": None,
            "department": "portfolio",
            "hypothesis": "No open constraint is visible in the connected metrics.",
            "first_action": "Refresh source timestamps and test data completeness.",
            "primary_measure": "freshness_and_completeness_of_authoritative_sources",
            "baseline": "unknown",
            "decision_rule": "Do not declare the business healthy from missing findings.",
            "guardrail": "Keep external and financial actions gated.",
            "execution": "autonomous_diagnostic",
        }

    return {
        "role": BUSINESS_SCIENTIST_PROFILE,
        "method": [
            "observe",
            "distinguish facts from unknowns",
            "rank the binding constraint",
            "state a falsifiable hypothesis",
            "run only an authorized bounded experiment",
            "measure and compare",
            "retain, repair, or roll back",
            "replan",
        ],
        "portfolio_growth_gates": [
            {"gate": "customer_problem", "pass_when": "A named buyer and repeated costly problem have attributable evidence."},
            {"gate": "willingness_to_pay", "pass_when": "A real paid test or documented buyer commitment supports the offer."},
            {"gate": "reliable_delivery", "pass_when": "An independent user can complete the promised outcome and delivery is reproducible."},
            {"gate": "positive_unit_economics", "pass_when": "Settled cash less refunds, provider fees, and attributable fulfillment costs is positive, by currency."},
            {"gate": "repeatable_acquisition", "pass_when": "A measured acquisition channel produces customers within an observed contribution limit."},
            {"gate": "controlled_expansion", "pass_when": "Prior gates remain true at a small increase in volume and rollback is tested."},
        ],
        "next_experiment": experiment,
        "do_not_scale": [
            "unknown or stale primary measures",
            "unverified revenue or simulated orders",
            "unaccepted factory outputs",
            "negative or unreconciled unit economics",
            "a checkout, security, or delivery failure",
            "an unresolved approval or legal requirement",
        ],
        "evidence_gaps": review["unknown_metrics"],
        "review": review,
    }


def _measure_for(department: str) -> str:
    return {
        "operations": "median_age_and_verified_completion_rate_by_stage",
        "strategy": "independent_demand_signals_for_a_named_buyer_problem",
        "sales": "verified_checkout_to_fulfillment_conversion",
        "finance": "reconciled_net_contribution_by_currency",
        "factory": "independent_acceptance_rate_and_repair_rate",
        "technology": "timestamped_site_availability_and_successful_customer_journey",
        "governance": "approved_decisions_completed_within_scope_and_expiry",
    }.get(department, "verified_customer_outcome_and_net_contribution")


def _guardrail_for(department: str) -> str:
    common = "No unapproved spend, external publication, or irreversible action."
    if department == "finance":
        return common + " Never count orders or intents as settled cash."
    if department in {"factory", "technology", "operations"}:
        return common + " Preserve backups, idempotency, and tested rollback."
    if department == "strategy":
        return common + " Keep source, sample, date, and uncertainty visible."
    return common
