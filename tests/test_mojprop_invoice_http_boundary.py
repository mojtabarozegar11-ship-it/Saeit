import json
from unittest.mock import patch
from django.test import RequestFactory, SimpleTestCase, override_settings
from types import SimpleNamespace
from prop_firm.plan1_views import start_plan1_invoice

@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "zomorodmelal.ir"])
class InvoiceBoundaryTests(SimpleTestCase):
    def request(self, payload, host="mojplaywin.com", secure=True):
        request = RequestFactory().post("/moj-prop/plan1/start/", data=json.dumps(payload), content_type="application/json", secure=secure, HTTP_HOST=host)
        request.user = SimpleNamespace(is_authenticated=True, email="buyer@example.com")
        request._dont_enforce_csrf_checks = True
        return request

    @patch("prop_firm.plan1_views._runtime_release_enabled", return_value=True)
    @patch("prop_firm.plan1_views.persist_plan1_invoice")
    def test_non_mojplaywin_host_rejected(self, persist, gate):
        self.assertEqual(start_plan1_invoice(self.request({}, host="zomorodmelal.ir")).status_code, 404)
        persist.assert_not_called()

    @patch("prop_firm.plan1_views._runtime_release_enabled", return_value=True)
    @patch("prop_firm.plan1_views.persist_plan1_invoice")
    def test_http_rejected(self, persist, gate):
        self.assertEqual(start_plan1_invoice(self.request({}, secure=False)).status_code, 404)
        persist.assert_not_called()

    @patch("prop_firm.plan1_views._runtime_release_enabled", return_value=True)
    @patch("prop_firm.plan1_views.persist_plan1_invoice")
    def test_nonobject_json_rejected(self, persist, gate):
        self.assertEqual(start_plan1_invoice(self.request([])).status_code, 400)
        persist.assert_not_called()

    @patch("prop_firm.plan1_views._runtime_release_enabled", return_value=True)
    @patch("prop_firm.plan1_views.persist_plan1_invoice")
    def test_client_retry_attestation_rejected(self, persist, gate):
        payload = {"buyer_email":"buyer@example.com", "buyer_terms_acceptance":True, "purchase_kind":"retry", "retry_eligibility_verified":True}
        self.assertEqual(start_plan1_invoice(self.request(payload)).status_code, 403)
        persist.assert_not_called()
