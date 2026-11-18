"""Django test suite for the actual Zomorod B2B inquiry route and receipt."""
from django.core import mail, signing
from django.test import Client, TestCase, override_settings
from core.company_inquiry_models import CompanyInquiry

class B2BTrustTests(TestCase):
    def payload(self):
        return {"kind":"commercial", "name":"Buyer Person", "organization":"Vendor Inc.",
                "email":"buyer@example.org", "subject":"OEM quotation",
                "message":"Please send your product catalogue and lead times."}

    def test_public_pages_and_links(self):
        for url in ("/", "/company/", "/en/partners/", "/privacy/"):
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertContains(self.client.get("/"), "/en/partners/")
        self.assertContains(self.client.get("/company/"), "/company/inquiry/")
        self.assertContains(self.client.get("/en/partners/"), 'lang="en"')

    def test_real_record_and_private_receipt(self):
        response = self.client.post("/company/inquiry/", self.payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CompanyInquiry.objects.count(), 1)
        receipt = self.client.get(response["Location"])
        self.assertEqual(receipt.status_code, 200)
        self.assertContains(receipt, "ZM-")
        self.assertNotContains(receipt, "buyer@example.org")
        self.assertEqual(receipt["Cache-Control"], "private, no-store")
        self.assertEqual(receipt["X-Robots-Tag"], "noindex, nofollow")

    def test_old_company_form_receipt(self):
        response = self.client.post("/company/", self.payload())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/company/inquiry/receipt/", response["Location"])

    def test_validation_and_honeypot(self):
        invalid = self.payload()
        invalid["email"] = "invalid"
        self.assertEqual(self.client.post("/company/inquiry/", invalid).status_code, 400)
        spam = self.payload()
        spam["company_url"] = "spam-url"
        self.assertEqual(self.client.post("/company/inquiry/", spam).status_code, 400)
        self.assertEqual(CompanyInquiry.objects.count(), 0)

    def test_no_unsigned_receipt_or_get_form(self):
        self.assertEqual(self.client.get("/company/inquiry/").status_code, 405)
        self.assertEqual(self.client.get("/company/inquiry/receipt/forged/").status_code, 404)
        token = signing.dumps({"id":123999},salt="zomorod-b2b-receipt-v1")
        self.assertEqual(self.client.get("/company/inquiry/receipt/"+token+"/").status_code,404)

    def test_csrf_required(self):
        self.assertEqual(Client(enforce_csrf_checks=True).post("/company/inquiry/", self.payload()).status_code,403)

    def test_english_receipt(self):
        data = self.payload()
        data["language"] = "en"
        response = self.client.post("/company/inquiry/",data)
        self.assertIn("?lang=en",response["Location"])
        self.assertContains(self.client.get(response["Location"]),"Inquiry received")

    @override_settings(
        COMPANY_INQUIRY_NOTIFICATION_ENABLED=True,
        COMPANY_TRADE_EMAIL="zomorodmelal@gmail.com",
        DEFAULT_FROM_EMAIL="zomorodmelal@gmail.com",
        EMAIL_HOST="smtp.example.invalid",
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_internal_email_only_when_configured(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post("/company/inquiry/",self.payload())
        self.assertEqual(len(mail.outbox),1)
        self.assertEqual(mail.outbox[0].to,["zomorodmelal@gmail.com"])
        self.assertNotIn("buyer@example.org",mail.outbox[0].body)

    def test_notification_disabled_by_default(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post("/company/inquiry/",self.payload())
        self.assertEqual(len(mail.outbox),0)
