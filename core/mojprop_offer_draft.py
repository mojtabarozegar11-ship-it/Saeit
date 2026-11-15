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


_SIGNAL_REQUEST_LINE = re.compile(
    r"Requested educational plan: (education-(?:weekly|monthly|quarterly)) "
    r"\(indicative USD ([0-9]{1,5}\.[0-9]{2}); written quote required\)\Z"
)


def _signal_price_note(lead, generic_start: int) -> str:
    """Infer *nonbinding* buyer scope from text, never approve an invoice."""
    # The public intake currently persists only a notes field, not a trusted
    # paid-plan foreign key. Treat these strings as buyer claims, not evidence.
    from services.mojtaba_signal_catalog import PLANS

    notes = _normalise_line_breaks(lead.notes)
    first_line = notes.splitlines()[0].strip() if notes.splitlines() else ""
    free_requested = (
        notes.startswith("Requested free educational example:")
        or notes.startswith("One-off FREE educational market-brief example request")
        or notes.startswith("Please provide a FREE historical educational example")
    )
    matched = [
        code for code in PLANS
        if re.search(r"(?<![a-z0-9-])" + re.escape(code) + r"(?![a-z0-9-])", notes)
    ]
    if free_requested and matched:
        return "Price WITHHELD: conflicting free/paid identifiers; operator must clarify scope."
    if free_requested:
        return (
            "FREE educational example requested; no price quoted, automatic "
            "free entitlement, or delivery promised. Manual review required."
        )
    if len(matched) > 1:
        return "Price WITHHELD: multiple educational plan identifiers; operator must clarify."
    # The leading, structured line is customer-supplied, not trusted pricing
    # authority. A contradictory plan ID or quoted amount must stop a draft.
    if first_line.startswith("Requested educational plan:"):
        match = _SIGNAL_REQUEST_LINE.fullmatch(first_line)
        if (match is None or len(matched) != 1 or matched[0] != match.group(1)
                or match.group(2) != format(PLANS[matched[0]].price_usd, ".2f")):
            return (
                "Price WITHHELD: inconsistent customer plan or amount; "
                "review the buyer's request against the official catalog."
            )
    if len(matched) == 1:
        code = matched[0]
        plan = PLANS[code]
        return (
            f"Buyer-selected plan: {code}; indicative catalog amount USD "
            f"{plan.price_usd:.2f}; final quote NOT APPROVED. "
            "Plan identity must be confirmed before invoicing."
        )
    return (
        "Price WITHHELD: no specific educational signal plan selected; "
        "confirm the customer's intended plan before proposing a price."
    )


def _starter30_selection(lead) -> str:
    """Classify buyer-claimed SKU scope; never grant a paid entitlement.

    The customer controls the notes string. An exact frontend-generated prefix
    makes the intended manual SKU recognizable for operator triage, but does
    NOT authenticate the SKU, price, signature, payment or authorization.
    """
    if lead.route != "blueprint":
        return "none"
    notes = str(lead.notes)
    code = "MOJPROP-STARTER30"
    if notes.startswith("Requested canonical product: " + code + " ("):
        return "buyer_claim"
    if code in notes:
        return "ambiguous"
    return "none"


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
    starter_selection = _starter30_selection(lead)
    if len(details) < 20:
        raise ValueError("scope_missing")
    if not lead.email or not lead.name:
        raise ValueError("customer_contact_missing")
    return "\n".join((
        "MOJ PROP / MOJTABA.BOT.AI — UNSENT COMMERCIAL OFFER DRAFT",
        "NOT A CONTRACT — NOT AN INVOICE — OWNER APPROVAL REQUIRED",
        f"Customer request reference: {lead.request_id}",
        f"Customer: {_one_line(lead.name)}",
        f"Contact email (not yet messaged): {_one_line(lead.email)}",
        ("Requested service: Moj Prop Starter 30 (buyer-claimed, NOT approved)"
         if starter_selection == "buyer_claim"
         else f"Requested service: {service['title']}"),
        f"Requested timing: {lead.get_horizon_display()}",
        "Client objective / scope supplied:",
        _quoted_scope(details),
        "",
        "Proposed work: written analysis/service deliverable to be scoped and reviewed.",
        (_signal_price_note(lead, service["indicative_from_usd"]) if lead.route == "signals"
         else ("Requested Starter30 reference: 30 native TRX INDICATIVE; price WITHHELD, "
               "not a payable quote; legal terms, buyer contract and merchant custody unverified."
               if starter_selection == "buyer_claim"
               else ("Price WITHHELD: ambiguous Starter30 identifier in a generic Blueprint inquiry; "
                     "operator must clarify, never substitute the USD 149 blueprint tariff."
                     if starter_selection == "ambiguous"
                     else f"Indicative starting amount: USD {service['indicative_from_usd']}; final quote NOT APPROVED."))),
        ("Reference material: 10-session simulated journal and scorecard; live publication UNVERIFIED."
         if starter_selection != "none"
         else "Deliverable sample: " + service["sample_url"]),
        "Jurisdiction, taxes, precise scope, revisions and delivery date: require separate human confirmation.",
        "Payment: DISABLED until valid written offer and approved lawful receiver/checkout.",
        "No funded trading account, investment advice, automatic orders, promised profits or paid entitlement.",
        "Status: DRAFT ONLY. Do not mark offer_sent until a real written offer is dispatched and archived.",
    )) + "\n"
