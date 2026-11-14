"""Isolated Django tests for the one-bot B2B owner-approved email path.

SMTP uses the locmem backend or a mock. These tests DO NOT send email,
contact customers, call an LLM, charge, trade, or touch live hosts.
"""
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from core.approval import ApprovalService
from core.autonomous_external_trade import (
    authorize_external_trade, execute_one_authorized_outbox,
)
from core.economic_trade_email import queue_trade_email, send_queued_trade_email
from core.economic_trade_models import TradeEmailAudit
from core.models import ApprovalGrant, ApprovalRequest, AuditLog
from core.trade_outbox_scope import message_digest, validate_outbox_for_owner_grant


@override_settings(
    COMPANY_TRADE_EMAIL="trade@example.invalid",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    TRADE_EMAIL_ENABLED=False,
)
class BoundTradeEmailTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser(
            username="trade-owner", email="owner@example.invalid",
            password="offline-only",
        )
        self.outbox = queue_trade_email(
            recipient="buyer@example.invalid",
            subject="Your requested agricultural feasibility quote",
            body="This is the scope of the requested consultation.",
            trade_context={
                "contact_basis": "requested_quote",
                "basis_evidence_sha256": "a" * 64,
            },
        )
        mailbox = self.outbox.mailbox
        mailbox.active = True
        mailbox.allow_outbound = True
        mailbox.save(update_fields=["active", "allow_outbound"])
        self.outbox.refresh_from_db()
        self.service = ApprovalService()

    def scope(self):
        return {
            "action": "external_write",
            "outbox_id": self.outbox.pk,
            "message_digest": message_digest(self.outbox),
        }

    def approve(self):
        req = authorize_external_trade(owner_id=self.owner.pk, outbox_id=self.outbox.pk)
        self.assertEqual(req.status, "pending")
        self.service.decide(req.pk, approved=True, actor_id=self.owner.pk)
        return req

    def grant(self):
        req = self.approve()
        return self.service.issue_grant(req.pk, self.owner.pk, self.scope())

    def assert_not_sent(self):
        self.assertEqual(len(mail.outbox), 0)

    def test_01_request_is_pending_and_no_mail(self):
        req = authorize_external_trade(owner_id=self.owner.pk, outbox_id=self.outbox.pk)
        self.assertEqual(req.status, "pending")
        self.assertEqual(req.target_id, str(self.outbox.pk))
        self.assert_not_sent()

    def test_02_approval_reason_omits_recipient_and_body(self):
        req = authorize_external_trade(owner_id=self.owner.pk, outbox_id=self.outbox.pk)
        self.assertNotIn(self.outbox.recipient, req.reason)
        self.assertNotIn(self.outbox.body, req.reason)
        self.assertIn(message_digest(self.outbox), req.reason)

    def test_03_grant_is_exact_message_bound(self):
        grant = self.grant()
        self.assertEqual(grant.scope, self.scope())
        self.assertEqual(grant.approval.target_type, "TradeEmailOutbox")

    def test_04_unapproved_request_cannot_grant(self):
        req = authorize_external_trade(owner_id=self.owner.pk, outbox_id=self.outbox.pk)
        with self.assertRaises(ValueError):
            self.service.issue_grant(req.pk, self.owner.pk, self.scope())
        self.assertFalse(ApprovalGrant.objects.exists())

    def test_05_non_superuser_cannot_request(self):
        u = get_user_model().objects.create_user(
            username="employee", password="test-only",
        )
        with self.assertRaises(PermissionError):
            authorize_external_trade(owner_id=u.pk, outbox_id=self.outbox.pk)

    def test_06_invalid_owner_id_denied(self):
        with self.assertRaises(ValueError):
            authorize_external_trade(owner_id=True, outbox_id=self.outbox.pk)

    def test_07_missing_outbox_id_denied(self):
        with self.assertRaises(ValueError):
            authorize_external_trade(owner_id=self.owner.pk)

    def test_08_invalid_outbox_bool_denied(self):
        with self.assertRaises(ValueError):
            authorize_external_trade(owner_id=self.owner.pk, outbox_id=True)

    def test_09_queued_without_contact_basis_denied(self):
        self.outbox.trade_context = {}
        self.outbox.save(update_fields=["trade_context"])
        with self.assertRaises(ValueError):
            authorize_external_trade(owner_id=self.owner.pk, outbox_id=self.outbox.pk)

    def test_10_unrecognized_contact_basis_denied(self):
        self.outbox.trade_context["contact_basis"] = "scraped_list"
        self.outbox.save(update_fields=["trade_context"])
        with self.assertRaises(ValueError):
            authorize_external_trade(owner_id=self.owner.pk, outbox_id=self.outbox.pk)

    def test_11_zero_evidence_denied(self):
        self.outbox.trade_context["basis_evidence_sha256"] = "0" * 64
        self.outbox.save(update_fields=["trade_context"])
        with self.assertRaises(ValueError):
            authorize_external_trade(owner_id=self.owner.pk, outbox_id=self.outbox.pk)

    def test_12_bad_evidence_denied(self):
        self.outbox.trade_context["basis_evidence_sha256"] = "fake"
        self.outbox.save(update_fields=["trade_context"])
        with self.assertRaises(ValueError):
            authorize_external_trade(owner_id=self.owner.pk, outbox_id=self.outbox.pk)

    def test_13_extra_context_denied(self):
        self.outbox.trade_context["send_to_everyone"] = True
        self.outbox.save(update_fields=["trade_context"])
        with self.assertRaises(ValueError):
            authorize_external_trade(owner_id=self.owner.pk, outbox_id=self.outbox.pk)

    def test_14_inactive_mailbox_denied(self):
        self.outbox.mailbox.active = False
        self.outbox.mailbox.save(update_fields=["active"])
        with self.assertRaises(ValueError):
            authorize_external_trade(owner_id=self.owner.pk, outbox_id=self.outbox.pk)

    def test_15_outbound_disabled_denied(self):
        self.outbox.mailbox.allow_outbound = False
        self.outbox.mailbox.save(update_fields=["allow_outbound"])
        with self.assertRaises(ValueError):
            authorize_external_trade(owner_id=self.owner.pk, outbox_id=self.outbox.pk)

    def test_16_policy_gate_disabled_denied(self):
        self.outbox.mailbox.require_policy_gate = False
        self.outbox.mailbox.save(update_fields=["require_policy_gate"])
        with self.assertRaises(ValueError):
            authorize_external_trade(owner_id=self.owner.pk, outbox_id=self.outbox.pk)

    def test_17_terminal_message_cannot_be_approved(self):
        self.outbox.status = "sent"
        self.outbox.save(update_fields=["status"])
        with self.assertRaises(ValueError):
            authorize_external_trade(owner_id=self.owner.pk, outbox_id=self.outbox.pk)

    def test_18_content_mutation_after_grant_refused(self):
        grant = self.grant()
        self.outbox.body += " Unauthorized appended terms."
        self.outbox.save(update_fields=["body"])
        with override_settings(TRADE_EMAIL_ENABLED=True):
            with self.assertRaises(ValueError):
                execute_one_authorized_outbox(grant_id=grant.pk)
        grant.refresh_from_db()
        self.assertIsNone(grant.used_at)
        self.assert_not_sent()

    def test_19_recipient_mutation_after_grant_refused(self):
        grant = self.grant()
        self.outbox.recipient = "different@example.invalid"
        self.outbox.save(update_fields=["recipient"])
        with override_settings(TRADE_EMAIL_ENABLED=True):
            with self.assertRaises(ValueError):
                execute_one_authorized_outbox(grant_id=grant.pk)
        self.assert_not_sent()

    def test_20_subject_mutation_after_grant_refused(self):
        grant = self.grant()
        self.outbox.subject = "changed"
        self.outbox.save(update_fields=["subject"])
        with override_settings(TRADE_EMAIL_ENABLED=True):
            with self.assertRaises(ValueError):
                execute_one_authorized_outbox(grant_id=grant.pk)
        self.assert_not_sent()

    def test_21_sender_mutation_after_grant_refused(self):
        grant = self.grant()
        self.outbox.mailbox.email_address = "wrong@example.invalid"
        self.outbox.mailbox.save(update_fields=["email_address"])
        with override_settings(TRADE_EMAIL_ENABLED=True):
            with self.assertRaises(RuntimeError):
                execute_one_authorized_outbox(grant_id=grant.pk)
        self.assert_not_sent()

    def test_22_sender_disabled_does_not_consume_grant(self):
        grant = self.grant()
        with self.assertRaises(RuntimeError):
            execute_one_authorized_outbox(grant_id=grant.pk)
        grant.refresh_from_db()
        self.assertIsNone(grant.used_at)
        self.assert_not_sent()

    def test_23_direct_send_without_grant_denied(self):
        with override_settings(TRADE_EMAIL_ENABLED=True):
            with self.assertRaisesRegex(RuntimeError, "OWNER_GRANT_REQUIRED"):
                send_queued_trade_email(self.outbox.pk)
        self.assert_not_sent()

    def test_24_one_mock_backend_delivery_marked_unverified(self):
        grant = self.grant()
        with override_settings(TRADE_EMAIL_ENABLED=True):
            sent = execute_one_authorized_outbox(grant_id=grant.pk)
        self.assertEqual(sent.pk, self.outbox.pk)
        self.assertEqual(sent.status, "delivery_submitted_unverified")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(AuditLog.objects.filter(
            action="external_trade_email_submitted_unverified").count(), 1)

    def test_25_second_send_denied(self):
        grant = self.grant()
        with override_settings(TRADE_EMAIL_ENABLED=True):
            execute_one_authorized_outbox(grant_id=grant.pk)
            with self.assertRaises(RuntimeError):
                execute_one_authorized_outbox(grant_id=grant.pk)
        self.assertEqual(len(mail.outbox), 1)

    def test_26_second_grant_from_same_approval_denied(self):
        grant = self.grant()
        with self.assertRaisesRegex(ValueError, "ALREADY_ISSUED"):
            self.service.issue_grant(grant.approval.pk, self.owner.pk, self.scope())

    def test_27_other_queued_message_not_implicitly_selected(self):
        other = queue_trade_email(
            recipient="other@example.invalid", subject="Second separate request",
            body="Not the message approved",
        )
        grant = self.grant()
        with override_settings(TRADE_EMAIL_ENABLED=True):
            execute_one_authorized_outbox(grant_id=grant.pk)
        other.refresh_from_db()
        self.assertEqual(other.status, "queued")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.outbox.recipient])

    def test_28_failed_transport_stays_uncertain_and_nonretryable(self):
        grant = self.grant()
        with override_settings(TRADE_EMAIL_ENABLED=True), patch(
            "core.economic_trade_email.EmailMessage.send", side_effect=OSError("synthetic")
        ):
            with self.assertRaisesRegex(RuntimeError, "RECONCILIATION_REQUIRED"):
                execute_one_authorized_outbox(grant_id=grant.pk)
        self.outbox.refresh_from_db()
        grant.refresh_from_db()
        self.assertEqual(self.outbox.status, "delivery_uncertain")
        self.assertIsNotNone(grant.used_at)

    def test_29_zero_transport_return_is_uncertain(self):
        grant = self.grant()
        with override_settings(TRADE_EMAIL_ENABLED=True), patch(
            "core.economic_trade_email.EmailMessage.send", return_value=0
        ):
            with self.assertRaises(RuntimeError):
                execute_one_authorized_outbox(grant_id=grant.pk)
        self.outbox.refresh_from_db()
        self.assertEqual(self.outbox.status, "delivery_uncertain")

    def test_30_revoked_owner_blocks_send(self):
        grant = self.grant()
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        with override_settings(TRADE_EMAIL_ENABLED=True):
            with self.assertRaises(ValueError):
                execute_one_authorized_outbox(grant_id=grant.pk)
        self.assert_not_sent()

    def test_31_revoked_approval_blocks_send(self):
        grant = self.grant()
        grant.approval.status = "rejected"
        grant.approval.save(update_fields=["status"])
        with override_settings(TRADE_EMAIL_ENABLED=True):
            with self.assertRaises(ValueError):
                execute_one_authorized_outbox(grant_id=grant.pk)
        self.assert_not_sent()

    def test_32_trade_context_mutation_blocks_send(self):
        grant = self.grant()
        self.outbox.trade_context["contact_basis"] = "existing_customer"
        self.outbox.save(update_fields=["trade_context"])
        with override_settings(TRADE_EMAIL_ENABLED=True):
            with self.assertRaises(ValueError):
                execute_one_authorized_outbox(grant_id=grant.pk)
        self.assert_not_sent()

    def test_33_wrong_grant_id_type_denied(self):
        with self.assertRaises(ValueError):
            execute_one_authorized_outbox(grant_id=True)

    def test_34_unbound_old_mailbox_grant_denied(self):
        fake = ApprovalRequest.objects.create(
            action_type="external_write", target_type="TradeMailbox",
            target_id="company-trade", reason="legacy wildcard",
            risk="high", status="approved", requested_by=self.owner,
        )
        with self.assertRaises(ValueError):
            self.service.issue_grant(
                fake.pk, self.owner.pk,
                {"action": "external_write", "target": "company-trade"},
            )

    def test_35_digest_is_deterministic(self):
        self.assertEqual(message_digest(self.outbox), message_digest(self.outbox))

    def test_36_digest_changes_on_recipient(self):
        old = message_digest(self.outbox)
        self.outbox.recipient = "new@example.invalid"
        self.assertNotEqual(old, message_digest(self.outbox))

    def test_37_claimed_basis_is_not_provider_delivery(self):
        scope = self.scope()
        self.assertEqual(
            validate_outbox_for_owner_grant(self.outbox, scope),
            scope["message_digest"],
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_38_missing_grant_does_not_allow_send(self):
        with override_settings(TRADE_EMAIL_ENABLED=True):
            with self.assertRaises(RuntimeError):
                send_queued_trade_email(self.outbox.pk, grant_id=None)
        self.assert_not_sent()

    def test_39_different_message_id_denied(self):
        grant = self.grant()
        other = queue_trade_email(
            recipient="other@example.invalid", subject="Different",
            body="Unapproved",
        )
        with override_settings(TRADE_EMAIL_ENABLED=True):
            with self.assertRaises(ValueError):
                send_queued_trade_email(other.pk, grant_id=grant.pk)
        self.assert_not_sent()

    def test_40_no_claim_of_settled_cash_or_customer_reply(self):
        grant = self.grant()
        with override_settings(TRADE_EMAIL_ENABLED=True):
            execute_one_authorized_outbox(grant_id=grant.pk)
        record = AuditLog.objects.get(action="external_trade_email_submitted_unverified")
        self.assertIsNone(record.after_state["settled_revenue"])
        self.assertIs(record.after_state["delivery_verified"], False)
        self.assertIs(record.after_state["customer_response_verified"], False)
