"""Commerce-relevant buyer anti-abuse responses have cache and retry semantics."""
from django.test import TestCase, override_settings
from core.models import MojPropRequest

URL="/moj-prop-intake/"
BASE={"name":"Buyer","email":"one@example.org","service":"blueprint",
      "horizon":"week","notes":"A legitimate inquiry about program design fees.",
      "consent":"yes"}


@override_settings(ALLOWED_HOSTS=["testserver"])
class MojPropC67ResponseContractTests(TestCase):
    def post(self,email):
        params=dict(BASE,email=email)
        return self.client.post(URL,data=params,REMOTE_ADDR="127.0.0.91")

    def test_quota_response_includes_retry_after(self):
        for i in range(5):
            self.assertEqual(self.post(f"visitor{i}@example.org").status_code,201)
        blocked=self.post("over@example.org")
        self.assertEqual(blocked.status_code,429)
        self.assertEqual(blocked["Retry-After"],"600")
        self.assertEqual(blocked.json()["retry_after"],600)

    def test_quota_error_not_cached_by_public_edge(self):
        for i in range(6):
            r=self.post(f"v{i}@example.org")
        self.assertEqual(r.status_code,429)
        self.assertEqual(r["Cache-Control"],"no-store")

    def test_json_is_never_sniffed_as_html(self):
        success=self.post("good@example.org")
        self.assertEqual(success.status_code,201)
        self.assertEqual(success["X-Content-Type-Options"],"nosniff")
        self.assertIn("application/json",success["Content-Type"])

    def test_invalid_buyer_payload_not_cached(self):
        response=self.client.post(URL,data={"name":"x"})
        self.assertEqual(response.status_code,400)
        self.assertEqual(response["Cache-Control"],"no-store")

    def test_no_payment_claim_in_public_success(self):
        response=self.post("visitor@example.org")
        self.assertEqual(response.status_code,201)
        self.assertNotIn("paid",response.json())
        self.assertNotIn("transaction_id",response.json())
        self.assertEqual(MojPropRequest.objects.count(),1)
