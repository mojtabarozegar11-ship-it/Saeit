from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone
from enterprise_portal.models import BusinessUnit
from .models import Contact, Message, MessageEvent
from .services import dispatch_one, enqueue

User = get_user_model()
TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"],
                   STORAGES=TEST_STORAGES, COMPANY_MESSAGING_SEND_ENABLED=True,
                   COMPANY_MESSAGING_EMAIL_ENABLED=True)
class MessagingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(username="owner-msg", email="owner@example.org", password="test-only")
        self.staff = User.objects.create_user(username="staff-msg", password="test-only", is_staff=True)
        self.other = User.objects.create_user(username="other-msg", password="test-only", is_staff=True)
        self.unit = BusinessUnit.objects.create(code="hqm", name="مدیریت")
        self.unit2 = BusinessUnit.objects.create(code="salesm", name="فروش")
        self.client.force_login(self.owner)

    def internal(self):
        return enqueue(Message(unit=self.unit, channel="internal", sender=self.owner,
                               recipient_user=self.owner, body="متن داخلی امن", subject="داخلی"))

    def external(self, **kwargs):
        c = Contact.objects.create(
            unit=self.unit, name="مشتری", email="customer@example.org",
            email_consent_at=timezone.now(), consent_evidence="documented opt-in ticket #42", **kwargs
        )
        return enqueue(Message(unit=self.unit, channel="email", sender=self.owner,
                               contact=c, body="متن ایمیل", subject="پیگیری"))

    def test_private_pages_and_auth(self):
        self.assertEqual(self.client.get("/company/office/messages/", secure=True).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get("/company/office/messages/", secure=True).status_code, 302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/company/office/messages/", secure=True).status_code, 403)

    def test_internal_inbox_read_only_on_explicit_post(self):
        msg = self.internal()
        self.assertEqual(msg.status, "internal")
        self.assertIsNone(msg.read_at)
        detail = "/company/office/messages/%s/" % msg.pk
        self.assertEqual(self.client.get(detail, secure=True).status_code, 200)
        self.assertEqual(self.client.get(detail + "read/", secure=True).status_code, 405)
        msg.refresh_from_db()
        self.assertIsNone(msg.read_at)
        self.assertEqual(self.client.post(detail + "read/", secure=True).status_code, 302)
        msg.refresh_from_db()
        self.assertIsNotNone(msg.read_at)
        self.assertEqual(msg.events.filter(code="read_by_recipient").count(), 1)

    def test_missing_consent_and_suppression_fail_closed(self):
        contact = Contact.objects.create(unit=self.unit, name="بدون رضایت", email="no@example.org")
        with self.assertRaises(ValidationError):
            enqueue(Message(unit=self.unit, channel="email", sender=self.owner,
                            contact=contact, body="نباید فرستاده شود"))
        self.assertEqual(Message.objects.count(), 0)
        msg = self.external()
        msg.contact.suppressed = True
        msg.contact.save()
        with patch("company_messaging.services._deliver") as delivery:
            self.assertEqual(dispatch_one(msg.pk), "blocked")
            delivery.assert_not_called()
        msg.refresh_from_db()
        self.assertEqual(msg.status, "blocked")

    def test_accepted_is_not_delivered_and_not_repeated(self):
        msg = self.external()
        with patch("company_messaging.services._deliver", return_value="provider-ack") as deliver:
            self.assertEqual(dispatch_one(msg.pk), "accepted")
            self.assertEqual(dispatch_one(msg.pk), "not_due")
            deliver.assert_called_once()
        msg.refresh_from_db()
        self.assertEqual(msg.status, "accepted")
        self.assertEqual(msg.external_reference, "provider-ack")
        self.assertIsNotNone(msg.accepted_at)
        self.assertEqual(msg.attempts, 1)

    def test_ambiguous_provider_failure_is_not_auto_retried(self):
        msg = self.external()
        with patch("company_messaging.services._deliver", side_effect=TimeoutError):
            self.assertEqual(dispatch_one(msg.pk), "uncertain")
        self.assertEqual(dispatch_one(msg.pk), "not_due")
        msg.refresh_from_db()
        self.assertEqual(msg.attempts, 1)
        self.assertEqual(msg.error_code, "provider_outcome_unknown")

    def test_disabled_kill_switch_never_sends(self):
        msg = self.external()
        with override_settings(COMPANY_MESSAGING_SEND_ENABLED=False):
            with patch("company_messaging.services._deliver") as delivery:
                self.assertEqual(dispatch_one(msg.pk), "disabled")
                delivery.assert_not_called()
        msg.refresh_from_db()
        self.assertEqual(msg.status, "queued")

    def test_cross_unit_contact_rejected(self):
        contact = Contact.objects.create(
            unit=self.unit2, name="واحد دیگر", email="second@example.org",
            email_consent_at=timezone.now(), consent_evidence="opt-in #43",
        )
        with self.assertRaises(ValidationError):
            enqueue(Message(unit=self.unit, channel="email", sender=self.owner,
                            contact=contact, body="ممنوع"))

    def test_contact_without_provenance_rejected(self):
        contact = Contact(unit=self.unit, name="فاقد سند", email="foo@example.org",
                          email_consent_at=timezone.now())
        with self.assertRaises(ValidationError):
            contact.full_clean()

    def test_compose_form_csrf_and_cross_unit(self):
        self.assertEqual(self.client.get("/company/office/messages/new/", secure=True).status_code, 200)
        contact = Contact.objects.create(
            unit=self.unit2, name="خارج از واحد", email="other@example.org",
            email_consent_at=timezone.now(), consent_evidence="ticket #999",
        )
        response = self.client.post("/company/office/messages/new/", secure=True, data={
            "unit": self.unit.pk, "channel": "email", "contact": contact.pk,
            "subject": "رد", "body": "باید رد شود",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Message.objects.count(), 0)
        self.assertContains(response, "مخاطب")

    @override_settings(
        COMPANY_MESSAGING_SMS_ENABLED=True,
        COMPANY_SMS_KAVENEGAR_KEY="offline-only-key",
        COMPANY_SMS_KAVENEGAR_SENDER="100010",
    )
    def test_sms_requires_positive_upstream_message_id(self):
        contact = Contact.objects.create(
            unit=self.unit, name="SMS opt-in", phone_e164="+989123456789",
            sms_consent_at=timezone.now(), consent_evidence="confirmed-optin-ticket-5",
        )
        missing = enqueue(Message(unit=self.unit, channel="sms", sender=self.owner,
                                  contact=contact, body="پیام اول"))
        with patch("company_messaging.services._http_post",
                   return_value={"return": {"status": 200}, "entries": [{}]}) as upstream:
            self.assertEqual(dispatch_one(missing.pk), "uncertain")
            self.assertEqual(dispatch_one(missing.pk), "not_due")
            upstream.assert_called_once()
        missing.refresh_from_db()
        self.assertEqual(missing.attempts, 1)
        self.assertFalse(missing.external_reference)
        valid = enqueue(Message(unit=self.unit, channel="sms", sender=self.owner,
                                contact=contact, body="پیام دوم"))
        with patch("company_messaging.services._http_post",
                   return_value={"return": {"status": 200}, "entries": [{"messageid": 901}]}) as upstream:
            self.assertEqual(dispatch_one(valid.pk), "accepted")
            upstream.assert_called_once()
        valid.refresh_from_db()
        self.assertEqual(valid.external_reference, "901")

    @override_settings(
        COMPANY_MESSAGING_WHATSAPP_ENABLED=True,
        COMPANY_WHATSAPP_ACCESS_TOKEN="offline-only-token",
        COMPANY_WHATSAPP_PHONE_ID="999123",
        COMPANY_WHATSAPP_TEMPLATE_NAME="approved_offline_template",
        COMPANY_WHATSAPP_TEMPLATE_LANGUAGE="fa",
    )
    def test_whatsapp_requires_positive_upstream_message_id(self):
        contact = Contact.objects.create(
            unit=self.unit, name="WhatsApp opt-in", phone_e164="+989123456789",
            whatsapp_consent_at=timezone.now(), consent_evidence="confirmed-optin-ticket-6",
        )
        missing = enqueue(Message(unit=self.unit, channel="whatsapp", sender=self.owner,
                                  contact=contact, body="پیام اول"))
        with patch("company_messaging.services._http_post", return_value={"messages": [{}]}) as upstream:
            self.assertEqual(dispatch_one(missing.pk), "uncertain")
            self.assertEqual(dispatch_one(missing.pk), "not_due")
            upstream.assert_called_once()
        missing.refresh_from_db()
        self.assertFalse(missing.external_reference)
        valid = enqueue(Message(unit=self.unit, channel="whatsapp", sender=self.owner,
                                contact=contact, body="پیام دوم"))
        with patch("company_messaging.services._http_post",
                   return_value={"messages": [{"id": "wamid.offline-99"}]}) as upstream:
            self.assertEqual(dispatch_one(valid.pk), "accepted")
            upstream.assert_called_once()
        valid.refresh_from_db()
        self.assertEqual(valid.external_reference, "wamid.offline-99")

    def test_queued_email_is_blocked_when_contact_address_changes(self):
        msg = self.external()
        original_fingerprint = msg.recipient_fingerprint
        self.assertEqual(len(original_fingerprint), 64)
        contact = msg.contact
        contact.email = "changed@example.org"
        contact.save()
        with patch("company_messaging.services._deliver") as deliver:
            self.assertEqual(dispatch_one(msg.pk), "blocked")
            deliver.assert_not_called()
        msg.refresh_from_db()
        self.assertEqual(msg.recipient_fingerprint, original_fingerprint)
        self.assertEqual(msg.error_code, "recipient_or_consent_invalid")

    def test_queued_message_is_blocked_when_consent_provenance_changes(self):
        msg = self.external()
        contact = msg.contact
        contact.consent_evidence = "changed-opt-in-proof-99"
        contact.save()
        with patch("company_messaging.services._deliver") as deliver:
            self.assertEqual(dispatch_one(msg.pk), "blocked")
            deliver.assert_not_called()

    def test_missing_legacy_queue_snapshot_fails_closed(self):
        msg = self.external()
        Message.objects.filter(pk=msg.pk).update(recipient_fingerprint="")
        with patch("company_messaging.services._deliver") as deliver:
            self.assertEqual(dispatch_one(msg.pk), "blocked")
            deliver.assert_not_called()

    def test_queued_body_and_destination_fingerprint_are_immutable(self):
        msg = self.external()
        msg.body = "unauthorized body replacement"
        with self.assertRaises(ValidationError):
            msg.save()
        msg.refresh_from_db()
        msg.recipient_fingerprint = "0" * 64
        with self.assertRaises(ValidationError):
            msg.save()
        msg.refresh_from_db()
        self.assertNotEqual(msg.body, "unauthorized body replacement")
        with self.assertRaises(ValidationError):
            enqueue(msg)

    def test_unchanged_destination_snapshot_allows_single_handoff(self):
        msg = self.external()
        with patch("company_messaging.services._deliver", return_value="accepted-reference") as deliver:
            self.assertEqual(dispatch_one(msg.pk), "accepted")
            self.assertEqual(dispatch_one(msg.pk), "not_due")
            deliver.assert_called_once()
        msg.refresh_from_db()
        self.assertEqual(len(msg.recipient_fingerprint), 64)
        self.assertEqual(msg.external_reference, "accepted-reference")
