from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from core.approval import ApprovalService
from core.autonomous_external_trade import authorize_external_trade
from core.economic_trade_email import mailbox_status, queue_trade_email, send_queued_trade_email
from core.economic_trade_models import TradeEmailAudit, TradeEmailOutbox, TradeMailbox
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

    def test_invalid_recipient_cannot_create_unusable_trade_draft(self):
        for recipient in ("", "not-an-address", " buyer@example.test",
                          "buyer@example.test\nBcc: victim@example.test", None):
            with self.subTest(recipient=recipient):
                with self.assertRaisesRegex(ValueError, "TRADE_EMAIL_RECIPIENT_INVALID"):
                    queue_trade_email(recipient=recipient, subject="Inquiry", body="Quote please")
        self.assertEqual(TradeEmailOutbox.objects.count(), 0)
        self.assertEqual(TradeMailbox.objects.count(), 0)

    def test_header_injection_and_oversized_subject_cannot_queue(self):
        for subject in ("", "Inquiry\r\nBcc: victim@example.test", "A" * 301, None):
            with self.subTest(subject=str(subject)[:25]):
                with self.assertRaisesRegex(ValueError, "TRADE_EMAIL_SUBJECT_INVALID"):
                    queue_trade_email(recipient="buyer@example.test", subject=subject, body="Quote")
        self.assertEqual(TradeEmailOutbox.objects.count(), 0)

    def test_blank_and_oversized_body_cannot_queue(self):
        for body in ("", "   ", "B" * 100001, None):
            with self.subTest(length=len(body) if body is not None else None):
                with self.assertRaisesRegex(ValueError, "TRADE_EMAIL_BODY_INVALID"):
                    queue_trade_email(recipient="buyer@example.test", subject="Quote", body=body)
        self.assertEqual(TradeEmailOutbox.objects.count(), 0)

    def test_trade_context_must_be_a_structured_object(self):
        for context in ("opaque", [], 1, True):
            with self.subTest(context=context):
                with self.assertRaisesRegex(ValueError, "TRADE_EMAIL_CONTEXT_INVALID"):
                    queue_trade_email(recipient="buyer@example.test", subject="Quote",
                                      body="Details", trade_context=context)
        self.assertEqual(TradeEmailOutbox.objects.count(), 0)

    @override_settings(TRADE_EMAIL_ENABLED=True)
    def test_direct_send_requires_owner_grant_even_if_mail_is_enabled(self):
        outbox = queue_trade_email(
            recipient="supplier@example.cn",
            subject="Trade inquiry",
            body="Draft only",
        )
        with self.assertRaisesRegex(RuntimeError, "requires an exact owner grant"):
            send_queued_trade_email(outbox.pk)

    def test_terminal_item_without_grant_cannot_be_sent_again(self):
        outbox = queue_trade_email(
            recipient="supplier@example.cn",
            subject="Already handled",
            body="No duplicate delivery.",
        )
        outbox.status = "sent"
        outbox.save(update_fields=["status"])
        # The mandatory grant check deliberately precedes reading message
        # state. This test checks the direct, unauthorised entrypoint; the
        # transactional sender tests cover terminal status with a valid grant.
        with override_settings(TRADE_EMAIL_ENABLED=True):
            with self.assertRaisesRegex(RuntimeError, "requires an exact owner grant"):
                send_queued_trade_email(outbox.pk)
        outbox.refresh_from_db()
        self.assertEqual(outbox.status, "sent")

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
        with self.assertRaisesRegex(ValueError, "outbox_id"):
            authorize_external_trade(owner_id=owner.pk)
        outbox = queue_trade_email(
            recipient="buyer@example.org", subject="Private inquiry",
            body="Please review this nonbinding trade inquiry.",
        )
        request = authorize_external_trade(owner_id=owner.pk, outbox_id=outbox.pk)
        request.refresh_from_db()
        self.assertEqual(request.target_type, "TradeEmailOutbox")
        self.assertEqual(request.target_id, str(outbox.pk))
        self.assertIsInstance(request, ApprovalRequest)
        self.assertEqual(request.status, "pending")
        self.assertFalse(request.grants.exists())

        with self.assertRaises(ValueError):
            ApprovalService().issue_grant(request.pk, owner.pk)
