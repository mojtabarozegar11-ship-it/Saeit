"""Commercial conversion regression for the ACTUAL Moj Prop root Passenger route."""
import json
import re
from pathlib import Path

from django.conf import settings
from django.test import Client, TestCase
from django.urls import resolve, reverse

from core.models import MojPropRequest
from core.mojprop_views import mojprop_intake


class MojPropActualFormContractTests(TestCase):
    def test_public_horizon_option_values_are_backend_model_codes(self):
        html = (Path(settings.BASE_DIR) / "templates/moj-prop-v4/index.html").read_text("utf-8")
        select = re.search(r'<select id="horizon">(.*?)</select>', html)
        self.assertIsNotNone(select)
        options = re.findall(r'<option value="([^"]+)">([^<]+)</option>', select.group(1))
        self.assertEqual(options, list(MojPropRequest.HORIZON_CHOICES))
        self.assertIn("const endpoint='/moj-prop-intake/';", html)

    def test_root_wsgi_path_resolves_to_actual_service(self):
        self.assertEqual(reverse("mojprop_intake"), "/moj-prop-intake/")
        self.assertIs(resolve("/moj-prop-intake/").func, mojprop_intake)

    def test_all_four_real_browser_values_create_recoverable_manual_leads(self):
        browser = Client(enforce_csrf_checks=True)
        token = browser.get("/moj-prop-intake/").json()["csrf_token"]
        for index, (value, label) in enumerate(MojPropRequest.HORIZON_CHOICES, start=1):
            with self.subTest(label=label):
                payload = {
                    "name": "Real browser integration",
                    "email": f"buyer{index}@mail-demo.org",
                    "service": "blueprint", "horizon": value,
                    "notes": "Please scope a written educational proposal and delivery.",
                    "consent": True, "website": "",
                }
                response = browser.post(
                    "/moj-prop-intake/", data=json.dumps(payload),
                    content_type="application/json", HTTP_X_CSRFTOKEN=token,
                )
                self.assertEqual(response.status_code, 201, response.content[:300])
                self.assertTrue(response.json()["request_id"].startswith("MOJPROP-"))
                record = MojPropRequest.objects.get(request_id=response.json()["request_id"])
                self.assertEqual(record.horizon, value)
                self.assertEqual(record.status, "new")
                self.assertTrue(record.consent)
        self.assertEqual(MojPropRequest.objects.count(), 4)
