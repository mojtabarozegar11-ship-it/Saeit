"""Generate non-binding, unsent service proposal drafts from real CRM leads.

No email sending, payment intent, signed contract or trade execution.
"""
from __future__ import annotations

import re

from .mojprop_catalog_contract import public_service_catalog


def _normalise_line_breaks(value: object) -> str:
    """Treat literal and actual line breaks consistently before rendering user text."""
    return str(value).replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")


def _one_line(value: object) -> str:
    """Keep user-supplied contact fields from injecting forged proposal headers."""
    text = _normalise_line_breaks(value)
    return re.sub(r"[\x00-\x1f\x7f\u2028\u2029]+", " ", text).strip()


def _quoted_scope(text: str) -> str:
    """Show the customer's exact scope as quoted content, not operator instructions."""
    normalised = _normalise_line_breaks(text)
    normalised = re.sub(r"[\x00-\x08\x0b-\x1f\x7f\u2028\u2029]", " ", normalised)
    return "\n".join(
        "> " + line.strip() for line in normalised.splitlines() if line.strip()
    )


_SIGNAL_PLAN_LINE = re.compile(
    r"Requested educational plan: (education-(?:weekly|monthly|quarterly)) "
    r"\(indicative USD ([0-9]{1,5}\.[0-9]{2}); written quote required\)\Z"
)


def _signal_draft_price_line(details: str) -> str:
    """Never turn a buyer-authored plan line into an approved subscription price.

    The public intake carries the plan only inside customer notes. An exact,
    catalog-matching first line may be shown as an unverified preference;
    malformed or price-tampered attributions cannot produce a proposal draft.
    Without a selected plan, do not falsely quote the generic service price
    (USD 29) for a weekly USD 9.90 educational brief.
    """
    from services.mojtaba_signal_catalog import get_signal_plan

    first_line = details.splitlines()[0].strip()
    if not first_line.startswith("Requested educational plan:"):
        return (
            "Educational signal plan: NOT SELECTED; obtain an explicit buyer "
            "preference and confirm the current catalog before quoting any amount."
        )
    match = _SIGNAL_PLAN_LINE.fullmatch(first_line)
    if match is None:
        raise ValueError("invalid_customer_signal_plan_attribution")
    plan = get_signal_plan(match.group(1))
    exact_amount = format(plan.price_usd, "f")
    if match.group(2) != exact_amount:
        raise ValueError("signal_plan_price_does_not_match_authoritative_catalog")
    return (
        f"Buyer-requested plan (NOT independently verified): {plan.plan_id}; "
        f"catalog reference USD {exact_amount}; "
        "written price, term and delivery require independent owner approval. "
        "NOT AN INVOICE OR SUBSCRIPTION."
    )


def build_offer_draft(lead) -> str:
    """Render a traceable customer-specific written-scope draft; never charge."""
    if not lead.pk or lead.status != "reviewing" or lead.consent is not True:
        raise ValueError("real_consent_and_operator_review_required")
    offers = {item["route"]: item for item in public_service_catalog()}
    service = offers.get(lead.route)
    if service is None:
        raise ValueError("unknown_customer_service")
    if not lead.request_id.startswith("MOJPROP-"):
        raise ValueError("unverified_lead_reference")
    details = str(lead.notes).strip()
    if len(details) < 20:
        raise ValueError("scope_missing")
    if not lead.email or not lead.name:
        raise ValueError("customer_contact_missing")
    pricing_line = (
        _signal_draft_price_line(details) if lead.route == "signals"
        else f"Indicative starting amount: USD {service['indicative_from_usd']}; final quote NOT APPROVED."
    )
    return "\n".join((
        "MOJ PROP / MOJTABA.BOT.AI — UNSENT COMMERCIAL OFFER DRAFT",
        "NOT A CONTRACT — NOT AN INVOICE — OWNER APPROVAL REQUIRED",
        f"Customer request reference: {lead.request_id}",
        f"Customer: {_one_line(lead.name)}",
        f"Contact email (not yet messaged): {_one_line(lead.email)}",
        f"Requested service: {service['title']}",
        f"Requested timing: {lead.get_horizon_display()}",
        "Client objective / scope supplied:",
        _quoted_scope(details),
        "",
        "Proposed work: written analysis/service deliverable to be scoped and reviewed.",
        pricing_line,
        "Deliverable sample: " + service["sample_url"],
        "Jurisdiction, taxes, precise scope, revisions and delivery date: require separate human confirmation.",
        "Payment: DISABLED until valid written offer and approved lawful receiver/checkout.",
        "No funded trading account, investment advice, automatic orders, promised profits or paid entitlement.",
        "Status: DRAFT ONLY. Do not mark offer_sent until a real written offer is dispatched and archived.",
    )) + "\n"
