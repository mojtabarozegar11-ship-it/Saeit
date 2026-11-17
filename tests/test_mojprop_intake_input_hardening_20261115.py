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
            "name_nul": {"name": "Buyer" + chr(0) + "Name"},
            "email_nul": {"email": "a" + chr(0) + "@example.org"},
            "name_cr": {"name": "Buyer" + chr(13) + "Name"},
            "name_tab": {"name": "Buyer" + chr(9) + "Name"},
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


    def test_multipart_duplicate_form_fields_rejected_without_database_write(self):
        from django.http import QueryDict
        from django.test.client import MULTIPART_CONTENT, BOUNDARY, encode_multipart
        data = {**self.data, "consent": "on"}
        encoded = encode_multipart(BOUNDARY, data)
        needle = b'Content-Disposition: form-data; name="email"'
        self.assertIn(needle, encoded)
        # Duplicate email fields must be rejected rather than trusting the last.
        duplicate = (b'--' + BOUNDARY.encode() + b'\r\n' +
                     b'Content-Disposition: form-data; name="email"\r\n\r\n' +
                     b'attacker@example.org\r\n')
        crafted = encoded.replace(
            b'--' + BOUNDARY.encode() + b'--',
            duplicate + b'--' + BOUNDARY.encode() + b'--', 1,
        )
        response = self.client.generic(
            "POST", "/moj-prop-intake/", crafted, content_type=MULTIPART_CONTENT,
            HTTP_X_CSRFTOKEN=self.token,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_multipart_file_attachment_not_accepted_as_lead(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        data = {**self.data, "consent": "on",
                "attachment": SimpleUploadedFile("sensitive.txt", b"do not store")}
        response = self.client.post("/moj-prop-intake/", data,
                                    HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_urlencoded_form_keeps_a_legitimate_non_json_intake(self):
        response = self.client.post(
            "/moj-prop-intake/",
            {**self.data, "consent": "on"},
            HTTP_X_CSRFTOKEN=self.token,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_browser_form_digital_sku_is_accepted_and_persisted(self):
        data = {**self.data, "service": "digital", "product_id": "72", "consent": "on"}
        response = self.client.post(
            "/moj-prop-intake/", data, HTTP_X_CSRFTOKEN=self.token,
        )
        self.assertEqual(response.status_code, 201, response.content[:300])
        lead = MojPropRequest.objects.get()
        self.assertEqual(lead.product_id, 72)
        self.assertEqual(lead.route, "digital")


    def test_json_digital_product_id_requires_exact_integer_not_string_or_boolean(self):
        payload = {**self.data, "service": "digital", "product_id": 72}
        accepted = self.post(payload)
        self.assertEqual(accepted.status_code, 201, accepted.content[:300])
        self.assertEqual(MojPropRequest.objects.get().product_id, 72)
        for raw_id in ("72", 72.0, True, None, -72, 999):
            with self.subTest(product_id=raw_id):
                rejected = self.post({**payload, "product_id": raw_id})
                self.assertEqual(rejected.status_code, 400, rejected.content[:300])
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_browser_form_noncanonical_digital_sku_is_rejected(self):
        for sku in ("072", "+72", "72 ", "72.0", "۷۲", "999", ""):
            with self.subTest(sku=sku):
                response = self.client.post(
                    "/moj-prop-intake/",
                    {**self.data, "service": "digital", "product_id": sku,
                     "consent": "on"},
                    HTTP_X_CSRFTOKEN=self.token,
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(MojPropRequest.objects.count(), 0)


    def test_unpaired_unicode_surrogate_cannot_reach_customer_database(self):
        for key in ("name", "notes"):
            with self.subTest(field=key):
                data = {**self.data, key: self.data[key] + chr(0xD800)}
                response = self.post(data)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_deep_json_structure_returns_400_instead_of_server_error(self):
        raw = "[" * 1100 + "0" + "]" * 1100
        response = self.post(raw=raw)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_negative_declared_body_size_rejected_at_parser_boundary(self):
        from django.test import RequestFactory
        from core.mojprop_views import _payload
        request = RequestFactory().post(
            "/moj-prop-intake/", json.dumps(self.data),
            content_type="application/json",
        )
        request.META["CONTENT_LENGTH"] = "-1"
        self.assertIsNone(_payload(request))

    @override_settings(MOJPROP_TRUSTED_PROXIES=("127.0.0.1",))
    def test_malformed_trusted_forwarded_headers_cannot_rotate_rate_keys(self):
        bad_ips = ("1.2.3.4, 5.6.7.8", "not-an-ip", "203.0.113.999",
                   "x" * 150, "198.51.100.3; spoofed", "8.8.8.8,")
        for index, bad in enumerate(bad_ips):
            response = self.post(
                {**self.data, "email": f"distinct{index}@example.org"},
                REMOTE_ADDR="127.0.0.1", HTTP_X_REAL_IP=bad,
            )
            self.assertEqual(response.status_code, 201 if index < 5 else 429)
        self.assertEqual(MojPropRequest.objects.count(), 5)
