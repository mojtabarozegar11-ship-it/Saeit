"""CSRF protection is part of the buyer conversion gate, not optional JS."""
import json
from django.test import Client, TestCase, override_settings
from core.models import MojPropRequest, MojPropRateBucket


URL="/moj-prop-intake/"
BUYER={"name":"Interested Visitor","email":"buyer@example.org",
       "service":"blueprint","horizon":"week",
       "notes":"I request a written educational service quote, please.",
       "consent":True,"website":""}


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com"])
class MojPropC67CsrfTests(TestCase):
    def setUp(self):
        self.browser=Client(enforce_csrf_checks=True)

    def test_post_without_csrf_rejected_before_any_database_write(self):
        response=self.browser.post(URL, data=json.dumps(BUYER),
                                   content_type="application/json",
                                   REMOTE_ADDR="127.0.0.9")
        self.assertEqual(response.status_code,403)
        self.assertFalse(MojPropRequest.objects.exists())
        self.assertFalse(MojPropRateBucket.objects.exists())

    def test_public_get_provides_a_token_without_recording_buyer(self):
        response=self.browser.get(URL,REMOTE_ADDR="127.0.0.9")
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()["csrf_token"])
        self.assertFalse(MojPropRequest.objects.exists())

    def test_valid_same_origin_csrf_creates_one_manual_review_lead(self):
        response=self.browser.get(URL,REMOTE_ADDR="127.0.0.9")
        csrf=response.json()["csrf_token"]
        posted=self.browser.post(URL,data=json.dumps(BUYER),
                                 content_type="application/json",
                                 REMOTE_ADDR="127.0.0.9",
                                 HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(posted.status_code,201)
        self.assertTrue(posted.json()["request_id"].startswith("MOJPROP-"))
        self.assertEqual(MojPropRequest.objects.count(),1)

    def test_wrong_csrf_token_rejected_without_spending_quota(self):
        self.browser.get(URL)
        r=self.browser.post(URL,data=json.dumps(BUYER),
                            content_type="application/json",
                            HTTP_X_CSRFTOKEN="a"*64)
        self.assertEqual(r.status_code,403)
        self.assertFalse(MojPropRateBucket.objects.exists())

    def test_get_does_not_create_payment_or_inquiry_even_with_consent_data(self):
        self.browser.get(URL,{"email":BUYER["email"],"consent":"yes"})
        self.assertFalse(MojPropRequest.objects.exists())
