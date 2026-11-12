"""Owned, email-free TRX invoice receipt recovery; no chain or SMTP calls."""
import os
import re
import secrets
from datetime import timedelta
from html import unescape
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.mpw_recovery_test_settings")

import django
django.setup()

from django.contrib.auth import get_user_model
from django.core import signing
from django.http import Http404, HttpResponse
from django.middleware.csrf import get_token
from django.test import RequestFactory, TransactionTestCase, override_settings
from django.utils import timezone

from core.models import Order, PaymentIntent
from services.mpw_trx_receipt_recovery import (
    RECEIPT_SALT, _read_receipt, issue_receipt,
    receipt_markup, receipt_recovery,
)
from services.mpw_walletless_commercial_intent import PROVIDER


@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "testserver"])
class GuestReceiptRecoveryTests(TransactionTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()
        self.buyer = User.objects.create(username="mpwguest_" + secrets.token_hex(12))
        self.buyer.set_unusable_password()
        self.buyer.save(update_fields=["password"])
        self.other = User.objects.create(username="mpwguest_" + secrets.token_hex(12))
        self.other.set_unusable_password()
        self.other.save(update_fields=["password"])
        self.order = Order.objects.create(
            customer=self.buyer, status="pending", total="5", currency="USD",
        )
        self.invoice = PaymentIntent.objects.create(
            order=self.order, amount="5", currency="USD", provider=PROVIDER,
            idempotency_key=secrets.token_hex(16),
        )

    def _request(self, code):
        csrf_secret = "a" * 32
        bootstrap = self.factory.get(
            "/commerce/trx-easy/receipt/", secure=True,
            HTTP_HOST="mojplaywin.com",
        )
        bootstrap.META["CSRF_COOKIE"] = csrf_secret
        token = get_token(bootstrap)
        request = self.factory.post(
            "/commerce/trx-easy/receipt/",
            {"receipt": code, "csrfmiddlewaretoken": token},
            secure=True, HTTP_HOST="mojplaywin.com",
            HTTP_REFERER="https://mojplaywin.com/commerce/trx-easy/receipt/",
        )
        request.META["CSRF_COOKIE"] = csrf_secret
        request.COOKIES["csrftoken"] = csrf_secret
        return request

    def test_receipt_is_bound_to_one_invoice_and_one_guest(self):
        code = issue_receipt(self.invoice.pk, self.buyer)
        self.assertEqual(_read_receipt(code), (self.invoice.pk, self.buyer.pk))
        self.assertNotIn("@", code)

    def test_receipt_is_displayed_without_email_field(self):
        markup = receipt_markup(self.invoice.pk, self.buyer)
        self.assertIn("Private purchase receipt", markup)
        self.assertIn("No email", markup)
        self.assertIn("readonly", markup)
        self.assertNotIn('name="email"', markup)

    def test_valid_receipt_delegates_only_to_existing_paid_file_handler(self):
        code = issue_receipt(self.invoice.pk, self.buyer)
        response = HttpResponse("verified download", status=200)
        with patch("services.mpw_trx_commercial_web._download_paid", return_value=response) as deliver:
            request = self._request(code)
            result = receipt_recovery(request)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b"verified download")
        deliver.assert_called_once_with(request, self.invoice.pk)
        self.assertEqual(request.user.pk, self.buyer.pk)
        self.assertEqual(result["X-Robots-Tag"], "noindex, nofollow")

    def test_expired_owned_invoice_keeps_receipt_without_stale_payment_details(self):
        """A guest must still be able to save the private key after quote expiry."""
        from services import mpw_trx_commercial_web as merchant

        request = self.factory.get(
            f"/commerce/trx-easy/invoice/{self.invoice.pk}/",
            secure=True, HTTP_HOST="mojplaywin.com",
        )
        request.user = self.buyer
        expired = SimpleNamespace(expires_at=timezone.now() - timedelta(minutes=40))
        with patch.object(merchant, "_ensure_live"), \
             patch.object(merchant, "_get_owner_invoice", return_value=self.invoice), \
             patch.object(merchant, "_decode", return_value=expired):
            response = merchant._show_invoice(request, self.invoice.pk)

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("Invoice no longer payable", html)
        self.assertIn("Do not send TRX to an expired quote.", html)
        self.assertIn("Your private purchase receipt key", html)
        self.assertIn("No email", html)
        self.assertNotIn("Send exact", html)
        self.assertNotIn('data-reconcile-url=', html)
        match = re.search(
            r'<textarea id="mpw-receipt-key" rows="4" readonly>([^<]+)</textarea>',
            html,
        )
        self.assertIsNotNone(match)
        self.assertEqual(
            _read_receipt(unescape(match.group(1))),
            (self.invoice.pk, self.buyer.pk),
        )
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertIn("no-store", response["Cache-Control"])

    def test_tampered_receipt_never_reaches_paid_handler(self):
        code = issue_receipt(self.invoice.pk, self.buyer)
        bad = ("A" if code[0] != "A" else "B") + code[1:]
        with patch("services.mpw_trx_commercial_web._download_paid") as deliver:
            with self.assertRaises(Http404):
                receipt_recovery(self._request(bad))
        deliver.assert_not_called()

    def test_valid_signature_cannot_reassign_another_buyers_invoice(self):
        mismatched = signing.dumps(
            {"v": 1, "i": self.invoice.pk, "u": self.other.pk},
            salt=RECEIPT_SALT,
        )
        with patch("services.mpw_trx_commercial_web._download_paid") as deliver:
            with self.assertRaises(Http404):
                receipt_recovery(self._request(mismatched))
        deliver.assert_not_called()

    def test_unpaid_or_unavailable_download_cannot_be_granted(self):
        code = issue_receipt(self.invoice.pk, self.buyer)
        with patch("services.mpw_trx_commercial_web._download_paid", side_effect=Http404):
            with self.assertRaises(Http404):
                receipt_recovery(self._request(code))

    def test_malformed_signed_claim_is_rejected(self):
        invalid = signing.dumps(
            {"v": True, "i": self.invoice.pk, "u": self.buyer.pk},
            salt=RECEIPT_SALT,
        )
        with self.assertRaises(Http404):
            _read_receipt(invalid)

    def test_no_receipt_for_password_enabled_customer(self):
        customer = get_user_model().objects.create_user(
            username="paying_member", password="secret-pass",
        )
        with self.assertRaises(Http404):
            issue_receipt(self.invoice.pk, customer)
        self.assertEqual(receipt_markup(self.invoice.pk, customer), "")

    def test_get_form_is_not_an_email_recovery_page(self):
        request = self.factory.get(
            "/commerce/trx-easy/receipt/", secure=True,
            HTTP_HOST="mojplaywin.com",
        )
        response = receipt_recovery(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="receipt"', response.content)
        self.assertNotIn(b'name="email"', response.content)
        self.assertEqual(response["Cache-Control"].split(",")[0], "private")

    def test_non_https_request_is_not_allowed(self):
        request = self.factory.get(
            "/commerce/trx-easy/receipt/", HTTP_HOST="mojplaywin.com",
        )
        with self.assertRaises(Http404):
            receipt_recovery(request)

    def test_receipt_does_not_create_an_owner_cookie(self):
        code = issue_receipt(self.invoice.pk, self.buyer)
        with patch("services.mpw_trx_commercial_web._download_paid", return_value=HttpResponse("ok")):
            response = receipt_recovery(self._request(code))
        self.assertNotIn("mpw_trx_guest_owner", response.cookies)
