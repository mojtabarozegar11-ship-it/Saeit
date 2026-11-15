"""Executable no-payment security regressions for the real Moj Prop request endpoint."""
import json
from django.test import Client, TestCase, override_settings
from core.models import MojPropRequest


class MojPropIntakeSafetyTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.token = self.client.get("/moj-prop-intake/").json()["csrf_token"]
        self.data = {
            "name": "Business buyer", "email": "buyer@example.org",
            "service": "blueprint", "horizon": "week",
            "notes": "Please scope a documented manual research deliverable.",
            "consent": True, "website": "",
        }

    def post(self, data=None, *, raw=None, **extra):
        payload = raw if raw is not None else json.dumps(self.data if data is None else data)
        return self.client.post(
            "/moj-prop-intake/", payload, content_type="application/json",
            HTTP_X_CSRFTOKEN=self.token, **extra,
        )

    def test_accepts_legitimate_lead_with_multiline_notes(self):
        data = {**self.data, "notes": "Please assess a\nmanual market research deliverable."}
        response = self.post(data)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["request_id"].startswith("MOJPROP-"))
        self.assertEqual(MojPropRequest.objects.count(), 1)
        self.assertEqual(MojPropRequest.objects.get().notes, data["notes"])
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_missing_csrf_cannot_create_request(self):
        response = Client(enforce_csrf_checks=True).post(
            "/moj-prop-intake/", json.dumps(self.data), content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_invalid_fields_do_not_write_customer_data(self):
        variations = {
            "name_type": {"name": {"unexpected": "dict"}},
            "email_type": {"email": ["buyer@example.org"]},
            "notes_type": {"notes": None},
            "route_type": {"service": 1},
            "horizon_type": {"horizon": ["week"]},
            "website_type": {"website": [""]},
            "name_overflow": {"name": "A" * 201},
            "email_overflow": {"email": "a" * 255},
            "notes_overflow": {"notes": "N" * 5001},
            "route_overflow": {"service": "s" * 31},
            "horizon_overflow": {"horizon": "w" * 21},
            "website_overflow": {"website": "x" * 121},
            "name_nul": {"name": "Buyer\\u0000Name"},
            "email_nul": {"email": "a\\u0000@example.org"},
            "name_cr": {"name": "Buyer\\rName"},
            "name_tab": {"name": "Buyer\\tName"},
            "missing_consent": {"consent": False},
            "string_consent": {"consent": "true"},
            "numeric_consent": {"consent": 1},
            "bot_honeypot": {"website": "https://spam.example"},
            "invalid_route": {"service": "live-trading"},
            "invalid_horizon": {"horizon": "never"},
            "short_notes": {"notes": "no"},
            "invalid_email": {"email": "not-an-email"},
            "short_name": {"name": "A"},
        }
        for scenario, changes in variations.items():
            with self.subTest(scenario=scenario):
                data = {**self.data, **changes}
                response = self.post(data)
                self.assertEqual(response.status_code, 400, response.content[:300])
                self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_malformed_json_variants_do_not_write(self):
        for raw in (
            "{", "null", "[]", "NaN",
            '{"name":"x","name":"y"}',
            '{"name":1e999}',
        ):
            with self.subTest(raw=raw):
                response = self.post(raw=raw)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_unknown_fields_forbidden(self):
        response = self.post({**self.data, "charge": True, "is_admin": True})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_request_size_limit_before_customer_write(self):
        response = self.post({**self.data, "notes": "A" * 17000})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_proxy_header_cannot_evade_rate_limit(self):
        for index in range(5):
            response = self.post(
                {**self.data, "email": f"customer{index}@example.org"},
                HTTP_X_REAL_IP=f"203.0.113.{index + 1}",
            )
            self.assertEqual(response.status_code, 201)
        sixth = self.post(
            {**self.data, "email": "sixth@example.org"}, HTTP_X_REAL_IP="203.0.113.99",
        )
        self.assertEqual(sixth.status_code, 429)
        self.assertEqual(sixth["Retry-After"], "600")
        self.assertEqual(MojPropRequest.objects.count(), 5)

    @override_settings(MOJPROP_TRUSTED_PROXIES=("127.0.0.1",))
    def test_explicit_trusted_proxy_can_forward_client_ip(self):
        first = self.post(self.data, REMOTE_ADDR="127.0.0.1", HTTP_X_REAL_IP="203.0.113.10")
        second = self.post(
            {**self.data, "email": "second@example.org"},
            REMOTE_ADDR="127.0.0.1", HTTP_X_REAL_IP="203.0.113.11",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(*MojPropRequest.objects.values_list("ip_hash", flat=True))

    def test_urlencoded_form_keeps_a_legitimate_non_json_intake(self):
        response = self.client.post(
            "/moj-prop-intake/",
            {**self.data, "consent": "on"},
            HTTP_X_CSRFTOKEN=self.token,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(MojPropRequest.objects.count(), 1)
