"""C19 existing public company sales intake: consent, six real scopes, no shadow bot."""
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from core.company_inquiry_models import CompanyInquiry

SCOPES=("AGR-01","RS-01","RS-02","RS-03","WEB-01","SEO-01")


@override_settings(ALLOWED_HOSTS=["testserver","mojplaywin.com","zomorodmelal.ir"])
class C19CompanyConversionTests(TestCase):
    def data(self):
        return {
            "kind":"commercial",
            "name":"Prospective Partner",
            "organization":"Example Cooperative",
            "email":"sales@example.org",
            "phone":"",
            "subject":"Greenhouse economic scope",
            "message":"I would like to discuss one defined greenhouse cost question.",
            "privacy_consent":"on",
            "website":"",
        }

    def test_six_public_scope_routes_discoverable_from_existing_django_hub(self):
        response=self.client.get(reverse("services"),HTTP_HOST="zomorodmelal.ir")
        self.assertEqual(response.status_code,200)
        html=response.content.decode("utf-8")
        for code in SCOPES:
            self.assertEqual(html.count('href="/services/scope/'+code+'/"'),1)
        self.assertIn('id="c19-six-service-scopes"',html)
        self.assertIn("توافق جداگانه",html)

    def test_mojplaywin_services_host_is_not_given_company_sales_links(self):
        response=self.client.get(reverse("services"),HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code,200)
        self.assertNotIn(b'c19-six-service-scopes',response.content)

    def test_company_form_has_explicit_unchecked_privacy_optin(self):
        html=self.client.get(reverse("company")).content.decode("utf-8")
        self.assertIn('type="checkbox" name="privacy_consent"',html)
        self.assertIn('name="website"',html)
        self.assertIn("اصلاح یا حذف داده",html)
        self.assertNotIn('name="privacy_consent" checked',html)

    def test_only_consented_original_db_records_are_created(self):
        for consent in ("","false"):
            data=self.data()
            data["privacy_consent"]=consent
            response=self.client.post(reverse("company"),data=data)
            self.assertEqual(response.status_code,302)
            self.assertFalse(CompanyInquiry.objects.exists())
        valid=self.data()
        response=self.client.post(reverse("company"),data=valid)
        self.assertEqual(response.status_code,302)
        self.assertEqual(CompanyInquiry.objects.count(),1)
        self.assertIn("C19_PRIVACY_CONSENT_V1",CompanyInquiry.objects.get().internal_note)

    def test_duplicate_guard_does_not_block_distinct_subject(self):
        data=self.data()
        for _ in range(2):
            self.client.post(reverse("company"),data=data)
        self.assertEqual(CompanyInquiry.objects.count(),1)
        data["subject"]="New and distinct enquiry"
        self.client.post(reverse("company"),data=data)
        self.assertEqual(CompanyInquiry.objects.count(),2)

    def test_no_autosending_in_main_company_view_source(self):
        import inspect
        from core.company_content_views import company_portal_home
        source=inspect.getsource(company_portal_home)
        self.assertNotIn("send_mail(",source)
        self.assertNotIn("requests.post(",source)
        self.assertNotIn("order.save(",source)

    def test_real_csrf_guard_still_rejects_unauthenticated_post(self):
        public=Client(enforce_csrf_checks=True)
        response=public.post(reverse("company"),data=self.data())
        self.assertEqual(response.status_code,403)
        self.assertFalse(CompanyInquiry.objects.exists())


    def test_six_optional_email_links_only_open_buyer_mail_app(self):
        html=self.client.get(reverse("services"),HTTP_HOST="zomorodmelal.ir").content.decode("utf-8")
        for code in SCOPES:
            self.assertIn(
                "mailto:zomorodmelal@gmail.com?subject=Service%20inquiry%20"+code,
                html,
            )
        self.assertEqual(html.count('class="c19-email-alternative"'),6)
        self.assertNotIn("mailto:zomorodmelal@gmail.com?body=",html)
        self.assertIn("هیچ پیام خودکاری ارسال نمی‌شود",html)

    def test_valid_receipt_returns_to_same_form_and_does_not_claim_paid_service(self):
        response=self.client.post(reverse("company"),data=self.data())
        self.assertEqual(response.status_code,302)
        self.assertTrue(response["Location"].endswith("#company-request"))
        self.assertEqual(CompanyInquiry.objects.count(),1)
        self.assertEqual(CompanyInquiry.objects.get().status,"new")
