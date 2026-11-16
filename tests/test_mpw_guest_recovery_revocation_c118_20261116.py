"""C118: owner disabling paid-guest email recovery revokes sessions/codes,
not original paid orders. Pure Django request tests: no live email, DB, RPC,
TRX transactions, migration, or customer access.
"""
from unittest.mock import patch

from django.core import signing
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, override_settings

from services import mpw_trx_email_recovery as recovery


@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "unregistered.example"])
class GuestRecoveryOwnerRevocationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def request(self, method="get", path=None, **data):
        path = path or recovery.ROOT + "verify/"
        make = getattr(self.factory, method)
        return make(path, data=data if method == "post" else None,
                    secure=True, HTTP_HOST="mojplaywin.com")

    @override_settings(MPW_GUEST_RECOVERY_ENABLED=False,
                       MPW_GUEST_RECOVERY_EMAIL_APPROVED=True)
    def test_disabled_recovery_code_get_denies_before_email_or_db(self):
        with patch.object(recovery, "_consume") as consume:
            with self.assertRaises(Http404):
                recovery.recovery_verify(self.request())
            consume.assert_not_called()

    @override_settings(MPW_GUEST_RECOVERY_ENABLED=True,
                       MPW_GUEST_RECOVERY_EMAIL_APPROVED=False)
    def test_email_permission_revoked_disables_code_post_before_consumption(self):
        request = self.request("post", code="X" * recovery.CODE_LENGTH)
        with patch.object(recovery, "_consume") as consume:
            with patch.object(recovery, "_allowed") as throttle:
                with self.assertRaises(Http404):
                    recovery.recovery_verify(request)
            consume.assert_not_called()
            throttle.assert_not_called()

    @override_settings(MPW_GUEST_RECOVERY_ENABLED=False,
                       MPW_GUEST_RECOVERY_EMAIL_APPROVED=False)
    def test_existing_signed_cookie_stops_authorizing_order_access(self):
        request = self.request(path=recovery.ROOT + "orders/")
        request.COOKIES[recovery.SESSION_COOKIE] = signing.dumps(
            {"e": "a" * 64, "n": "session"},
            salt=recovery.SESSION_SALT,
        )
        with patch.object(recovery, "_eligible_orders") as orders:
            with self.assertRaises(Http404):
                recovery.recovery_orders(request)
            orders.assert_not_called()
        with self.assertRaises(Http404):
            recovery._scope(request)

    @override_settings(MPW_GUEST_RECOVERY_ENABLED=False,
                       MPW_GUEST_RECOVERY_EMAIL_APPROVED=True)
    def test_old_session_cannot_enter_download_or_read_invoice(self):
        request = self.request(path=recovery.ROOT + "download/42/")
        request.COOKIES[recovery.SESSION_COOKIE] = signing.dumps(
            {"e": "a" * 64, "n": "session"},
            salt=recovery.SESSION_SALT,
        )
        with patch.object(recovery.PaymentIntent.objects, "select_related") as invoice:
            with self.assertRaises(Http404):
                recovery.recovery_download(request, 42)
            invoice.assert_not_called()

    @override_settings(MPW_GUEST_RECOVERY_ENABLED=True,
                       MPW_GUEST_RECOVERY_EMAIL_APPROVED=True,
                       MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED=False)
    def test_lawfully_existing_paid_recovery_is_independent_of_new_invoices(self):
        # Cancelling NEW payable invoices must not cancel a previously
        # consented recovery feature. The independent email flags own it.
        self.assertTrue(recovery._recovery_enabled())
        response = recovery.recovery_verify(self.request())
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Code from email', response.content)

    @override_settings(MPW_GUEST_RECOVERY_ENABLED=False,
                       MPW_GUEST_RECOVERY_EMAIL_APPROVED=False)
    def test_customer_request_still_has_friendly_no_repayment_hold(self):
        response = recovery.recovery_request(
            self.request(path=recovery.ROOT)
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Do not make another payment", response.content)
        self.assertNotIn(b"Request code", response.content)

    def test_non_boolean_config_values_fail_closed(self):
        for enabled, approved in (
            (1, True), ("true", True), (True, 1),
            (True, "yes"), (None, True), (False, True),
        ):
            with self.subTest(enabled=enabled, approved=approved):
                with override_settings(
                    MPW_GUEST_RECOVERY_ENABLED=enabled,
                    MPW_GUEST_RECOVERY_EMAIL_APPROVED=approved,
                ):
                    self.assertFalse(recovery._recovery_enabled())

    @override_settings(MPW_GUEST_RECOVERY_ENABLED=True,
                       MPW_GUEST_RECOVERY_EMAIL_APPROVED=True)
    def test_enabled_valid_signed_scope_is_supported_until_expiry(self):
        request = self.request(path=recovery.ROOT + "orders/")
        digest = "a" * 64
        request.COOKIES[recovery.SESSION_COOKIE] = signing.dumps(
            {"e": digest, "n": "session"},
            salt=recovery.SESSION_SALT,
        )
        self.assertEqual(recovery._scope(request), digest)

    @override_settings(MPW_GUEST_RECOVERY_ENABLED=True,
                       MPW_GUEST_RECOVERY_EMAIL_APPROVED=True)
    def test_untrusted_host_never_opens_recovery(self):
        request = self.factory.get(recovery.ROOT + "verify/", secure=True,
                                   HTTP_HOST="unregistered.example")
        with self.assertRaises(Http404):
            recovery.recovery_verify(request)


if __name__ == "__main__":
    import unittest
    unittest.main()
