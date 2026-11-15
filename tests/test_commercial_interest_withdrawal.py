from urllib.parse import urlencode
from django.core.cache import cache
"""One-way contact revocation: real database mutation without invoices or email."""
from django.core import signing
from django.test import Client, TestCase, override_settings
from core.signal_interest_models import CommercialInterest
from core.interest_withdrawal import SALT
from core.models import Order, PaymentIntent

@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir", "evil.example"])
class WithdrawalTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()  # Per-test bounded intake limiter, never bypasses production limits.

    def post_interest(self, path, payload):
        """Browser-equivalent URL-encoded form; no multipart test-only exceptions."""
        return self.client.post(
            path, urlencode(payload), content_type="application/x-www-form-urlencoded",
            secure=True, HTTP_HOST="mojplaywin.com",
        )

    def add(self, family="signals"):
        if family == "signals":
            return CommercialInterest.objects.create(
                email="buyer@example.org", offer_family="signals", brand="saman",
                plan_code="moj-signals-standard", source_host="mojplaywin.com",
                source_language="en", consent_version="mojtaba-signals-interest-v1",
            )
        return CommercialInterest.objects.create(
            email="buyer@example.org", offer_family="moj_prop", brand="moj_prop",
            plan_code="MOJ-PROP-01", source_host="mojplaywin.com",
            source_language="fa", consent_version="moj-prop-interest-v1",
        )
    def path(self, lead):
        token = signing.dumps({"id":lead.pk, "host":lead.source_host,
                               "family":lead.offer_family}, salt=SALT)
        return "/commercial-interest/withdraw/" + token + "/"

    def test_get_is_informational_not_revocation(self):
        lead = self.add()
        response = self.client.get(self.path(lead), secure=True, HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CommercialInterest.objects.get(pk=lead.pk).status, "new")
        self.assertContains(response, 'method="post"')
        self.assertNotContains(response, "buyer@example.org")
        self.assertIn("no-store", response["Cache-Control"])

    def test_post_is_real_irreversible_withdrawal(self):
        lead = self.add()
        url = self.path(lead)
        result = self.client.post(url, {"csrfmiddlewaretoken":"browser-managed"},
                                  secure=True, HTTP_HOST="mojplaywin.com")
        self.assertEqual(result.status_code, 200)
        lead.refresh_from_db()
        self.assertEqual(lead.status, "withdrawn")
        self.assertIsNotNone(lead.withdrawn_at)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(PaymentIntent.objects.count(), 0)
        self.assertEqual(self.client.post(url, {"csrfmiddlewaretoken":"browser-managed"},
                            secure=True, HTTP_HOST="mojplaywin.com").status_code, 200)

    def test_other_offer_family_remains_untouched(self):
        a, b = self.add(), self.add("moj_prop")
        self.client.post(self.path(a), {"csrfmiddlewaretoken":"browser-managed"},
                         secure=True, HTTP_HOST="mojplaywin.com")
        self.assertEqual(CommercialInterest.objects.get(pk=a.pk).status, "withdrawn")
        self.assertEqual(CommercialInterest.objects.get(pk=b.pk).status, "new")

    def test_foreign_host_http_and_www_alias_refused(self):
        lead = self.add()
        path = self.path(lead)
        for host,secure in (("evil.example",True),("mojplaywin.com",False),
                            ("www.mojplaywin.com",True)):
            with self.subTest(host=host, secure=secure):
                self.assertEqual(self.client.get(path,HTTP_HOST=host,secure=secure).status_code,404)
        self.assertEqual(CommercialInterest.objects.get(pk=lead.pk).status, "new")

    def test_tampered_signed_payload_rejected(self):
        lead = self.add()
        path = self.path(lead)
        signature = path.split("/")[-2]
        altered = path.replace(signature, signature+"X")
        self.assertEqual(self.client.post(altered, {"csrfmiddlewaretoken":"browser-managed"},
                         secure=True, HTTP_HOST="mojplaywin.com").status_code,404)

    def test_csrf_required_to_write(self):
        lead = self.add()
        browser = Client(enforce_csrf_checks=True)
        self.assertEqual(browser.post(self.path(lead), {}, secure=True,
                                      HTTP_HOST="mojplaywin.com").status_code, 403)
        self.assertEqual(CommercialInterest.objects.get(pk=lead.pk).status, "new")

    def test_unexpected_post_fields_fail_closed(self):
        lead = self.add()
        response=self.client.post(self.path(lead), {"email":"buyer@example.org"},
                                  secure=True, HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(CommercialInterest.objects.get(pk=lead.pk).status,"new")

    def test_localized_moj_prop_can_withdraw(self):
        lead = self.add("moj_prop")
        response=self.client.get(self.path(lead), secure=True, HTTP_HOST="mojplaywin.com")
        self.assertContains(response, "لغو رضایت تماس")
        self.assertContains(response, 'dir="rtl"')

    def test_signal_interest_confirmation_exposes_revocation_link(self):
        body={"email":"Buyer@Example.org", "brand":"saman", "plan_code":"moj-signals-standard",
              "source_language":"en", "contact_consent":"yes",
              "consent_version":"mojtaba-signals-interest-v1", "csrfmiddlewaretoken":"browser-managed"}
        response=self.post_interest("/market-signals/interest/", body)
        self.assertEqual(response.status_code, 202)
        self.assertContains(response, "Withdraw contact consent", status_code=202)
        self.assertIn("commercial-interest/withdraw/",response.content.decode())

    def test_prop_interest_confirmation_exposes_revocation_link(self):
        body={"email":"Buyer@Example.org","plan_code":"MOJ-PROP-01","source_language":"fa",
              "contact_consent":"yes","consent_version":"moj-prop-interest-v1",
              "csrfmiddlewaretoken":"browser-managed"}
        response=self.post_interest("/moj-prop/interest/", body)
        self.assertEqual(response.status_code,202)
        self.assertContains(response,"لغو رضایت تماس",status_code=202)

    def test_repeat_signal_intake_cannot_reissue_revocation_bearer(self):
        payload = {"email": "Buyer@Example.org", "brand": "saman",
                   "plan_code": "moj-signals-standard", "source_language": "en",
                   "contact_consent": "yes", "consent_version": "mojtaba-signals-interest-v1",
                   "csrfmiddlewaretoken": "browser-managed"}
        first = self.post_interest("/market-signals/interest/", payload)
        self.assertIn("commercial-interest/withdraw/", first.content.decode())
        second = self.post_interest("/market-signals/interest/", payload)
        self.assertEqual(second.status_code, 202)
        self.assertNotIn("commercial-interest/withdraw/", second.content.decode())
        self.assertEqual(CommercialInterest.objects.count(), 1)

    def test_repeat_prop_intake_cannot_reissue_revocation_bearer(self):
        payload = {"email": "Buyer@Example.org", "plan_code": "MOJ-PROP-01",
                   "source_language": "fa", "contact_consent": "yes",
                   "consent_version": "moj-prop-interest-v1",
                   "csrfmiddlewaretoken": "browser-managed"}
        first = self.post_interest("/moj-prop/interest/", payload)
        self.assertIn("commercial-interest/withdraw/", first.content.decode())
        second = self.post_interest("/moj-prop/interest/", payload)
        self.assertEqual(second.status_code, 202)
        self.assertNotIn("commercial-interest/withdraw/", second.content.decode())
        self.assertEqual(CommercialInterest.objects.count(), 1)
