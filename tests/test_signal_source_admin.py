"""Signal receipts are staff-read-only evidence, not subscriber products."""
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import SignalSourceEvent


class SignalSourceEvidenceAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        model = get_user_model()
        cls.owner = model.objects.create_superuser(
            username="signals_evidence_super", password="only-a-test-pass",
            email="signals-evidence@example.invalid",
        )
        cls.staff_without_permission = model.objects.create_user(
            username="signals_evidence_staff", password="only-a-test-pass",
            is_staff=True,
        )
        SignalSourceEvent.objects.create(
            brand="saman", source_id="broker_a", event_id="event-001",
            event_at=datetime(2026, 11, 14, tzinfo=timezone.utc),
            canonical_payload="redacted-fixture-payload",
            payload_sha256="a" * 64, source_signature="b" * 64,
        )

    def list_path(self):
        return reverse("admin:core_signalsourceevent_changelist")

    def detail_path(self):
        return reverse("admin:core_signalsourceevent_change",
                       args=[SignalSourceEvent.objects.first().pk])

    def test_anonymous_cannot_view_signal_receipts(self):
        self.assertNotEqual(self.client.get(self.list_path()).status_code, 200)

    def test_staff_without_view_permission_is_denied(self):
        self.client.force_login(self.staff_without_permission)
        self.assertEqual(self.client.get(self.list_path()).status_code, 403)

    def test_superuser_can_review_source_receipt_read_only(self):
        self.client.force_login(self.owner)
        res = self.client.get(self.list_path())
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "event-001")
        self.assertContains(res, "pending_audit")
        self.assertNotContains(res, "Payment verified")

    def test_admin_wont_allow_creating_a_fake_paid_signal(self):
        self.client.force_login(self.owner)
        res = self.client.post(
            reverse("admin:core_signalsourceevent_add"),
            {"brand": "saman", "event_id": "fake-paid", "state": "paid"},
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(SignalSourceEvent.objects.count(), 1)

    def test_admin_wont_edit_source_signature(self):
        self.client.force_login(self.owner)
        res = self.client.post(self.detail_path(), {
            "brand": "zahra", "event_id": "changed",
            "source_signature": "c" * 64, "state": "verified",
        })
        self.assertNotEqual(res.status_code, 302)
        receipt = SignalSourceEvent.objects.get()
        self.assertEqual(receipt.brand, "saman")
        self.assertEqual(receipt.state, "pending_audit")

    def test_admin_wont_delete_audit_row(self):
        self.client.force_login(self.owner)
        res = self.client.post(
            reverse("admin:core_signalsourceevent_delete",
                    args=[SignalSourceEvent.objects.first().pk]),
            {"post": "yes"},
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(SignalSourceEvent.objects.count(), 1)
