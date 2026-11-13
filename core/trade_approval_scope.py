"""Exact, immutable review scope for a single proposed trade email.

A mailbox-level approval cannot authorize arbitrary queued recipients.
All checks are read-only and do not send or enqueue external messages.
"""
import hashlib
import json

from .services import normalize_action


def trade_email_fingerprint(outbox):
    payload = {
        "outbox_id": outbox.pk,
        "mailbox_id": outbox.mailbox_id,
        "mailbox_code": outbox.mailbox.code,
        "sender": outbox.mailbox.email_address,
        "recipient": outbox.recipient,
        "subject": outbox.subject,
        "body": outbox.body,
        "context": outbox.trade_context,
        "idempotency_key": outbox.idempotency_key,
    }
    stable = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                        separators=(",", ":"), default=str)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def exact_trade_email_reason(outbox):
    return (
        f"Owner review of one queued company-trade email: "
        f"outbox={outbox.pk}; recipient={outbox.recipient}; "
        f"subject={outbox.subject!r}; sha256={trade_email_fingerprint(outbox)}"
    )


def trade_email_approval_matches(approval, outbox):
    return bool(
        outbox is not None
        and approval.target_type == "TradeEmailOutbox"
        and approval.target_id == str(outbox.pk)
        and normalize_action(approval.action_type) == "external_write"
        and outbox.status == "queued"
        and outbox.mailbox.code == "company-trade"
        and approval.reason == exact_trade_email_reason(outbox)
    )
