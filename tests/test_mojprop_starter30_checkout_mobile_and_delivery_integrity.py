"""Offline Starter30 buyer UX and truthful fulfilment event regression.

Does not send any POST, native TRX, email, payment, customer data or DB write.
"""
from pathlib import Path
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from prop_firm.starter30_views import _buyer_portal_link

ROOT = Path(__file__).resolve().parents[1]
CHECKOUT = ROOT / "prop_firm/starter30_views.py"
OPEN = {
    "MPW_MOJPROP_DB_ALIAS_ENABLED": True,
    "MPW_MOJPROP_DEPLOYMENT_ENV": "production",
    "MPW_MOJPROP_PRODUCTION_RELEASE_APPROVED": True,
    "MPW_MOJPROP_TRX_RELEASE_ENABLED": True,
    "MPW_MOJPROP_TRX_RPC_ATTESTED": True,
    "MPW_MOJPROP_SELLER_ELIGIBILITY_VERIFIED": True,
    "MPW_MOJPROP_INVOICE_CUSTODY_VERIFIED": True,
    "MPW_MOJPROP_REWARD_RESERVE_VERIFIED": True,
    "MPW_MOJPROP_REWARD_SETTLEMENT_RAIL_VERIFIED": True,
    "MPW_MOJPROP_DELIVERY_RECOVERY_VERIFIED": True,
}
PORTAL_FLAGS = {
    "MPW_MOJPROP_BUYER_PORTAL_APPROVED": True,
    "MPW_MOJPROP_BUYER_TRANSACTIONAL_EMAIL_APPROVED": True,
    "MPW_MOJPROP_BUYER_SHARED_RATE_LIMIT_VERIFIED": True,
    "MPW_MOJPROP_BUYER_DELIVERY_RECOVERY_VERIFIED": True,
}


class Starter30LiveMobileAndDeliveryIntegrityTests(SimpleTestCase):
    @override_settings(**OPEN)
    def test_get_has_normal_checkbox_and_full_disclosure_links(self):
        with patch("prop_firm.starter30_views.verify_pre_invoice_configuration"):
            with patch("prop_firm.starter30_views._record_funnel_event") as telemetry:
                response = self.client.get("/mojprop-starter30-checkout/")
        self.assertEqual(response.status_code, 200)
        page = response.content.decode()
        self.assertIn("input:not([type=checkbox])", page)
        self.assertIn("input[type=checkbox]{width:auto;", page)
        # Unverified browsers must not be offered a payable invoice form.
        self.assertIn("name='action' value='request_email_code'", page)
        self.assertIn("Email a one-time verification code", page)
        self.assertNotIn("name='terms' value='yes' required", page)
        self.assertIn("name='email' type='email' required", page)
        self.assertNotIn("name='payer_address'", page)
        self.assertNotIn("Create 30 TRX invoice", page)
        # The gated verified-mail step still has a mobile terms checkbox,
        # risk/rules disclosures and optional payer wallet.
        from prop_firm.starter30_views import _form
        from django.test import RequestFactory
        gated = _form(RequestFactory().get("/mojprop-starter30-checkout/"))
        self.assertIn("name='terms' value='yes' required", gated)
        self.assertIn("href='/moj-prop/rules/'", gated)
        self.assertIn("href='/moj-prop/payment/'", gated)
        self.assertIn("name='payer_address'", gated)
        self.assertIn("Create 30 TRX invoice", gated)
        self.assertNotIn("href='/mojprop-buyer-portal/'", page)
        telemetry.assert_called_once()

    def test_private_buyer_account_link_never_bypasses_owner_hold(self):
        with override_settings(**PORTAL_FLAGS):
            self.assertIn("/mojprop-buyer-portal/", _buyer_portal_link())
        for flag in PORTAL_FLAGS:
            with self.subTest(flag=flag):
                with override_settings(**{**PORTAL_FLAGS, flag: False}):
                    self.assertEqual(_buyer_portal_link(), "")

    def test_payment_is_not_misreported_as_educational_delivery(self):
        src = CHECKOUT.read_text(encoding="utf8")
        self.assertIn('_record_funnel_event(request, "payment_confirmed")', src)
        self.assertNotIn('_record_funnel_event(request, "delivery_success")', src)
        self.assertIn("Do not manufacture delivery_success", src)
        self.assertIn("settle_invoice(", src)
        self.assertIn("_buyer_portal_link()", src)
        self.assertNotIn("send_mail(", src)
        self.assertNotIn("triggerSmartContract(", src)


if __name__ == "__main__":
    import unittest
    unittest.main()
