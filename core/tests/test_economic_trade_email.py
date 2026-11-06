from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from core.approval import ApprovalService
from core.autonomous_external_trade import authorize_external_trade
from core.economic_trade_email import mailbox_status, queue_trade_email, send_queued_trade_email
from core.economic_trade_models import TradeEmailAudit, TradeMailbox
from core.models import ApprovalRequest


class EconomicTradeEmailTests(TestCase):
    def test_queue_is_company_mailbox_only_and_idempotent(self):
        with override_settings(COMPANY_TRADE_EMAIL="trade@example.com"):
            first = queue_trade_email(
                recipient="supplier@example.cn",
                subject="Trade inquiry",
                body="Please provide your catalogue.",
                trade_context={"country": "CN"},
            )
            second = queue_trade_email(
                recipient="supplier@example.cn",
                subject="Trade inquiry",
                body="Please provide your catalogue.",
                trade_context={"country": "CN"},
            )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(TradeMailbox.objects.count(), 1)
        self.assertEqual(TradeEmailAudit.objects.count(), 2)
        self.assertEqual(first.status, "queued")

    @override_settings(TRADE_EMAIL_ENABLED=False)
    def test_real_send_is_disabled_by_default(self):
        outbox = queue_trade_email(
            recipient="supplier@example.cn",
            subject="Trade inquiry",
            body="Draft only",
        )
        with self.assertRaises(RuntimeError):
            send_queued_trade_email(outbox.pk)

    def test_non_queued_item_cannot_be_sent_again(self):
        outbox = queue_trade_email(
            recipient="supplier@example.cn",
            subject="Already handled",
            body="No duplicate delivery.",
        )
        outbox.status = "sent"
        outbox.save(update_fields=["status"])
        with override_settings(TRADE_EMAIL_ENABLED=True):
            with self.assertRaisesRegex(RuntimeError, "not queued"):
                send_queued_trade_email(outbox.pk)

    def test_status_does_not_expose_credentials(self):
        status = mailbox_status()
        self.assertNotIn("password", status)
        self.assertNotIn("host_password", status)


class ExternalTradeApprovalTests(TestCase):
    def test_request_step_never_self_approves_or_issues_grant(self):
        owner = get_user_model().objects.create_user(
            username="trade-owner",
            email="owner@example.com",
        )
        request = authorize_external_trade(owner_id=owner.pk)
        request.refresh_from_db()
        self.assertIsInstance(request, ApprovalRequest)
        self.assertEqual(request.status, "pending")
        self.assertFalse(request.grants.exists())

        with self.assertRaises(ValueError):
            ApprovalService().issue_grant(request.pk, owner.pk)
