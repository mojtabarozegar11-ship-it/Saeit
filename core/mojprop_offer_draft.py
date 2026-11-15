"""Generate non-binding, unsent service proposal drafts from real CRM leads.

No email sending, payment intent, signed contract or trade execution.
"""
from __future__ import annotations

import re

from .mojprop_catalog_contract import public_service_catalog


def _one_line(value: object) -> str:
    """Keep user-supplied contact fields from injecting forged proposal headers."""
    return re.sub(r"[\x00-\x1f\x7f\u2028\u2029]+", " ", str(value)).strip()


def _quoted_scope(text: str) -> str:
    """Show the customer's exact scope as quoted content, not operator instructions."""
    return "\n".join("> " + line for line in text.splitlines())


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
        f"Indicative starting amount: USD {service['indicative_from_usd']}; final quote NOT APPROVED.",
        "Deliverable sample: " + service["sample_url"],
        "Jurisdiction, taxes, precise scope, revisions and delivery date: require separate human confirmation.",
        "Payment: DISABLED until valid written offer and approved lawful receiver/checkout.",
        "No funded trading account, investment advice, automatic orders, promised profits or paid entitlement.",
        "Status: DRAFT ONLY. Do not mark offer_sent until a real written offer is dispatched and archived.",
    )) + "\n"
