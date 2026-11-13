"""Only a single reviewed trade email can use an owner grant.

All tests use isolated Django data. Any simulated send is explicitly mocked;
no SMTP, broker, payment, real email or deployment is invoked.
"""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from core.approval import ApprovalService
from core.autonomous_external_trade import (
    authorize_external_trade, execute_one_authorized_outbox,
)
from core.economic_trade_email import queue_trade_email, send_queued_trade_email
from core.models import ApprovalGrant, ApprovalRequest, AuditLog
from core.trade_approval_scope import trade_email_fingerprint

pytestmark = pytest.mark.django_db


@pytest.fixture
def queued_trade(db):
    owner = get_user_model().objects.create_user(
        username="outbox-review-owner", password="unused",
    )
    with override_settings(COMPANY_TRADE_EMAIL="company@example.test"):
        first = queue_trade_email(
            recipient="first@example.test", subject="First draft",
            body="Nonbinding draft one",
        )
        second = queue_trade_email(
            recipient="second@example.test", subject="Second draft",
            body="Nonbinding draft two",
        )
    first.mailbox.active = True
    first.mailbox.allow_outbound = True
    first.mailbox.save(update_fields=["active", "allow_outbound"])
    return owner, first, second


def _review(owner, outbox):
    request = authorize_external_trade(owner_id=owner.pk, outbox_id=outbox.pk)
    ApprovalService().decide(request.pk, True, actor_id=owner.pk)
    return request


def _grant(owner, outbox, approval):
    return ApprovalService().issue_grant(
        approval.pk, owner.pk,
        {"action": "external_write", "outbox_id": outbox.pk,
         "message_sha256": trade_email_fingerprint(outbox)},
    )


def test_missing_outbox_never_creates_general_email_approval(queued_trade):
    owner, _, _ = queued_trade
    before = ApprovalRequest.objects.count()
    for identifier in (None, 0, -1, "1", True):
        with pytest.raises(ValueError, match="outbox_id"):
            authorize_external_trade(owner_id=owner.pk, outbox_id=identifier)
    assert ApprovalRequest.objects.count() == before


def test_request_is_pending_and_exact_to_one_queued_message(queued_trade):
    owner, first, second = queued_trade
    request = authorize_external_trade(owner_id=owner.pk, outbox_id=second.pk)
    assert request.status == "pending"
    assert request.target_type == "TradeEmailOutbox"
    assert request.target_id == str(second.pk)
    assert request.grants.count() == 0
    assert first.status == second.status == "queued"


def test_owner_cannot_approve_mutated_recipient_or_body(queued_trade):
    owner, first, _ = queued_trade
    request = authorize_external_trade(owner_id=owner.pk, outbox_id=first.pk)
    first.recipient = "unexpected@example.test"
    first.body = "Unreviewed changed body"
    first.save(update_fields=["recipient", "body"])
    before = AuditLog.objects.count()
    with pytest.raises(ValueError, match="target or content has changed"):
        ApprovalService().decide(request.pk, True, actor_id=owner.pk)
    request.refresh_from_db()
    assert request.status == "pending"
    assert AuditLog.objects.count() == before


def test_grant_must_be_bound_to_reviewed_message_and_digest(queued_trade):
    owner, first, second = queued_trade
    approval = _review(owner, second)
    with pytest.raises(ValueError, match="outbox identity mismatch"):
        ApprovalService().issue_grant(
            approval.pk, owner.pk,
            {"action": "external_write", "outbox_id": first.pk,
             "message_sha256": trade_email_fingerprint(second)},
        )
    with pytest.raises(ValueError, match="message digest mismatch"):
        ApprovalService().issue_grant(
            approval.pk, owner.pk,
            {"action": "external_write", "outbox_id": second.pk,
             "message_sha256": trade_email_fingerprint(first)},
        )
    assert not ApprovalGrant.objects.filter(approval=approval).exists()


def test_mutation_after_approval_blocks_grant_issuance(queued_trade):
    owner, first, _ = queued_trade
    approval = _review(owner, first)
    first.subject = "Unreviewed new subject"
    first.save(update_fields=["subject"])
    with pytest.raises(ValueError, match="reviewed trade email changed"):
        _grant(owner, first, approval)


def test_mutation_after_grant_blocks_consumption_without_sending(queued_trade):
    owner, first, _ = queued_trade
    approval = _review(owner, first)
    grant = _grant(owner, first, approval)
    first.body = "Unreviewed changed content"
    first.save(update_fields=["body"])
    with override_settings(COMPANY_TRADE_EMAIL="company@example.test", TRADE_EMAIL_ENABLED=True), patch(
        "core.autonomous_external_trade.send_queued_trade_email"
    ) as sender:
        with pytest.raises(RuntimeError, match="REVIEWED_CONTENT_CHANGED"):
            execute_one_authorized_outbox(grant_id=grant.pk)
    sender.assert_not_called()
    grant.refresh_from_db()
    assert grant.used_at is None


