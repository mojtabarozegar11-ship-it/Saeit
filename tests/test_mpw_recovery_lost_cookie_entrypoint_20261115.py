"""Regression: paid guest recovery must be discoverable after browser cookie loss.

No orders, emails, invoices, chain requests, or customer identifiers are made.
"""
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase, override_settings

from services.mpw_trx_guest_commerce import patch_public


@override_settings(ALLOWED_HOSTS=["mojplaywin.com"])
class LostCookieRecoveryEntryTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.routes = {
            "product_checkout": lambda request, product_id: None,
            "purchases": lambda request: None,
        }
        patch_public(self.routes)

    def page(self, **settings):
        request = self.factory.get(
            "/commerce/trx-easy/purchases/",
            secure=True,
            HTTP_HOST="mojplaywin.com",
        )
        request.user = AnonymousUser()
        with override_settings(**settings):
            with patch(
                "services.mpw_trx_guest_commerce._read_user", return_value=None
            ):
                return self.routes["purchases"](request)

    def test_approved_email_recovery_is_linked_without_new_invoice(self):
        response = self.page(
            MPW_GUEST_RECOVERY_ENABLED=True,
            MPW_GUEST_RECOVERY_EMAIL_APPROVED=True,
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn('href="/commerce/trx-easy/recover/"', html)
        self.assertIn("do not pay again", html.lower())
        self.assertIn("no-store", response["Cache-Control"])

    def test_no_link_when_outbound_mail_not_approved(self):
        response = self.page(
            MPW_GUEST_RECOVERY_ENABLED=True,
            MPW_GUEST_RECOVERY_EMAIL_APPROVED=False,
        )
        self.assertNotIn(b'href="/commerce/trx-easy/recover/"', response.content)
        self.assertIn(b"purchase support", response.content)

    def test_no_link_when_recovery_release_not_enabled(self):
        response = self.page(
            MPW_GUEST_RECOVERY_ENABLED=False,
            MPW_GUEST_RECOVERY_EMAIL_APPROVED=True,
        )
        self.assertNotIn(b'href="/commerce/trx-easy/recover/"', response.content)

    def test_disabled_recovery_does_not_ask_for_a_second_payment(self):
        response = self.page(
            MPW_GUEST_RECOVERY_ENABLED=False,
            MPW_GUEST_RECOVERY_EMAIL_APPROVED=False,
        )
        self.assertIn(b"do not pay again", response.content.lower())
        self.assertNotIn(b"amount", response.content)
