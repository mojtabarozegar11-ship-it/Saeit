"""MOJ PROP Plan 1 can collect genuine leads without exposing paid checkout."""
from django.core import mail
from django.test import Client, TestCase, override_settings
from prop_firm.models import PropInterest

@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com"])
class PropInterestIntakeTests(TestCase):
    PATH="/moj-prop/interest/"
    VALID={
        "email":"Buyer@Example.com", "plan_code":"MOJ-PROP-01",
        "consent_version":"moj-prop-interest-v1", "contact_consent":"yes",
    }
    def post(self, data=None, secure=True, host="mojplaywin.com"):
        return self.client.post(self.PATH, data or self.VALID,
                                secure=secure, HTTP_HOST=host)

    def test_real_post_records_exact_plan_without_invoice(self):
        response=self.post()
        self.assertEqual(response.status_code,202)
        lead=PropInterest.objects.get()
        self.assertEqual(lead.email,"buyer@example.com")
        self.assertEqual(lead.plan_code,"MOJ-PROP-01")
        self.assertEqual(lead.status,"new")
        self.assertEqual(response["Cache-Control"],"private, no-store")
        from core.models import Order, PaymentIntent
        from prop_firm.models import PropAccount, PropChallengeEnrollment
        self.assertEqual(Order.objects.count(),0)
        self.assertEqual(PaymentIntent.objects.count(),0)
        self.assertEqual(PropAccount.objects.count(),0)
        self.assertEqual(PropChallengeEnrollment.objects.count(),0)
        self.assertEqual(len(mail.outbox),0)

    def test_duplicate_request_is_idempotent(self):
        self.assertEqual(self.post().status_code,202)
        duplicate=dict(self.VALID,email="buyer@example.com")
        self.assertEqual(self.post(duplicate).status_code,202)
        self.assertEqual(PropInterest.objects.count(),1)

    def test_consent_and_plan_rejections(self):
        for name, value in (
            ("contact_consent","no"), ("plan_code","MOJ-PROP-02"),
            ("plan_code","MOJ-PROP-10"), ("consent_version","bad"),
            ("email","not-an-email")
        ):
            with self.subTest(name=name,value=value):
                data={**self.VALID,name:value}
                self.assertEqual(self.post(data).status_code,400)
        self.assertEqual(PropInterest.objects.count(),0)

    def test_secure_host_required(self):
        self.assertEqual(self.post(secure=False).status_code,404)
        self.assertEqual(self.post(host="zomorodmelal.ir").status_code,400)
        self.assertEqual(PropInterest.objects.count(),0)

    def test_get_never_mutates(self):
        response=self.client.get(self.PATH,secure=True,HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code,405)
        self.assertEqual(PropInterest.objects.count(),0)

    def test_csrf_protects_real_guest_submission(self):
        client=Client(enforce_csrf_checks=True)
        response=client.post(self.PATH,self.VALID,secure=True,HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code,403)
        self.assertEqual(PropInterest.objects.count(),0)

    def test_form_contains_real_application_endpoint_but_no_payment_button(self):
        response=self.client.get("/moj-prop/",HTTP_HOST="mojplaywin.com",secure=True)
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'action="/moj-prop/interest/"')
        self.assertContains(response,"No order or TRX invoice is created")
