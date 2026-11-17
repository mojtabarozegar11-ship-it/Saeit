"""CSRF validation survives misconfigured global middleware in a hosted deployment."""
import json

from django.conf import settings
from django.test import Client, TestCase, override_settings

from core.models import MojPropRequest


@override_settings(MIDDLEWARE=[
    x for x in settings.MIDDLEWARE if x != "django.middleware.csrf.CsrfViewMiddleware"
])
class MojPropDirectCsrfProtectionTests(TestCase):
    def test_missing_csrf_token_rejected_even_without_global_middleware(self):
        client = Client(enforce_csrf_checks=True)
        body = {
            "name": "CSRF Client", "email": "csrf@sample.org",
            "service": "brief", "horizon": "review",
            "notes": "Please provide scoped educational research on market drivers.",
            "consent": True, "website": "",
        }
        response = client.post(
            "/moj-prop-intake/", data=json.dumps(body), content_type="application/json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_valid_csrf_token_can_send_a_bounded_request(self):
        client = Client(enforce_csrf_checks=True)
        token = client.get("/moj-prop-intake/").json()["csrf_token"]
        data = {
            "name": "CSRF Client", "email": "csrf@sample.org",
            "service": "brief", "horizon": "review",
            "notes": "Please provide scoped educational research on market drivers.",
            "consent": True, "website": "",
        }
        response = client.post(
            "/moj-prop-intake/", data=json.dumps(data),
            content_type="application/json", HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(MojPropRequest.objects.count(), 1)
