"""Isolated Django tests: no network, real money, SMTP or production DB."""
import hashlib
import json
import os
import secrets
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from unittest.mock import MagicMock
from pytest import mark

pytestmark = mark.django_db(transaction=True)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.mpw_recovery_test_settings")

import django
django.setup()

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.test import RequestFactory, override_settings
from django.utils import timezone
from core.models import (GuestOrderEmail, GuestRecoveryRate, GuestRecoveryToken,
                         LedgerEntry, Order, PaymentIntent, PaymentWebhookEvent)
from services import mpw_trx_email_recovery as module
from services import mpw_trx_guest_commerce as guest_adapter


class RecoveryIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("migrate", run_syncdb=True, verbosity=0, interactive=False)

    def setUp(self):
        GuestRecoveryToken.objects.all().delete()
        GuestRecoveryRate.objects.all().delete()
        GuestOrderEmail.objects.all().delete()
        PaymentWebhookEvent.objects.all().delete()
        LedgerEntry.objects.all().delete()
        PaymentIntent.objects.all().delete()
        Order.objects.all().delete()
        get_user_model().objects.all().delete()
        self.rf = RequestFactory()
        self.user = get_user_model().objects.create(username="mpwguest_" + secrets.token_hex(12))
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])

    def _request(self, email="buyer@example.com"):
        req = self.rf.post("/commerce/trx-easy/start/72/", {"email": email},
                           secure=True, HTTP_HOST="mojplaywin.com")
        req.user = self.user
        return req

    def _identity(self, request, create=False):
        return self.user, None

    @staticmethod
    def _install(response, cookie):
        return response

    def _start(self, req, *_a, **_k):
        order = Order.objects.create(customer=req.user, status="pending", total="5", currency="USD")
        intent = PaymentIntent.objects.create(order=order, amount="5", currency="USD",
                     provider="mpw_walletless_trx_v1", idempotency_key=secrets.token_hex(16))
        response = HttpResponse(status=302)
        response["Location"] = "/commerce/trx-easy/invoice/%d/" % intent.pk
        return response

    def test_checkout_binds_immutable_email_to_exact_new_order(self):
        response = module.bound_checkout(self._request(), self._start, self._identity,
                                         self._install, (72,), {})
        self.assertEqual(response.status_code, 302)
        claim = GuestOrderEmail.objects.get()
        self.assertEqual(claim.email_address, "buyer@example.com")
        self.assertEqual(claim.email_digest, module._digest("buyer@example.com"))
        self.assertEqual(claim.order.customer_id, self.user.pk)

    def test_missing_email_rejects_before_order_creation(self):
        response = module.bound_checkout(self._request(""), self._start, self._identity,
                                         self._install, (72,), {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_alias_email_field_works_but_conflicting_values_fail_closed(self):
        req = self.rf.post("/commerce/trx-easy/start/72/",
                           {"buyer_email": "buyer@example.com"},
                           secure=True, HTTP_HOST="mojplaywin.com")
        req.user = self.user
        self.assertEqual(module.bound_checkout(req, self._start, self._identity,
                         self._install, (72,), {}).status_code, 302)
        req2 = self.rf.post("/commerce/trx-easy/start/72/",
                            {"email": "buyer@example.com", "buyer_email": "other@example.com"},
                            secure=True, HTTP_HOST="mojplaywin.com")
        req2.user = self.user
        self.assertEqual(module.bound_checkout(req2, self._start, self._identity,
                         self._install, (72,), {}).status_code, 400)
        self.assertEqual(Order.objects.count(), 1)

    def test_email_claim_cannot_be_reassigned_after_creation(self):
        module.bound_checkout(self._request(), self._start, self._identity,
                              self._install, (72,), {})
        claim = GuestOrderEmail.objects.get()
        claim.email_address = "attacker@example.com"
        with self.assertRaises(ValidationError):
            claim.save()
        claim.refresh_from_db()
        self.assertEqual(claim.email_address, "buyer@example.com")

    def test_preexisting_unclaimed_order_cannot_be_attached_to_new_email(self):
        order = Order.objects.create(customer=self.user, status="pending", total="5", currency="USD")
        intent = PaymentIntent.objects.create(order=order, amount="5", currency="USD",
                        idempotency_key="old", provider="mpw_walletless_trx_v1")

        def replay(req, *_a, **_k):
            res = HttpResponse(status=302)
            res["Location"] = f"/commerce/trx-easy/invoice/{intent.pk}/"
            return res

        with self.assertRaises(Http404):
            module.bound_checkout(self._request(), replay, self._identity,
                                  self._install, (72,), {})
        self.assertFalse(GuestOrderEmail.objects.exists())

    def test_reused_invoice_must_match_original_checkout_email(self):
        response = module.bound_checkout(self._request(), self._start, self._identity,
                                         self._install, (72,), {})
        intent = PaymentIntent.objects.get()

        def replay(req, *_a, **_k):
            return response

        same = module.bound_checkout(self._request("BUYER@example.com"), replay,
                                     self._identity, self._install, (72,), {})
        self.assertEqual(same.status_code, 302)
        with self.assertRaises(Http404):
            module.bound_checkout(self._request("other@example.com"), replay,
                                  self._identity, self._install, (72,), {})
        self.assertEqual(GuestOrderEmail.objects.get().order_id, intent.order_id)

    def test_token_is_hash_only_expires_and_consumes_once(self):
        code = secrets.token_urlsafe(32)
        digest = hashlib.sha256(code.encode("ascii")).hexdigest()
        GuestRecoveryToken.objects.create(token_digest=digest, email_digest="a" * 64,
                    expires_at=timezone.now() + timedelta(minutes=15))
        self.assertEqual(module._consume(code), "a" * 64)
        self.assertIsNone(module._consume(code))
        self.assertNotIn(code, str(GuestRecoveryToken.objects.values().first()))
        expired = secrets.token_urlsafe(32)
        GuestRecoveryToken.objects.create(
            token_digest=hashlib.sha256(expired.encode("ascii")).hexdigest(),
            email_digest="b" * 64, expires_at=timezone.now() - timedelta(seconds=1))
        self.assertIsNone(module._consume(expired))

    @override_settings(MPW_GUEST_RECOVERY_EMAIL_APPROVED=False)
    def test_nonexistent_and_existing_email_get_same_response_without_mail(self):
        req1 = self.rf.post(module.ROOT, {"email": "unknown@example.com"},
                            secure=True, HTTP_HOST="mojplaywin.com", REMOTE_ADDR="192.0.2.101",
                            HTTP_REFERER="https://mojplaywin.com" + module.ROOT)
        req2 = self.rf.post(module.ROOT, {"email": "buyer@example.com"},
                            secure=True, HTTP_HOST="mojplaywin.com", REMOTE_ADDR="192.0.2.102",
                            HTTP_REFERER="https://mojplaywin.com" + module.ROOT)
        from django.middleware.csrf import get_token
        for req in (req1, req2):
            req.META["CSRF_COOKIE"] = "A" * 32
            req.COOKIES["csrftoken"] = "A" * 32
            data = req.POST.copy()
            data["csrfmiddlewaretoken"] = get_token(req)
            req._post = data
        with patch.object(module, "_issue") as issued:
            first = module.recovery_request(req1)
            second = module.recovery_request(req2)
        self.assertEqual(first.content, second.content)
        self.assertEqual(first.status_code, 200)
        issued.assert_not_called()
        self.assertFalse(GuestRecoveryToken.objects.exists())

    def test_recovery_throttle_persists_and_denies_abuse(self):
        req = self.rf.post(module.ROOT, secure=True, REMOTE_ADDR="192.0.2.55")
        for _ in range(8):
            self.assertTrue(module._allowed(req))
        self.assertFalse(module._allowed(req))
        self.assertEqual(GuestRecoveryRate.objects.count(), 1)

    @override_settings(MPW_GUEST_RECOVERY_EMAIL_APPROVED=True)
    def test_approved_request_still_does_not_send_for_unknown_email(self):
        module.bound_checkout(self._request(), self._start, self._identity,
                              self._install, (72,), {})
        responses = []
        with patch.object(module, "_allowed", return_value=True), \
             patch.object(module, "_eligible_orders") as eligible, \
             patch.object(module, "_issue") as issue:
            for address, found in (("buyer@example.com", True),
                                   ("unknown@example.com", False)):
                req = self.rf.post(module.ROOT, {"email": address}, secure=True,
                    HTTP_HOST="mojplaywin.com",
                    HTTP_REFERER="https://mojplaywin.com" + module.ROOT)
                from django.middleware.csrf import get_token
                req.META["CSRF_COOKIE"] = "B" * 32
                req.COOKIES["csrftoken"] = "B" * 32
                data = req.POST.copy()
                data["csrfmiddlewaretoken"] = get_token(req)
                req._post = data
                eligible.return_value = ([(Order.objects.get(), PaymentIntent.objects.get())]
                                         if found else [])
                responses.append(module.recovery_request(req))
            self.assertEqual(issue.call_count, 1)
        self.assertEqual(responses[0].content, responses[1].content)

    def test_fulfillment_rejects_partially_ready_order(self):
        fake_field = SimpleNamespace(name="item", related_model=SimpleNamespace(
            _meta=SimpleNamespace(label_lower="core.orderitem")))
        state_field = SimpleNamespace(name="status")
        fulfillment = SimpleNamespace(
            _meta=SimpleNamespace(fields=[fake_field, state_field]),
            objects=MagicMock(),
        )
        fulfillment.objects.filter.return_value.count.return_value = 1
        fake_items = MagicMock()
        fake_items.objects.filter.return_value.count.return_value = 2
        with patch.object(module.apps, "get_model", return_value=fulfillment), \
             patch.object(module, "OrderItem", fake_items):
            self.assertFalse(module._ready(SimpleNamespace(pk=123)))
            fulfillment.objects.filter.return_value.count.return_value = 2
            self.assertTrue(module._ready(SimpleNamespace(pk=123)))

    def test_prune_removes_no_persistent_order_claims(self):
        module.bound_checkout(self._request(), self._start, self._identity,
                              self._install, (72,), {})
        GuestRecoveryRate.objects.create(bucket="f" * 64, count=1,
                            expires_at=timezone.now() - timedelta(days=3))
        GuestRecoveryToken.objects.create(token_digest="e" * 64,
                            email_digest="a" * 64,
                            expires_at=timezone.now() - timedelta(days=3))
        call_command("mpw_purge_recovery_ephemeral", verbosity=0)
        self.assertEqual(GuestOrderEmail.objects.count(), 1)
        self.assertEqual(GuestRecoveryToken.objects.count(), 0)
        self.assertEqual(GuestRecoveryRate.objects.count(), 0)

    @override_settings(MPW_GUEST_RECOVERY_ENABLED=True)
    def test_recovery_urls_are_grafted_without_replacing_existing_handlers(self):
        def handler(*a, **k):
            return HttpResponse()
        names = {"_start_order": handler, "_show_invoice": handler,
                 "_invoice_status": handler, "_reconcile_invoice": handler,
                 "_download_paid": handler}
        names["COMMERCIAL_URLPATTERNS"] = (
            ("commerce/trx-easy/start/<int:product_id>/", handler),
            ("commerce/trx-easy/download/<int:invoice_id>/", handler),
        )
        guest_adapter.patch_commercial(names)
        routes = dict(names["COMMERCIAL_URLPATTERNS"])
        self.assertEqual(len(routes), 6)
        self.assertIn("commerce/trx-easy/recover/download/<int:invoice_id>/", routes)
        self.assertIs(routes["commerce/trx-easy/recover/"], module.recovery_request)
        self.assertIs(names["_start_order"], handler)

    def test_positive_delegation_uses_existing_download_checks(self):
        module.bound_checkout(self._request(), self._start, self._identity,
                              self._install, (72,), {})
        intent = PaymentIntent.objects.get()
        req = self.rf.get(module.ROOT + f"download/{intent.pk}/", secure=True,
                          HTTP_HOST="mojplaywin.com")
        from django.core import signing
        req.COOKIES[module.SESSION_COOKIE] = signing.dumps(
            {"e": module._digest("buyer@example.com"), "n": "test"},
            salt=module.SESSION_SALT)
        called = []

        def original(request, invoice_id):
            called.append((request.user.pk, invoice_id))
            return HttpResponse(b"synthetic-file-only")

        from types import ModuleType
        trusted = ModuleType("services.mpw_trx_commercial_web")
        trusted._download_paid = original
        with patch.object(module, "verified_walletless_credit", return_value=True), \
             patch.object(module, "_ready", return_value=True), \
             patch.dict("sys.modules", {"services.mpw_trx_commercial_web": trusted}), \
             patch("django.urls.resolve", side_effect=AssertionError(
                 "Recovered buyer must not pass through the lost-cookie adapter")):
            res = module.recovery_download(req, intent.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(called, [(self.user.pk, intent.pk)])
        self.assertIn("no-store", res["Cache-Control"])

    def test_missing_private_download_handler_denies_recovery(self):
        from types import ModuleType
        from django.core import signing
        module.bound_checkout(self._request(), self._start, self._identity,
                              self._install, (72,), {})
        intent = PaymentIntent.objects.get()
        req = self.rf.get(module.ROOT + f"download/{intent.pk}/", secure=True,
                          HTTP_HOST="mojplaywin.com")
        req.COOKIES[module.SESSION_COOKIE] = signing.dumps(
            {"e": module._digest("buyer@example.com"), "n": "test"},
            salt=module.SESSION_SALT)
        unavailable = ModuleType("services.mpw_trx_commercial_web")
        with patch.object(module, "verified_walletless_credit", return_value=True), \
             patch.object(module, "_ready", return_value=True), \
             patch.dict("sys.modules", {"services.mpw_trx_commercial_web": unavailable}):
            with self.assertRaises(Http404):
                module.recovery_download(req, intent.pk)

    def test_claim_does_not_grant_download_for_other_email(self):
        module.bound_checkout(self._request(), self._start, self._identity,
                              self._install, (72,), {})
        intent = PaymentIntent.objects.get()
        req = self.rf.get(module.ROOT + f"download/{intent.pk}/", secure=True,
                          HTTP_HOST="mojplaywin.com")
        from django.core import signing
        req.COOKIES[module.SESSION_COOKIE] = signing.dumps(
            {"e": module._digest("other@example.com"), "n": "test"},
            salt=module.SESSION_SALT)
        with patch.object(module, "verified_walletless_credit", return_value=True), \
             patch.object(module, "_ready", return_value=True):
            with self.assertRaises(Http404):
                module.recovery_download(req, intent.pk)

    def test_paid_flag_without_finalized_credit_never_grants_download(self):
        module.bound_checkout(self._request(), self._start, self._identity,
                              self._install, (72,), {})
        intent = PaymentIntent.objects.get()
        order = intent.order
        order.status = "paid"
        order.save(update_fields=["status"])
        intent.status = "paid"
        intent.save(update_fields=["status"])
        with patch.object(module, "_ready", return_value=True):
            self.assertEqual(module._eligible_orders(module._digest("buyer@example.com")), [])

    def test_full_finalized_receipt_is_required_for_recovery(self):
        module.bound_checkout(self._request(), self._start, self._identity,
                              self._install, (72,), {})
        intent = PaymentIntent.objects.get()
        order = intent.order
        order.status = "paid"
        order.save(update_fields=["status"])
        intent.status = "paid"
        receiver = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"
        suns = 12345678
        intent.provider_reference = json.dumps({
            "v": 1, "to": receiver, "sun": suns, "rate": "0.2",
            "at": timezone.now().isoformat(),
        })
        intent.idempotency_key = ("wltrx1:" + hashlib.sha256(receiver.encode()).hexdigest()
                                  + ":" + str(suns))
        intent.save(update_fields=["status", "provider_reference", "idempotency_key"])
        tx = "a" * 64
        proof = "b" * 64
        event = PaymentWebhookEvent.objects.create(
            provider="mpw_walletless_trx_v1", event_id=tx,
            event_type="tron_finalized", status="processed",
            payment_intent=intent, payload_hash=proof,
        )
        credit = LedgerEntry.objects.create(
            order=order, payment_intent=intent, entry_type="credit", amount=order.total,
            currency="USD", reference="walletless:tron-mainnet:" + tx,
            metadata={"payment_method": "mpw_walletless_trx_v1", "network": "tron-mainnet",
                      "tx_hash": tx, "evidence_digest": proof,
                      "walletless_receipt_event_id": event.pk, "sender": receiver},
        )
        with patch.object(module, "_ready", return_value=True):
            self.assertEqual(len(module._eligible_orders(module._digest("buyer@example.com"))), 1)
        with patch.object(module, "_ready", return_value=False):
            self.assertEqual(module._eligible_orders(module._digest("buyer@example.com")), [])
        credit.metadata["evidence_digest"] = "c" * 64
        credit.save(update_fields=["metadata"])
        with patch.object(module, "_ready", return_value=True):
            self.assertEqual(module._eligible_orders(module._digest("buyer@example.com")), [])


if __name__ == "__main__":
    unittest.main()