def test_broad_mailbox_grant_does_not_authorize_any_email(queued_trade):
    owner, first, _ = queued_trade
    approval = ApprovalRequest.objects.create(
        action_type="external_write", target_type="TradeMailbox",
        target_id="company-trade", reason="Legacy blanket approval",
        risk="high", status="approved", requested_by=owner,
    )
    grant = ApprovalService().issue_grant(
        approval.pk, owner.pk,
        {"action": "external_write", "target": "company-trade"},
    )
    with patch("core.autonomous_external_trade.send_queued_trade_email") as sender:
        with pytest.raises(RuntimeError, match="EXACT_OUTBOX_APPROVAL_REQUIRED"):
            execute_one_authorized_outbox(grant_id=grant.pk)
    sender.assert_not_called()
    grant.refresh_from_db()
    assert grant.used_at is None
    assert first.status == "queued"


def test_disabled_sender_does_not_consume_grant_or_send(queued_trade):
    owner, first, _ = queued_trade
    approval = _review(owner, first)
    grant = _grant(owner, first, approval)
    with override_settings(TRADE_EMAIL_ENABLED=False), patch(
        "core.autonomous_external_trade.send_queued_trade_email"
    ) as sender:
        with pytest.raises(RuntimeError, match="disabled"):
            execute_one_authorized_outbox(grant_id=grant.pk)
    sender.assert_not_called()
    grant.refresh_from_db()
    assert grant.used_at is None


@pytest.mark.django_db(transaction=True)
def test_valid_owner_grant_selects_only_approved_message(queued_trade):
    owner, first, second = queued_trade
    approval = _review(owner, second)
    grant = _grant(owner, second, approval)
    # Patch Django SMTP only: exercise the real approval consumption, row
    # locking and outbox status update without sending a real message.
    with override_settings(
        COMPANY_TRADE_EMAIL="company@example.test",
        TRADE_EMAIL_ENABLED=True,
    ), patch("core.economic_trade_email.EmailMessage.send", return_value=1) as smtp:
        result = execute_one_authorized_outbox(grant_id=grant.pk)
    assert result.pk == second.pk
    assert result.status == "sent"
    smtp.assert_called_once()
    grant.refresh_from_db()
    assert grant.used_at is not None
    first.refresh_from_db()
    assert first.status == "queued"


def test_direct_sender_cannot_bypass_owner_approval(queued_trade):
    _, first, _ = queued_trade
    with override_settings(TRADE_EMAIL_ENABLED=True), patch(
        "core.economic_trade_email.EmailMessage.send", return_value=1,
    ) as smtp:
        with pytest.raises(RuntimeError, match="requires an exact owner grant"):
            send_queued_trade_email(first.pk)
    smtp.assert_not_called()
    first.refresh_from_db()
    assert first.status == "queued"


@pytest.mark.django_db(transaction=True)
def test_direct_sender_rejects_grant_issued_for_a_different_message(queued_trade):
    owner, first, second = queued_trade
    approval = _review(owner, second)
    grant = _grant(owner, second, approval)
    with override_settings(TRADE_EMAIL_ENABLED=True), patch(
        "core.economic_trade_email.EmailMessage.send", return_value=1,
    ) as smtp:
        with pytest.raises(RuntimeError, match="EXACT_OUTBOX_APPROVAL_REQUIRED"):
            send_queued_trade_email(first.pk, grant_id=grant.pk)
    smtp.assert_not_called()
    grant.refresh_from_db()
    assert grant.used_at is None
    first.refresh_from_db()
    assert first.status == "queued"

def test_nonqueued_message_cannot_be_sent_with_old_grant(queued_trade):
    owner, first, _ = queued_trade
    approval = _review(owner, first)
    grant = _grant(owner, first, approval)
    first.status = "sent"
    first.save(update_fields=["status"])
    with override_settings(TRADE_EMAIL_ENABLED=True), patch(
        "core.autonomous_external_trade.send_queued_trade_email"
    ) as sender:
        with pytest.raises(RuntimeError, match="REVIEWED_CONTENT_CHANGED"):
            execute_one_authorized_outbox(grant_id=grant.pk)
    sender.assert_not_called()
    grant.refresh_from_db()
    assert grant.used_at is None
