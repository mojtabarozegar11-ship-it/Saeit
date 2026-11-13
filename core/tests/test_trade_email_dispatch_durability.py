"""Durable SMTP dispatch: no automatic second attempt after uncertain delivery.

Tests use a transactional, isolated Django database. Django's EmailMessage
transport is always mocked; no actual email, payment or external call occurs.
"""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import override_settings

from core.approval import ApprovalService
from core.autonomous_external_trade import authorize_external_trade, execute_one_authorized_outbox
from core.economic_trade_email import send_queued_trade_email, queue_trade_email
from core.economic_trade_models import TradeEmailAudit, TradeEmailOutbox
from core.models import AuditLog, ApprovalGrant
from core.trade_approval_scope import trade_email_fingerprint

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def ready_email(transactional_db):
    owner = get_user_model().objects.create_user(username="smtp-durable-owner")
    with override_settings(COMPANY_TRADE_EMAIL="company@example.test"):
        outbox = queue_trade_email(
            recipient="customer@example.test", subject="Nonbinding draft",
            body="Owner-reviewed, test-only trade message",
        )
    outbox.mailbox.active = True
    outbox.mailbox.allow_outbound = True
    outbox.mailbox.save(update_fields=["active", "allow_outbound"])
    request = authorize_external_trade(owner_id=owner.pk, outbox_id=outbox.pk)
    ApprovalService().decide(request.pk, True, actor_id=owner.pk)
    grant = ApprovalService().issue_grant(
        request.pk, owner.pk, {
            "action": "external_write", "outbox_id": outbox.pk,
            "message_sha256": trade_email_fingerprint(outbox),
        },
    )
    return outbox, grant


@override_settings(TRADE_EMAIL_ENABLED=True)
def test_dispatch_reservation_and_permission_are_recorded_before_smtp(ready_email):
    outbox, grant = ready_email
    observations = []

    def smtp_is_mocked(self, *, fail_silently=False):
        item = TradeEmailOutbox.objects.get(pk=outbox.pk)
        token = ApprovalGrant.objects.get(pk=grant.pk)
        observations.append((
            item.status, token.used_at is not None,
            TradeEmailAudit.objects.filter(outbox=item, action="dispatch_reserved").count(),
        ))
        return 1

    with patch("core.economic_trade_email.EmailMessage.send", new=smtp_is_mocked):
        result = send_queued_trade_email(outbox.pk, grant_id=grant.pk)
    assert observations == [("dispatching", True, 1)]
    assert result.status == "sent"
    with patch("core.economic_trade_email.EmailMessage.send") as smtp:
        with pytest.raises(RuntimeError, match="not queued"):
            send_queued_trade_email(outbox.pk, grant_id=grant.pk)
    smtp.assert_not_called()


@override_settings(TRADE_EMAIL_ENABLED=True)
def test_provider_exception_does_not_roll_back_one_shot_reservation(ready_email):
    outbox, grant = ready_email
    with patch(
        "core.economic_trade_email.EmailMessage.send",
        side_effect=OSError("ambiguous SMTP transport result"),
    ) as smtp:
        with pytest.raises(RuntimeError, match="DELIVERY_UNKNOWN_RECONCILE_REQUIRED"):
            send_queued_trade_email(outbox.pk, grant_id=grant.pk)
    smtp.assert_called_once()
    outbox.refresh_from_db()
    grant.refresh_from_db()
    assert outbox.status == "delivery_unknown"
    assert grant.used_at is not None
    assert TradeEmailAudit.objects.filter(outbox=outbox, action="dispatch_reserved").count() == 1
    assert TradeEmailAudit.objects.filter(outbox=outbox, action="delivery_unknown").count() == 1
    with patch("core.economic_trade_email.EmailMessage.send") as smtp_again:
        with pytest.raises(RuntimeError, match="not queued"):
            send_queued_trade_email(outbox.pk, grant_id=grant.pk)
    smtp_again.assert_not_called()


