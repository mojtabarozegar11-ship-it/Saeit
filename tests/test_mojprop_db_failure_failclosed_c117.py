"""C117 fail-closed real Django Moj Prop CRM outage regressions.

Every test uses only Django test DB and mocked storage faults; no real lead,
customer record, web request, mail, TRON payment or production action.
"""
import json
from unittest.mock import patch

from django.db import DatabaseError, IntegrityError
from django.test import Client, TestCase

from core.models import MojPropRequest

KEY = "11111111-1111-4111-8111-111111111111"


class MojPropCrmOutageC117Tests(TestCase):
    def setUp(self):
        self.browser = Client(enforce_csrf_checks=True)
        initial = self.browser.get("/moj-prop-intake/")
        self.assertEqual(initial.status_code, 200)
        self.csrf = initial.json()["csrf_token"]

    def request(self, *, keyed=False):
        data = {
            "name": "CRM failure recovery",
            "email": "buyer@example.com",
            "service": "blueprint",
            "horizon": "week",
            "notes": "Please prepare an educational written proposal for review.",
            "consent": True,
            "website": "",
        }
        if keyed:
            data["idempotency_key"] = KEY
        return self.browser.post(
            "/moj-prop-intake/",
            data=json.dumps(data),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def assert_no_receipt(self, result):
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result["Cache-Control"], "no-store")
        self.assertEqual(result["Referrer-Policy"], "no-referrer")
        self.assertEqual(result["Retry-After"], "60")
        body = result.json()
        self.assertFalse(body["ok"])
        self.assertFalse(body["storage_confirmed"])
        self.assertEqual(body["payment_status"], "not_collected_by_this_service")
        self.assertNotIn("receipt_token", body)
        self.assertNotIn("request_id", body)
        self.assertNotIn("buyer@example.com", result.content.decode())

    def test_01_existing_key_lookup_db_down_returns_unconfirmed_503(self):
        with patch.object(MojPropRequest.objects, "filter",
                          side_effect=DatabaseError("private internal SQL details")):
            response = self.request(keyed=True)
        self.assert_no_receipt(response)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_02_rate_limit_lookup_db_down_returns_unconfirmed_503(self):
        with patch("core.mojprop_views._rate_limited",
                   side_effect=DatabaseError("rate storage unavailable")):
            response = self.request()
        self.assert_no_receipt(response)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_03_insert_db_down_returns_unconfirmed_503(self):
        with patch.object(MojPropRequest.objects, "create",
                          side_effect=DatabaseError("write failed")):
            response = self.request()
        self.assert_no_receipt(response)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_04_keyed_insert_db_down_returns_unconfirmed_503(self):
        with patch.object(MojPropRequest.objects, "create",
                          side_effect=DatabaseError("write failed")):
            response = self.request(keyed=True)
        self.assert_no_receipt(response)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_05_keyed_integrity_race_recovery_db_down_is_not_500(self):
        real_filter = MojPropRequest.objects.filter
        visits = {"count": 0}

        def mocked_filter(*args, **kwargs):
            visits["count"] += 1
            if visits["count"] >= 2:
                raise DatabaseError("conflict lookup unavailable")
            return real_filter(*args, **kwargs)

        with patch.object(MojPropRequest.objects, "filter", side_effect=mocked_filter):
            with patch("core.mojprop_views._rate_limited", return_value=False):
                with patch.object(MojPropRequest.objects, "create",
                                  side_effect=IntegrityError("duplicate key")):
                    response = self.request(keyed=True)
        self.assertEqual(visits["count"], 2)  # initial and post-conflict lookup
        self.assert_no_receipt(response)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_06_valid_request_with_storage_available_still_returns_receipt(self):
        response = self.request(keyed=True)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["ok"])
        self.assertTrue(response.json()["receipt_token"])
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_11_invalid_consent_is_rejected_before_crm_database_access(self):
        with patch.object(MojPropRequest.objects, "filter",
                          side_effect=DatabaseError("unreachable")):
            response = self.browser.post(
                "/moj-prop-intake/",
                data=json.dumps({
                    "name": "Name",
                    "email": "buyer@example.com",
                    "service": "blueprint",
                    "horizon": "week",
                    "notes": "Please prepare written educational terms for review.",
                    "consent": False,
                    "website": "",
                }),
                content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf,
            )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("receipt_token", response.json())
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_12_invalid_uuid_is_rejected_before_crm_database_access(self):
        with patch.object(MojPropRequest.objects, "filter",
                          side_effect=DatabaseError("unreachable")):
            result = self.browser.post(
                "/moj-prop-intake/",
                data=json.dumps({
                    "name": "Name",
                    "email": "buyer@example.com",
                    "service": "blueprint",
                    "horizon": "week",
                    "notes": "Please prepare written educational terms for review.",
                    "consent": True,
                    "website": "",
                    "idempotency_key": "not-an-uuid",
                }),
                content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf,
            )
        self.assertEqual(result.status_code, 400)
        self.assertNotIn("receipt_token", result.json())
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_07_json_receipt_status_db_failure_is_private_503(self):
        created = self.request(keyed=True)
        token = created.json()["receipt_token"]
        with patch.object(MojPropRequest.objects, "filter",
                          side_effect=DatabaseError("do not leak SQL")):
            result = self.browser.post(
                "/moj-prop-status/",
                data=json.dumps({"receipt_token": token}),
                content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf,
            )
        self.assert_no_receipt(result)
        self.assertNotIn(token, result.content.decode())

    def test_09_reconnect_same_uuid_after_outage_creates_only_one_real_lead(self):
        with patch("core.mojprop_views._rate_limited",
                   side_effect=DatabaseError("SQL temporarily offline")):
            failed = self.request(keyed=True)
        self.assert_no_receipt(failed)
        first = self.request(keyed=True)
        second = self.request(keyed=True)
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(first.json()["request_id"], second.json()["request_id"])
        self.assertTrue(second.json()["reused"])
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_10_html_request_db_outage_returns_private_503_and_no_false_receipt(self):
        csrf_page = self.browser.get("/moj-prop-intake/?format=html")
        self.assertEqual(csrf_page.status_code, 200)
        with patch("core.mojprop_views._rate_limited",
                   side_effect=DatabaseError("private auth SQL details")):
            response = self.browser.post(
                "/moj-prop-intake/?format=html",
                data={
                    "name": "Native HTML customer",
                    "email": "buyer@example.com",
                    "service": "blueprint",
                    "horizon": "week",
                    "notes": "Please prepare written educational terms for review.",
                    "consent": "on",
                    "website": "",
                },
                HTTP_X_CSRFTOKEN=self.csrf,
            )
        self.assertEqual(response.status_code, 503)
        self.assertIn("no-store", response.get("Cache-Control", ""))
        self.assertIn(b"Request status unavailable", response.content)
        self.assertNotIn(b"buyer@example.com", response.content)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_08_html_receipt_status_db_failure_has_no_bearer_in_html(self):
        created = self.request(keyed=True)
        token = created.json()["receipt_token"]
        html_form = self.browser.get("/moj-prop-status/?format=html")
        self.assertEqual(html_form.status_code, 200)
        with patch.object(MojPropRequest.objects, "filter",
                          side_effect=DatabaseError("private SQL failure")):
            result = self.browser.post(
                "/moj-prop-status/?format=html",
                data={"receipt_token": token}, HTTP_X_CSRFTOKEN=self.csrf,
            )
        self.assertEqual(result.status_code, 503)
        self.assertIn(b"temporarily unavailable", result.content)
        self.assertNotIn(token.encode(), result.content)
        self.assertIn("no-store", result.get("Cache-Control", ""))
        self.assertEqual(result.get("Retry-After"), "60")
        self.assertEqual(MojPropRequest.objects.count(), 1)
