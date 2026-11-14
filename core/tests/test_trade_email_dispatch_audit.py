"""Read-only triage of external email delivery uncertainty; no SMTP calls."""
import json
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from core.economic_trade_models import TradeEmailAudit, TradeEmailOutbox, TradeMailbox

pytestmark = pytest.mark.django_db


@pytest.fixture
def trade_mailbox(db):
    return TradeMailbox.objects.create(
        code="company-trade", display_name="Private trade mailbox",
        email_address="internal@example.test", active=False, allow_outbound=False,
    )


def _outbox(mailbox, *, status, token):
    return TradeEmailOutbox.objects.create(
        mailbox=mailbox, idempotency_key=token, status=status,
        recipient=f"{token}@private.example.test",
        subject=f"Private subject {token}", body=f"Confidential body {token}",
    )


def _audit(*, limit=50, stale_after=900):
    stream = StringIO()
    call_command("audit_trade_email_dispatch", limit=limit,
                 stale_after=stale_after, stdout=stream)
    return json.loads(stream.getvalue())


def test_empty_queue_yields_zero_without_side_effects(db):
    with patch("core.economic_trade_email.EmailMessage.send") as smtp:
        data = _audit()
    smtp.assert_not_called()
    assert data["unresolved_total"] == 0
    assert data["items"] == []
    assert data["send_performed"] is False
    assert data["automated_retry_allowed"] is False


def test_dispatching_and_delivery_unknown_are_listed_without_private_data(trade_mailbox):
    pending = _outbox(trade_mailbox, status="dispatching", token="sensitive123")
    uncertain = _outbox(trade_mailbox, status="delivery_unknown", token="secret567")
    safe = _outbox(trade_mailbox, status="sent", token="secret-sent")
    TradeEmailAudit.objects.create(outbox=pending, action="dispatch_reserved", trace_id="private-test-1")
    age = timezone.now() - timedelta(minutes=61)
    TradeEmailOutbox.objects.filter(pk=pending.pk).update(updated_at=age)
    count = TradeEmailAudit.objects.count()
    with patch("core.economic_trade_email.EmailMessage.send") as smtp:
        data = _audit()
    smtp.assert_not_called()
    assert data["counts"] == {"dispatching": 1, "delivery_unknown": 1}
    assert data["unresolved_total"] == 2
    assert data["returned_count"] == 2
    assert safe.pk not in [r["outbox_id"] for r in data["items"]]
    row = next(x for x in data["items"] if x["outbox_id"] == pending.pk)
    assert row["stale_dispatch"] is True
    assert row["dispatch_reservation_recorded"] is True
    assert data["owner_approval_consumed"] is False
    assert TradeEmailAudit.objects.count() == count
    # A read-only operator report must not disclose mailbox PII or content.
    report = json.dumps(data)
    for forbidden in ["sensitive123", "secret567", "private.example.test",
                      "Confidential", "Private subject", "internal@example.test"]:
        assert forbidden not in report
    assert TradeEmailOutbox.objects.get(pk=pending.pk).status == "dispatching"


def test_recent_dispatch_is_not_false_stale(trade_mailbox):
    _outbox(trade_mailbox, status="dispatching", token="recent")
    row = _audit(stale_after=900)["items"][0]
    assert row["status"] == "dispatching"
    assert row["stale_dispatch"] is False
    assert row["requires_manual_reconciliation"] is True


def test_limit_is_honored_without_losing_total_counts(trade_mailbox):
    for i in range(3):
        _outbox(trade_mailbox, status="delivery_unknown", token=f"item-{i}")
    data = _audit(limit=1)
    assert data["unresolved_total"] == 3
    assert data["returned_count"] == 1
    assert data["truncated"] is True
    assert data["automated_retry_allowed"] is False


@pytest.mark.parametrize("limit,stale_after", [(0, 900), (101, 900), (5, 59), (5, 86401)])
def test_invalid_audit_limits_are_rejected(limit, stale_after, db):
    with pytest.raises(CommandError):
        _audit(limit=limit, stale_after=stale_after)


def test_other_mailbox_not_confused_with_company_trade(trade_mailbox):
    another = TradeMailbox.objects.create(
        code="unrelated-mailbox", display_name="Unrelated",
        email_address="unrelated@example.test",
    )
    _outbox(another, status="dispatching", token="unrelated")
    _outbox(trade_mailbox, status="sent", token="sent")
    data = _audit()
    assert data["unresolved_total"] == 0