@override_settings(TRADE_EMAIL_ENABLED=True, COMPANY_TRADE_EMAIL="company@example.test")
def test_zero_provider_confirmation_is_not_reported_as_sent(ready_email):
    outbox, grant = ready_email
    with patch("core.economic_trade_email.EmailMessage.send", return_value=0):
        result = execute_one_authorized_outbox(grant_id=grant.pk)
    assert result.status == "delivery_unknown"
    assert not AuditLog.objects.filter(
        action="external_trade_email_sent", target_id=str(outbox.pk),
    ).exists()
    assert AuditLog.objects.filter(
        action="external_trade_email_delivery_unknown",
        target_id=str(outbox.pk),
    ).exists()


@override_settings(TRADE_EMAIL_ENABLED=True)
def test_failure_to_finalize_after_smtp_keeps_non_retryable_dispatch_marker(ready_email):
    outbox, grant = ready_email
    with patch("core.economic_trade_email.EmailMessage.send", return_value=1) as smtp, patch(
        "core.economic_trade_email._finalize_dispatch",
        side_effect=RuntimeError("Simulated post-SMTP DB failure"),
    ):
        with pytest.raises(RuntimeError, match="Simulated post-SMTP"):
            send_queued_trade_email(outbox.pk, grant_id=grant.pk)
    smtp.assert_called_once()
    outbox.refresh_from_db()
    grant.refresh_from_db()
    assert outbox.status == "dispatching"
    assert grant.used_at is not None
    with patch("core.economic_trade_email.EmailMessage.send") as no_second_send:
        with pytest.raises(RuntimeError, match="not queued"):
            send_queued_trade_email(outbox.pk, grant_id=grant.pk)
    no_second_send.assert_not_called()


@override_settings(TRADE_EMAIL_ENABLED=True)
def test_external_transaction_refused_before_consuming_owner_grant(ready_email):
    outbox, grant = ready_email
    with patch("core.economic_trade_email.EmailMessage.send") as smtp:
        with transaction.atomic():
            with pytest.raises(RuntimeError, match="REQUIRES_NO_OUTER_TRANSACTION"):
                send_queued_trade_email(outbox.pk, grant_id=grant.pk)
    smtp.assert_not_called()
    grant.refresh_from_db()
    outbox.refresh_from_db()
    assert grant.used_at is None and outbox.status == "queued"


@override_settings(TRADE_EMAIL_ENABLED=True)
def test_provider_ambiguous_return_stays_unknown_and_never_requeues(ready_email):
    outbox, grant = ready_email
    with patch("core.economic_trade_email.EmailMessage.send", return_value=2):
        result = send_queued_trade_email(outbox.pk, grant_id=grant.pk)
    assert result.status == "delivery_unknown"
    assert ApprovalGrant.objects.get(pk=grant.pk).used_at is not None
    assert TradeEmailOutbox.objects.get(pk=outbox.pk).status == "delivery_unknown"

@override_settings(TRADE_EMAIL_ENABLED=True, COMPANY_TRADE_EMAIL="")
def test_bridge_requires_configured_sender_and_preserves_one_shot_grant(ready_email):
    outbox, grant = ready_email
    with patch("core.economic_trade_email.EmailMessage.send") as smtp:
        with pytest.raises(RuntimeError, match="not configured"):
            execute_one_authorized_outbox(grant_id=grant.pk)
    smtp.assert_not_called()
    grant.refresh_from_db()
    outbox.refresh_from_db()
    assert grant.used_at is None
    assert outbox.status == "queued"


@override_settings(TRADE_EMAIL_ENABLED=True, COMPANY_TRADE_EMAIL="company@example.test")
def test_bridge_requires_active_mailbox_and_does_not_consume_grant(ready_email):
    outbox, grant = ready_email
    outbox.mailbox.allow_outbound = False
    outbox.mailbox.save(update_fields=["allow_outbound"])
    with patch("core.economic_trade_email.EmailMessage.send") as smtp:
        with pytest.raises(RuntimeError, match="outbound policy is disabled"):
            execute_one_authorized_outbox(grant_id=grant.pk)
    smtp.assert_not_called()
    grant.refresh_from_db()
    outbox.refresh_from_db()
    assert grant.used_at is None
    assert outbox.status == "queued"
