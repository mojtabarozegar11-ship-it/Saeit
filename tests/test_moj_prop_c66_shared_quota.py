"""Executable real Django DB tests: one MojPropRequest, multi-worker quota."""
from django.core.cache import cache
from django.test import TestCase, override_settings
from core.models import MojPropRateBucket, MojPropRequest

URL="/moj-prop-intake/"
DATA={"name":"Interested Buyer","email":"buyer@example.org","service":"blueprint",
      "horizon":"week","notes":"Please explain the private services, terms and cost.",
      "consent":"yes"}


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com"])
class MojPropSharedQuotaTests(TestCase):
    def post(self, email=None, remote_addr="127.0.0.9", **other):
        data=dict(DATA)
        if email is not None:
            data["email"]=email
        data.update(other)
        return self.client.post(URL, data=data, REMOTE_ADDR=remote_addr)

    def test_get_is_read_only_and_discloses_csrf(self):
        response=self.client.get(URL)
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()["csrf_token"])
        self.assertEqual(MojPropRequest.objects.count(),0)

    def test_one_consent_creates_one_manual_review_request(self):
        r=self.post()
        self.assertEqual(r.status_code,201)
        self.assertEqual(r.json()["next_step"],"manual_review")
        self.assertEqual(MojPropRequest.objects.count(),1)
        self.assertEqual(MojPropRateBucket.objects.count(),2)

    def test_five_same_client_requests_allowed(self):
        for i in range(5):
            self.assertEqual(self.post(email=f"buyer{i}@example.org").status_code,201)
        self.assertEqual(MojPropRequest.objects.count(),5)

    def test_sixth_same_client_rejected(self):
        for i in range(5):
            self.post(email=f"b{i}@example.org")
        r=self.post(email="sixth@example.org")
        self.assertEqual(r.status_code,429)
        self.assertEqual(MojPropRequest.objects.count(),5)
        self.assertEqual(r.json()["retry_after"],600)

    def test_cache_clearing_does_not_reset_db_quota(self):
        for i in range(5):
            self.post(email=f"p{i}@example.org")
        cache.clear()
        self.assertEqual(self.post(email="later@example.org").status_code,429)

    def test_second_client_has_independent_hmac_bucket(self):
        for i in range(5):
            self.post(email=f"u{i}@example.org")
        self.assertEqual(self.post(email="second@example.org",
                                   remote_addr="127.0.0.10").status_code,201)
        self.assertEqual(MojPropRateBucket.objects.count(),8)

    def test_email_quota_cannot_be_bypassed_by_changing_ip(self):
        for i in range(5):
            self.assertEqual(self.post(remote_addr=f"127.0.0.{i+1}").status_code,201)
        self.assertEqual(self.post(remote_addr="127.0.0.90").status_code,429)
        self.assertEqual(MojPropRequest.objects.count(),5)

    def test_origin_bucket_uses_keyed_hash_not_plain_sha(self):
        from hashlib import sha256
        self.post()
        for row in MojPropRateBucket.objects.all():
            self.assertEqual(len(row.digest),64)
            self.assertNotEqual(row.digest,sha256(b"127.0.0.9").hexdigest())

    def test_reject_without_consent_creates_no_bucket(self):
        r=self.post(consent="")
        self.assertEqual(r.status_code,400)
        self.assertEqual(MojPropRateBucket.objects.count(),0)

    def test_reject_bad_email_creates_no_bucket(self):
        r=self.post(email="not-valid")
        self.assertEqual(r.status_code,400)
        self.assertEqual(MojPropRateBucket.objects.count(),0)

    def test_rejected_sixth_attempt_does_not_increment_any_counter(self):
        for i in range(5):
            self.post(email=f"x{i}@example.org")
        before={r.digest:r.count for r in MojPropRateBucket.objects.all()}
        self.post(email="later@example.org")
        after={r.digest:r.count for r in MojPropRateBucket.objects.all()}
        self.assertEqual(before,after)

    def test_quota_is_anonymous_not_a_new_signup_system(self):
        self.post()
        row=MojPropRequest.objects.get()
        self.assertTrue(row.consent)
        self.assertEqual(row.status,"new")
        self.assertEqual(row.source,"moj-prop-public")
        self.assertNotIn("paid",row.__dict__)
