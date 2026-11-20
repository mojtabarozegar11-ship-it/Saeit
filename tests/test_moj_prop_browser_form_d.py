"""D integration: browser-native root Plan1 lead form, not a checkout.

All HTTP clients and users are synthetic isolated CI fixtures. No true buyer,
email delivery, wallet transfer, broker trading, or live deployment.
"""
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings

from core.models import Order, PaymentIntent
from prop_firm.models import PropInterest, PropAccount, PropChallengeEnrollment

@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"])
class NonJSPlanOneFormTests(TestCase):
    GET = "/moj-prop-interest/form/"
    POST = "/moj-prop-interest/"
    DATA = {
        "email": "genuine-test-buyer@farmco.org",
        "plan_code": "MOJ-PROP-01",
        "contact_consent": "yes",
        "consent_version": "moj-prop-interest-v1",
        "source_language": "en",
    }

    def get(self, url=None, *, host="mojplaywin.com", secure=True, client=None):
        return (client or self.client).get(
            url or self.GET, secure=secure, HTTP_HOST=host,
        )

    def post(self, data=None, *, host="mojplaywin.com", secure=True, client=None):
        return (client or self.client).post(
            self.POST,
            data=urlencode(self.DATA if data is None else data),
            secure=secure, HTTP_HOST=host,
            HTTP_REFERER=("https://" if secure else "http://") +
                         host + self.GET,
            content_type="application/x-www-form-urlencoded",
        )

    def test_01_https_plan1_form_is_rendered(self):
        r=self.get()
        self.assertEqual(r.status_code,200)
        self.assertContains(r,"MOJ-PROP-01")

    def test_02_www_hostname_is_valid(self):
        self.assertEqual(self.get(host="www.mojplaywin.com").status_code,200)

    def test_03_http_is_not_a_legal_or_secure_lead_channel(self):
        self.assertEqual(self.get(secure=False).status_code,404)

    def test_04_other_company_host_rejected(self):
        self.assertEqual(self.get(host="zomorodmelal.ir").status_code,404)

    def test_05_form_view_post_cannot_mutate(self):
        response=self.client.post(self.GET, data=self.DATA,
                                  secure=True,HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code,405)
        self.assertEqual(PropInterest.objects.count(),0)

    def test_06_exact_plan1_form_action_root_wsgi(self):
        html=self.get().content.decode("utf-8")
        self.assertIn('action="/moj-prop-interest/"',html)
        self.assertNotIn('action="/moj-prop/interest/"',html)

    def test_07_form_is_plain_browser_native_post(self):
        html=self.get().content.decode("utf-8")
        self.assertIn('method="post"',html)
        self.assertNotIn("<script",html.lower())

    def test_08_csrf_token_is_present(self):
        self.assertContains(self.get(),"csrfmiddlewaretoken")

    def test_09_contact_consent_is_required_and_explicit(self):
        html=self.get().content.decode("utf-8")
        self.assertIn('name="contact_consent" value="yes" required',html)

    def test_10_required_email_not_prepoulated_from_query(self):
        html=self.get().content.decode("utf-8")
        self.assertIn('name="email" type="email"',html)
        self.assertNotIn('value="genuine-test-buyer@farmco.org"',html)

    def test_11_only_plan_one_can_be_requested(self):
        html=self.get().content.decode("utf-8")
        self.assertIn('name="plan_code" value="MOJ-PROP-01"',html)
        self.assertNotIn("MOJ-PROP-02",html)

    def test_12_educational_starter_never_presented_as_product(self):
        self.assertNotContains(self.get(),"MOJPROP-STARTER30")

    def test_13_contract_is_not_a_real_capital_promise(self):
        html=self.get().content.decode("utf-8")
        self.assertIn("independently verified corporate capital",html)
        self.assertIn("simulated evaluation stages",html)

    def test_14_no_wallet_or_pay_button_is_present(self):
        html=self.get().content.decode("utf-8").lower()
        self.assertIn("no payment",html)
        self.assertNotIn('name="wallet"',html)
        self.assertNotIn('action="/moj-prop/pay',html)

    def test_15_en_localization_is_left_to_right(self):
        self.assertContains(self.get(),'<html lang="en" dir="ltr">',html=False)

    def test_16_fa_localization_is_right_to_left(self):
        self.assertContains(self.get(self.GET+"?lang=fa"),'<html lang="fa" dir="rtl">',html=False)

    def test_17_ar_localization_is_right_to_left(self):
        self.assertContains(self.get(self.GET+"?lang=ar"),'<html lang="ar" dir="rtl">',html=False)

    def test_18_de_localization_is_left_to_right(self):
        self.assertContains(self.get(self.GET+"?lang=de"),'<html lang="de" dir="ltr">',html=False)

    def test_19_unknown_locale_rejected(self):
        self.assertEqual(self.get(self.GET+"?lang=javascript").status_code,400)

    def test_20_duplicate_locale_parameter_rejected(self):
        self.assertEqual(self.get(self.GET+"?lang=en&lang=fa").status_code,400)

    def test_21_unsolicited_email_query_parameter_rejected(self):
        self.assertEqual(self.get(self.GET+"?email=someone%40mail.org").status_code,400)

    def test_22_private_no_store_cache_referrer_policy(self):
        r=self.get()
        self.assertIn("no-store",r["Cache-Control"])
        self.assertEqual(r["Referrer-Policy"],"same-origin")
        self.assertIn("Cookie",r.get("Vary",""))

    def test_23_csp_prevents_external_submission_scripts_frames(self):
        r=self.get()
        self.assertIn("form-action 'self'",r["Content-Security-Policy"])
        self.assertIn("default-src 'none'",r["Content-Security-Policy"])
        self.assertEqual(r["X-Frame-Options"],"DENY")

    def test_24_get_has_no_customer_transaction_or_email_effect(self):
        self.get()
        self.assertEqual(PropInterest.objects.count(),0)
        self.assertEqual(Order.objects.count(),0)
        self.assertEqual(PaymentIntent.objects.count(),0)
        self.assertEqual(PropChallengeEnrollment.objects.count(),0)
        self.assertEqual(PropAccount.objects.count(),0)
        self.assertEqual(len(mail.outbox),0)

    def test_25_post_without_csrf_is_forbidden(self):
        client=Client(enforce_csrf_checks=True)
        response=self.post(client=client)
        self.assertEqual(response.status_code,403)
        self.assertEqual(PropInterest.objects.count(),0)

    def test_26_real_browser_get_then_post_persists_only_opted_in_interest(self):
        client=Client(enforce_csrf_checks=True)
        r=self.get(client=client)
        self.assertEqual(r.status_code,200)
        csrf=client.cookies["csrftoken"].value
        response=self.post(data={**self.DATA,"csrfmiddlewaretoken":csrf},client=client)
        self.assertEqual(response.status_code,202)
        prospect=PropInterest.objects.get()
        self.assertEqual(prospect.email,"genuine-test-buyer@farmco.org")
        self.assertEqual(prospect.plan_code,"MOJ-PROP-01")
        self.assertEqual(prospect.consent_version,"moj-prop-interest-v1")
        self.assertEqual(Order.objects.count(),0)
        self.assertEqual(PaymentIntent.objects.count(),0)
        self.assertEqual(PropChallengeEnrollment.objects.count(),0)
        self.assertEqual(len(mail.outbox),0)

    def test_27_no_opt_in_consent_means_no_customer_record(self):
        payload=dict(self.DATA)
        payload["contact_consent"]="no"
        self.assertEqual(self.post(payload).status_code,400)
        self.assertEqual(PropInterest.objects.count(),0)

    def test_28_wrong_real_plan_cannot_create_interest(self):
        payload=dict(self.DATA)
        payload["plan_code"]="MOJ-PROP-02"
        self.assertEqual(self.post(payload).status_code,400)
        self.assertEqual(PropInterest.objects.count(),0)

    def test_29_invalid_reserved_email_cannot_inflate_first_buyer(self):
        payload=dict(self.DATA)
        payload["email"]="demo@example.com"
        self.assertEqual(self.post(payload).status_code,400)
        self.assertEqual(PropInterest.objects.count(),0)

    def test_30_repeated_request_does_not_create_second_prospect(self):
        self.assertEqual(self.post().status_code,202)
        self.assertEqual(self.post().status_code,202)
        self.assertEqual(PropInterest.objects.count(),1)

    def test_31_wrong_host_post_is_rejected(self):
        self.assertEqual(self.post(host="zomorodmelal.ir").status_code,404)
        self.assertEqual(PropInterest.objects.count(),0)

    def test_32_wrong_protocol_post_is_rejected(self):
        self.assertEqual(self.post(secure=False).status_code,404)
        self.assertEqual(PropInterest.objects.count(),0)

    def test_33_form_html_is_not_indexed_and_not_cached(self):
        r=self.get()
        self.assertIn("noindex",r["X-Robots-Tag"])
        self.assertEqual(r["X-Content-Type-Options"],"nosniff")
        self.assertEqual(r["Pragma"],"no-cache")

    def test_34_unexpected_product_parameter_rejected(self):
        self.assertEqual(self.get(self.GET+"?sku=MOJPROP-STARTER30").status_code,400)

    def test_35_unexpected_identity_and_language_mix_rejected(self):
        self.assertEqual(self.get(self.GET+"?lang=fa&email=test%40mail.org").status_code,400)
