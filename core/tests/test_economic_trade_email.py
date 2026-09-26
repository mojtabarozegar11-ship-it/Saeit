from django.test import TestCase, override_settings

from core.economic_trade_email import mailbox_status, queue_trade_email, send_queued_trade_email
from core.economic_trade_models import TradeEmailAudit, TradeMailbox


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

    def test_status_does_not_expose_credentials(self):
        status = mailbox_status()
        self.assertNotIn("password", status)
        self.assertNotIn("host_password", status)
