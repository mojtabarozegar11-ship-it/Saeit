#!/usr/bin/env python3
"""Evidence requirements, not self-certification, for a commercial sale.

Does not accept owner-supplied boolean claims as validated external receipts.
"""
from mojtaba_revenue_portfolio import CANONICAL_BOT, OFFERS

GATES = (
    ("source", "commit_ref_and_scope_diff"),
    ("test", "exact_head_ci_job_success"),
    ("live", "authenticated_domain_route_browser_and_inquiry_proof"),
    ("consent", "real_opt_in_inquiry_without_leaked_personal_data"),
    ("legal_collection", "owner_approved_eligible_payment_method_and_terms"),
    ("receipt", "independent_settled_payment_evidence"),
    ("delivery", "private_qc_passed_customer_access_and_receipt"),
)


def requirements(offer_id):
    if type(offer_id) is not str or offer_id not in OFFERS:
        raise ValueError("UNKNOWN_OFFER")
    return {
        "schema": "mojtaba.bot.ai.commercial-gates.v1",
        "canonical_bot": CANONICAL_BOT,
        "offer_id": offer_id,
        "source": OFFERS[offer_id].source,
        "gate_count": len(GATES),
        "gates": [
            {"id": name, "required_evidence": evidence, "status": "UNKNOWN"}
            for name, evidence in GATES
        ],
        "verified_gates": None,
        "commercial_ready": False,
        "claimed_revenue": None,
        "paid_orders": None,
        "proof_inspection_must_be_independent": True,
    }


def explain_ratio(numerator, denominator):
    if type(numerator) is not int or type(denominator) is not int:
        raise ValueError("BOOLEANS_ARE_NOT_COUNTS")
    if not 0 <= numerator <= denominator or denominator == 0:
        raise ValueError("INVALID_PROGRESS_DENOMINATOR")
    # This is a planning metric, never income or an audited customer metric.
    return {
        "numerator": numerator, "denominator": denominator,
        "percent": round(100 * numerator / denominator, 2),
        "source_gate_proof": False,
        "cash_receipt_proof": False,
    }
