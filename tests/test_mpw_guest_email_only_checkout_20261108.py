"""Regression checks for real guest email/TRX checkout, with no SMTP or chain IO."""
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
from services.mpw_trx_email_recovery import _digest


@override_settings(
    ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com", "testserver"],
    MPW_GUEST_RECOVERY_ENABLED=False,
    MPW_GUEST_RECOVERY_EMAIL_APPROVED=False,
)
class GuestEmailOnlyCheckoutTests(TransactionTestCase):
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

    def test_missing_email_is_rejected_even_when_recovery_mail_is_disabled(self):
        response = self._dispatch({})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(GuestOrderEmail.objects.count(), 0)

    def test_email_is_durably_bound_without_sending_recovery_mail(self):
        with patch("django.core.mail.EmailMessage.send") as send:
            response = self._dispatch({"email": "Buyer@Example.com"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 1)
        claim = GuestOrderEmail.objects.get()
        self.assertEqual(claim.email_address, "buyer@example.com")
        self.assertEqual(claim.email_digest, _digest("buyer@example.com"))
        self.assertEqual(claim.order.customer_id, self.buyer.pk)
        send.assert_not_called()

    def test_conflicting_email_aliases_fail_without_unowned_invoice(self):
        response = self._dispatch({
            "email": "a@example.com", "buyer_email": "b@example.com",
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())


    def test_guest_creation_accepts_recovery_compatible_purchase_email_alias(self):
        request = self._request({"purchase_email": "Buyer@Example.com"})
        request.META["CSRF_COOKIE"] = "a" * 32
        with patch.object(guest, "_rate_limit", return_value=None):
            created, cookie = guest._new_user(request)
        self.assertNotEqual(created.pk, self.buyer.pk)
        self.assertEqual(created.email, "buyer@example.com")
        self.assertTrue(created.username.startswith("mpwguest_"))
        self.assertIsInstance(cookie, str)

    def test_existing_guest_accepts_recovery_compatible_purchase_email_alias(self):
        request = self._request({"purchase_email": "Buyer@Example.com"})
        guest._bind_guest_email(request, self.buyer)
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.email, "buyer@example.com")


    def test_blank_primary_alias_does_not_override_valid_purchase_email(self):
        request = self._request({"email": "", "purchase_email": "Buyer@Example.com"})
        request.META["CSRF_COOKIE"] = "b" * 32
        with patch.object(guest, "_rate_limit", return_value=None):
            created, _cookie = guest._new_user(request)
        self.assertEqual(created.email, "buyer@example.com")
        guest._bind_guest_email(request, self.buyer)
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.email, "buyer@example.com")

    def test_conflicting_aliases_cannot_create_or_rebind_guest(self):
        request = self._request({
            "email": "first@example.com", "purchase_email": "second@example.com",
        })
        request.META["CSRF_COOKIE"] = "c" * 32
        with self.assertRaises(Http404):
            guest._new_user(request)
        self.assertEqual(get_user_model().objects.count(), 1)
        with self.assertRaises(Http404):
            guest._bind_guest_email(request, self.buyer)
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.email, "")


def test_checkout_template_is_guest_email_only_and_has_no_wallet_js():
    root = Path(__file__).resolve().parents[1]
    markup = (
        root / "mpw_commerce/templates/mpw_commerce/product_checkout.html"
    ).read_text(encoding="utf-8")
    assert '{% csrf_token %}' in markup
    assert 'name="email"' in markup and 'type="email"' in markup
    assert 'maxlength="254"' in markup and " required" in markup
    assert 'method="post"' in markup
    assert 'action="/commerce/trx-easy/start/{{ product.pk }}/"' in markup
    assert '<script' not in markup.lower()
    assert "connect wallet" not in markup.lower()
    assert "window.ethereum" not in markup
    assert '<meta name="referrer" content="no-referrer">' in markup
