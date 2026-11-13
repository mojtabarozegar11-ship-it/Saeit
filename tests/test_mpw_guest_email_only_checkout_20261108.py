"""Regression for the owner's newer email-free guest checkout policy.

The historical filename is retained so existing CI discovery keeps this test.
"""
import os
import secrets
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.mpw_recovery_test_settings")

import django
django.setup()

from django.contrib.auth import get_user_model
from django.http import Http404, HttpResponse
from django.test import RequestFactory, TransactionTestCase, override_settings

from core.models import GuestOrderEmail, Order, PaymentIntent
from services import mpw_trx_guest_commerce as guest


@override_settings(
    ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com", "testserver"],
    MPW_GUEST_RECOVERY_ENABLED=False,
    MPW_GUEST_RECOVERY_EMAIL_APPROVED=False,
)
class GuestReceiptCheckoutTests(TransactionTestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.buyer = get_user_model().objects.create(username="mpwguest_" + secrets.token_hex(12))
        self.buyer.set_unusable_password()
        self.buyer.save(update_fields=["password"])

    def _request(self, form):
        request = self.rf.post(
            "/commerce/trx-easy/start/72/", form, secure=True,
            HTTP_HOST="mojplaywin.com",
        )
        request.user = self.buyer
        return request

    @staticmethod
    def _start(request, product_id):
        order = Order.objects.create(
            customer=request.user, status="pending", total="5", currency="USD",
        )
        intent = PaymentIntent.objects.create(
            order=order, amount="5", currency="USD", provider="mpw_walletless_trx_v1",
            idempotency_key=secrets.token_hex(16),
        )
        response = HttpResponse(status=302)
        response["Location"] = "/commerce/trx-easy/invoice/%d/" % intent.pk
        return response

    def _dispatch(self, form):
        with patch.object(guest, "_identity", return_value=(self.buyer, None)):
            with patch.object(guest, "_install_cookie", side_effect=lambda response, _cookie: response):
                return guest._dispatch(self._request(form), self._start, (72,), {}, create=True)

    def test_missing_email_issues_an_owned_invoice_without_email_claim(self):
        response = self._dispatch({})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(GuestOrderEmail.objects.count(), 0)
        self.assertEqual(Order.objects.get().customer_id, self.buyer.pk)

    def test_submitted_email_is_ignored_and_no_mail_is_sent(self):
        with patch("django.core.mail.EmailMessage.send") as send:
            response = self._dispatch({"email": "Buyer@Example.com"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(GuestOrderEmail.objects.count(), 0)
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.email, "")
        send.assert_not_called()

    def test_conflicting_email_aliases_cannot_bind_buyer_identity(self):
        response = self._dispatch({
            "email": "a@example.com", "buyer_email": "b@example.com",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(GuestOrderEmail.objects.count(), 0)
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.email, "")

    def test_guest_creation_without_email_persists_owner_cookie(self):
        request = self._request({})
        request.META["CSRF_COOKIE"] = "a" * 32
        with patch.object(guest, "_rate_limit", return_value=None):
            created, cookie = guest._new_user(request)
        self.assertNotEqual(created.pk, self.buyer.pk)
        self.assertEqual(created.email, "")
        self.assertTrue(created.username.startswith("mpwguest_"))
        self.assertIsInstance(cookie, str)

    def test_guest_creation_does_not_store_posted_email(self):
        request = self._request({"email": "Buyer@Example.com"})
        request.META["CSRF_COOKIE"] = "b" * 32
        with patch.object(guest, "_rate_limit", return_value=None):
            created, _cookie = guest._new_user(request)
        self.assertEqual(created.email, "")

    def test_unexpected_checkout_response_rolls_back_order(self):
        def invalid_checkout(request, product_id):
            Order.objects.create(
                customer=request.user, status="pending", total="5", currency="USD",
            )
            return HttpResponse("not an invoice", status=200)
        with self.assertRaises(Http404):
            with patch.object(guest, "_identity", return_value=(self.buyer, None)):
                guest._dispatch(self._request({}), invalid_checkout, (72,), {}, create=True)
        self.assertFalse(Order.objects.exists())


def test_checkout_template_is_email_free_and_has_no_wallet_js():
    root = Path(__file__).resolve().parents[1]
    markup = (
        root / "mpw_commerce/templates/mpw_commerce/product_checkout.html"
    ).read_text(encoding="utf-8")
    assert '{% csrf_token %}' in markup
    assert 'name="email"' not in markup and 'type="email"' not in markup
    assert "private receipt key" in markup
    assert 'method="post"' in markup
    assert 'action="/commerce/trx-easy/start/{{ product.pk }}/"' in markup
    assert '<script' not in markup.lower()
    assert "connect wallet" not in markup.lower()
    assert "window.ethereum" not in markup
    assert '<meta name="referrer" content="no-referrer">' in markup
