"""Immutable, private consent-claim and content-digest checks for one trade email.

A syntactically valid consent evidence hash is NOT independent proof of consent.
Actual legal basis and provider delivery require separate verification.
"""
from __future__ import annotations

import hashlib
import json
import re

EVIDENCE_SHA = re.compile(r"[a-f0-9]{64}\Z")
ALLOWED_BASES = frozenset({"consented_inquiry", "requested_quote", "existing_customer"})


def message_digest(outbox) -> str:
    """Bind the exact message, sender, recipient, mailbox and context."""
    context = getattr(outbox, "trade_context", None)
    if type(context) is not dict:
        raise ValueError("OUTBOX_CONTEXT_INVALID")
    mailbox = getattr(outbox, "mailbox", None)
    fields = (
        getattr(mailbox, "code", None),
        getattr(mailbox, "email_address", None),
        getattr(outbox, "recipient", None),
        getattr(outbox, "subject", None),
        getattr(outbox, "body", None),
        getattr(outbox, "idempotency_key", None),
    )
    if any(type(value) is not str or not value.strip() for value in fields):
        raise ValueError("OUTBOX_CONTENT_INVALID")
    if len(fields[2]) > 254 or len(fields[3]) > 300 or len(fields[4]) > 10000:
        raise ValueError("OUTBOX_CONTENT_TOO_LONG")
    payload = {"fields": fields, "trade_context": context}
    try:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (ValueError, TypeError) as exc:
        raise ValueError("OUTBOX_CONTEXT_UNSERIALIZABLE") from exc
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_outbox_for_owner_grant(outbox, scope) -> str:
    """Reject unbound/unsupported/changed message before granting authority."""
    if type(scope) is not dict or set(scope) != {"action", "outbox_id", "message_digest"}:
        raise ValueError("OUTBOX_SCOPE_INVALID")
    if scope["action"] != "external_write":
        raise ValueError("OUTBOX_ACTION_INVALID")
    if type(getattr(outbox, "pk", None)) is not int or outbox.pk < 1:
        raise ValueError("OUTBOX_ID_INVALID")
    if type(scope["outbox_id"]) is not int or scope["outbox_id"] != outbox.pk:
        raise ValueError("OUTBOX_SCOPE_ID_MISMATCH")
    if getattr(outbox, "status", None) != "queued":
        raise ValueError("OUTBOX_NOT_QUEUED")
    mailbox = getattr(outbox, "mailbox", None)
    if (
        getattr(mailbox, "code", None) != "company-trade"
        or getattr(mailbox, "active", None) is not True
        or getattr(mailbox, "allow_outbound", None) is not True
        or getattr(mailbox, "require_policy_gate", None) is not True
    ):
        raise ValueError("OUTBOX_MAILBOX_POLICY_INACTIVE")
    context = outbox.trade_context
    if type(context) is not dict or set(context) != {
        "contact_basis", "basis_evidence_sha256"
    }:
        raise ValueError("OUTBOX_CONTACT_BASIS_NOT_ATTESTED")
    if context.get("contact_basis") not in ALLOWED_BASES:
        raise ValueError("OUTBOX_CONTACT_BASIS_NOT_ALLOWLISTED")
    evidence = context.get("basis_evidence_sha256")
    if (
        type(evidence) is not str
        or EVIDENCE_SHA.fullmatch(evidence) is None
        or evidence == "0" * 64
    ):
        raise ValueError("OUTBOX_CONTACT_EVIDENCE_INVALID")
    digest = message_digest(outbox)
    if (
        type(scope["message_digest"]) is not str
        or EVIDENCE_SHA.fullmatch(scope["message_digest"]) is None
        or scope["message_digest"] != digest
    ):
        raise ValueError("OUTBOX_MESSAGE_CHANGED")
    return digest
