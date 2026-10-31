import json
import unittest

from scripts.s01_live_passenger_health_readonly_20261031 import classify_response


class LivePassengerHealthReadonlyTests(unittest.TestCase):
    def response(self, status=200, host="mojplaywin.com", payload=None):
        if payload is None:
            payload = {"status": "ok", "service": "saeit", "database": "ok"}
        return classify_response(status, f"https://{host}/api/health/", json.dumps(payload).encode())

    def test_live_health_select1_result_confirms_same_site_passenger_db(self):
        result = self.response()
        self.assertTrue(result["same_site_https"])
        self.assertTrue(result["live_passenger_db_select1_verified"])
        self.assertTrue(result["passenger_worker_db_authority_verified"])
        self.assertFalse(result["database_modified"])
        self.assertEqual(result["customer_rows_read"], 0)
        self.assertEqual(result["business_rows_read"], 0)
        self.assertEqual(result["orders_created"], 0)
        self.assertEqual(result["payments_created"], 0)

    def test_degraded_database_does_not_confirm_authority(self):
        result = self.response(payload={"status": "degraded", "service": "saeit", "database": "unavailable"})
        self.assertFalse(result["live_passenger_db_select1_verified"])
        self.assertEqual(result["database_status"], "unavailable")

    def test_http_error_does_not_confirm_authority(self):
        result = self.response(status=503)
        self.assertFalse(result["passenger_worker_db_authority_verified"])

    def test_cross_site_redirect_does_not_confirm_authority(self):
        result = self.response(host="attacker.example")
        self.assertFalse(result["same_site_https"])
        self.assertFalse(result["passenger_worker_db_authority_verified"])

    def test_unexpected_service_or_invalid_payload_fails_closed(self):
        for payload in [
            {"status": "ok", "database": "ok", "service": "other"},
            {"not_json_contract": True},
        ]:
            result = self.response(payload=payload)
            self.assertFalse(result["passenger_worker_db_authority_verified"])

    def test_oversized_response_fails_closed(self):
        body = b" " * 4097
        result = classify_response(200, "https://mojplaywin.com/api/health/", body)
        self.assertFalse(result["passenger_worker_db_authority_verified"])


if __name__ == "__main__":
    unittest.main()
