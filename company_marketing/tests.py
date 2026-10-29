"""Offline tests: no real provider calls, no real spend, no live deployment."""
import json
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone
from enterprise_portal.models import BusinessUnit
from company_messaging.models import Contact, Message
from company_messaging.domestic_providers import send_bot_message
from company_messaging.services import enqueue, dispatch_one
from .models import Campaign, ChannelAccount, Publication, Lead, PerformanceMetric
from .services import approve_publication, dispatch_publication

User = get_user_model()
TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"], STORAGES=TEST_STORAGES)
class MarketingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(
            username="marketing-root", email="marketing@example.org", password="testing-only"
        )
        self.staff = User.objects.create_user(username="marketing-staff", password="testing-only", is_staff=True)
        self.unit = BusinessUnit.objects.create(code="marketing-zm", name="بازاریابی")
        self.other_unit = BusinessUnit.objects.create(code="marketing-other", name="دیگر")
        self.campaign = Campaign.objects.create(
            unit=self.unit, code="autumn", title="کمپین پاییز",
            objective="معرفی تولیدات مجاز", owner=self.owner,
            starts_on=timezone.localdate(), status="active",
        )
        self.channel = ChannelAccount.objects.create(
            unit=self.unit, platform="bale", title="کانال سازمانی",
            destination="-10002", is_company_owned=True,
            ownership_evidence="private-control-log:49", verified_at=timezone.now(),
        )
        self.client.force_login(self.owner)

    def publication(self, **kwargs):
        base = dict(campaign=self.campaign, channel=self.channel, created_by=self.owner,
                    title="اطلاعیه", content="محتوای اختصاصی", rights_reference="rights:001")
        base.update(kwargs)
        return Publication.objects.create(**base)

    def test_management_private_routes_and_permissions(self):
        root = "/company/office/marketing/"
        self.assertEqual(self.client.get(root, secure=True).status_code, 200)
        self.assertEqual(self.client.get(root + "campaigns/new/", secure=True).status_code, 200)
        self.assertEqual(self.client.get(root + "publications/new/", secure=True).status_code, 200)
        item = self.publication()
        self.assertEqual(self.client.get(root + "publications/%s/" % item.pk, secure=True).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(root, secure=True).status_code, 302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(root, secure=True).status_code, 403)

    def test_other_unit_publication_is_hidden(self):
        campaign = Campaign.objects.create(
            unit=self.other_unit, code="other", title="کمپین دیگر",
            objective="other", owner=self.owner
        )
        account = ChannelAccount.objects.create(
            unit=self.other_unit, platform="rubika", title="دیگری", destination="u42"
        )
        item = self.publication(campaign=campaign, channel=account)
        self.assertEqual(self.client.get(
            "/company/office/marketing/publications/%s/" % item.pk, secure=True
        ).status_code, 200)  # Superuser can see both; ordinary staff cannot.
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(
            "/company/office/marketing/publications/%s/" % item.pk, secure=True
        ).status_code, 403)  # Permission denied before lookup.

    def test_cross_unit_publication_rejected(self):
        campaign = Campaign.objects.create(
            unit=self.other_unit, code="cross", title="دیگر", objective="x", owner=self.owner
        )
        with self.assertRaises(ValidationError):
            self.publication(campaign=campaign)

    def test_unverified_channel_cannot_be_approved(self):
        account = ChannelAccount.objects.create(unit=self.unit, platform="bale",
                                                title="فاقد تایید", destination="-11")
        item = self.publication(channel=account)
        with self.assertRaises(ValidationError):
            approve_publication(item.pk, self.owner)
        item.refresh_from_db()
        self.assertEqual(item.status, "draft")

    def test_approval_freezes_signed_payload(self):
        item = self.publication()
        approve_publication(item.pk, self.owner)
        item.refresh_from_db()
        self.assertEqual(item.status, "approved")
        self.assertEqual(item.content_sha256, item.payload_hash())
        item.content = "تغییر بدون تأیید"
        with self.assertRaises(ValidationError):
            item.save()
        item.refresh_from_db()
        self.assertEqual(item.content, "محتوای اختصاصی")

    def test_approval_requires_rights_reference(self):
        item = self.publication(rights_reference="")
        with self.assertRaises(ValidationError):
            approve_publication(item.pk, self.owner)

    def test_publish_disabled_never_contacts_network(self):
        item = self.publication()
        approve_publication(item.pk, self.owner)
        with override_settings(COMPANY_MARKETING_PUBLISH_ENABLED=False):
            with patch("company_marketing.services.send_bot_message") as send:
                self.assertEqual(dispatch_publication(item.pk), "disabled")
                send.assert_not_called()
        item.refresh_from_db()
        self.assertEqual(item.status, "approved")

    @override_settings(COMPANY_MARKETING_PUBLISH_ENABLED=True, COMPANY_MESSAGING_SEND_ENABLED=True)
    def test_provider_acceptance_not_user_delivery_and_no_retry(self):
        item = self.publication()
        approve_publication(item.pk, self.owner)
        with patch("company_marketing.services.send_bot_message", return_value="server-msg-7") as send:
            self.assertEqual(dispatch_publication(item.pk), "accepted")
            self.assertEqual(dispatch_publication(item.pk), "not_due")
            send.assert_called_once()
        item.refresh_from_db()
        self.assertEqual(item.provider_reference, "server-msg-7")
        self.assertEqual(item.attempts, 1)
        self.assertEqual(item.status, "accepted")
        self.assertEqual(item.events.filter(code="accepted").count(), 1)

    @override_settings(COMPANY_MARKETING_PUBLISH_ENABLED=True, COMPANY_MESSAGING_SEND_ENABLED=True)
    def test_unknown_response_requires_manual_reconciliation(self):
        item = self.publication()
        approve_publication(item.pk, self.owner)
        with patch("company_marketing.services.send_bot_message", side_effect=TimeoutError):
            self.assertEqual(dispatch_publication(item.pk), "uncertain")
            self.assertEqual(dispatch_publication(item.pk), "not_due")
        item.refresh_from_db()
        self.assertEqual(item.attempts, 1)
        self.assertEqual(item.error_code, "provider_outcome_unknown")

    @override_settings(COMPANY_MARKETING_PUBLISH_ENABLED=True, COMPANY_MESSAGING_SEND_ENABLED=True)
    def test_unverified_or_unsupported_account_never_publishes(self):
        account = ChannelAccount.objects.create(
            unit=self.unit, platform="soroush", title="سروش", destination="-100",
            is_company_owned=True, verified_at=timezone.now(), ownership_evidence="record#20"
        )
        item = self.publication(channel=account)
        approve_publication(item.pk, self.owner)
        with patch("company_marketing.services.send_bot_message") as send:
            self.assertEqual(dispatch_publication(item.pk), "blocked")
            send.assert_not_called()

    def test_lead_won_cannot_be_recorded_without_verified_evidence(self):
        contact = Contact.objects.create(unit=self.unit, name="مشتری")
        item = Lead(unit=self.unit, contact=contact, campaign=self.campaign,
                    stage="won", source="bale", owner=self.owner)
        with self.assertRaises(ValidationError):
            item.full_clean()
        item.sale_evidence_reference = "confirmed-receipt-ref-12"
        item.verified_sale_irr = 10000
        item.full_clean()
        item.save()
        self.assertEqual(Lead.objects.filter(stage="won").count(), 1)

    def test_metric_without_source_is_rejected(self):
        item = self.publication()
        metric = PerformanceMetric(publication=item, recorded_by=self.owner, impressions=10)
        with self.assertRaises(ValidationError):
            metric.full_clean()

    def test_domestic_contact_must_consent_for_each_network(self):
        contact = Contact.objects.create(unit=self.unit, name="مخاطب",
                                         bale_chat_id="42", consent_evidence="opt-in:339")
        msg = Message(unit=self.unit, channel="bale", sender=self.owner,
                      contact=contact, body="پیام")
        with self.assertRaises(ValidationError):
            enqueue(msg)
        contact.bale_consent_at = timezone.now()
        contact.save()
        msg = enqueue(Message(unit=self.unit, channel="bale", sender=self.owner,
                              contact=contact, body="پیام"))
        self.assertEqual(msg.status, "queued")

    @override_settings(COMPANY_MESSAGING_SEND_ENABLED=True, COMPANY_MESSAGING_BALE_ENABLED=True)
    def test_bale_direct_message_adapter(self):
        contact = Contact.objects.create(unit=self.unit, name="مخاطب", bale_chat_id="42",
            consent_evidence="opt-in:45", bale_consent_at=timezone.now())
        msg = enqueue(Message(unit=self.unit, channel="bale", sender=self.owner,
                              contact=contact, body="سلام"))
        with override_settings(COMPANY_BALE_BOT_TOKEN="fake-offline"):
            with patch("company_messaging.domestic_providers._http_post",
                       return_value={"ok": True, "result": {"message_id": 45}}) as call:
                self.assertEqual(dispatch_one(msg.pk), "accepted")
                url, payload, headers = call.call_args.args
                self.assertIn("tapi.bale.ai", url)
                self.assertEqual(json.loads(payload)["chat_id"], "42")

    @override_settings(COMPANY_MESSAGING_EITAA_ENABLED=True, COMPANY_EITAA_APP_TOKEN="fake-offline")
    def test_eitaa_official_endpoint_contract(self):
        with patch("company_messaging.domestic_providers._http_post",
                   return_value={"ok": True, "result": "success"}) as call:
            self.assertEqual(send_bot_message("eitaa", "45", "توضیح"), "accepted-by-eitaayar")
            self.assertIn("eitaayar.ir/api/app/sendMessage", call.call_args.args[0])
        with patch("company_messaging.domestic_providers._http_post",
                   return_value={"ok": False}):
            with self.assertRaises(RuntimeError):
                send_bot_message("eitaa", "45", "توضیح")

    @override_settings(COMPANY_MESSAGING_RUBIKA_ENABLED=True, COMPANY_RUBIKA_BOT_TOKEN="fake-offline")
    def test_rubika_official_endpoint_contract(self):
        with patch("company_messaging.domestic_providers._http_post",
                   return_value={"data": {"message_id": "rub-9"}}) as call:
            self.assertEqual(send_bot_message("rubika", "c1", "سلام"), "rub-9")
            self.assertIn("botapi.rubika.ir/v3/", call.call_args.args[0])
