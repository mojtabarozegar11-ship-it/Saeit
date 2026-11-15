"""Protect public Moj Prop lead conversion without any live finance actions."""
from datetime import timedelta
from unittest.mock import patch
from django.db import DatabaseError, IntegrityError
from django.test import TestCase, override_settings
from django.utils import timezone
from core.models import MojPropRateBucket, MojPropRequest
from tests.test_moj_prop_c66_shared_quota import DATA, URL


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com"])
class MojPropCanonicalSecurityTests(TestCase):
    def post(self, **kwargs):
        data=dict(DATA)
        data.update(kwargs.pop("data",{}))
        return self.client.post(URL, data=data, **kwargs)

    def test_spoofed_x_real_ip_does_not_allow_sixth_request(self):
        for i in range(5):
            self.assertEqual(self.post(REMOTE_ADDR="127.0.0.2",
                                       HTTP_X_REAL_IP=f"8.8.8.{i+1}").status_code,201)
        self.assertEqual(self.post(REMOTE_ADDR="127.0.0.2",
                                   HTTP_X_REAL_IP="1.1.1.1").status_code,429)

    def test_spoofed_x_forwarded_for_does_not_allow_sixth_request(self):
        for i in range(5):
            self.post(REMOTE_ADDR="127.0.0.3",HTTP_X_FORWARDED_FOR=f"10.1.2.{i+1}")
        self.assertEqual(self.post(REMOTE_ADDR="127.0.0.3",
                                   HTTP_X_FORWARDED_FOR="10.1.2.99").status_code,429)

    def test_malformed_origin_fails_closed_without_lead(self):
        self.assertEqual(self.post(REMOTE_ADDR="this-is-not-ip").status_code,503)
        self.assertEqual(MojPropRequest.objects.count(),0)
        self.assertEqual(MojPropRateBucket.objects.count(),0)

    def test_missing_origin_fails_closed(self):
        self.assertEqual(self.post(REMOTE_ADDR="").status_code,503)
        self.assertEqual(MojPropRequest.objects.count(),0)

    def test_rejected_honeypot_never_touches_quota(self):
        response=self.post(data={"website":"junk"})
        self.assertEqual(response.status_code,400)
        self.assertFalse(MojPropRateBucket.objects.exists())

    def test_malformed_json_never_touches_quota(self):
        response=self.client.post(URL,data="{not-json",
                                  content_type="application/json")
        self.assertEqual(response.status_code,400)
        self.assertFalse(MojPropRateBucket.objects.exists())

    def test_database_quota_failure_yields_recoverable_503(self):
        with patch("core.mojprop_views.MojPropRateBucket.objects.select_for_update",
                   side_effect=DatabaseError("private database down")):
            r=self.post()
        self.assertEqual(r.status_code,503)
        self.assertEqual(MojPropRequest.objects.count(),0)

    def test_request_insert_failure_rolls_back_both_quota_buckets(self):
        with patch("core.mojprop_views.MojPropRequest.objects.create",
                   side_effect=DatabaseError("lead database unavailable")):
            r=self.post()
        self.assertEqual(r.status_code,503)
        self.assertEqual(MojPropRateBucket.objects.count(),0)
        self.assertEqual(MojPropRequest.objects.count(),0)

    def test_request_id_collision_retry_cannot_double_consume_quota(self):
        original=MojPropRequest.objects.create
        calls={"n":0}
        def conflict_first(*args,**kwargs):
            calls["n"]+=1
            if calls["n"]==1:
                raise IntegrityError("simulated unique id collision")
            return original(*args,**kwargs)
        with patch("core.mojprop_views.MojPropRequest.objects.create",
                   side_effect=conflict_first):
            r=self.post()
        self.assertEqual(r.status_code,201)
        self.assertEqual(MojPropRateBucket.objects.count(),2)
        self.assertEqual(sorted(x.count for x in MojPropRateBucket.objects.all()),[1,1])
        self.assertEqual(MojPropRequest.objects.count(),1)

    def test_never_reports_funded_account_or_payment_created(self):
        r=self.post()
        self.assertEqual(r.status_code,201)
        self.assertNotIn("amount",r.json())
        self.assertNotIn("funded",r.json())
        self.assertNotIn("payment_address",r.json())

    def test_no_raw_origin_email_or_user_agent_in_quota_table(self):
        self.post(REMOTE_ADDR="192.0.2.11",HTTP_USER_AGENT="buyer special")
        for row in MojPropRateBucket.objects.all():
            self.assertEqual(set(row.__dict__)-{"_state"},
                             {"digest","count","expires_at"})
            self.assertNotIn("192.0.2.11",str(row.__dict__))
            self.assertNotIn("buyer@example.org",str(row.__dict__))
            self.assertNotIn("buyer special",str(row.__dict__))

    def test_bucket_expiry_is_roughly_30_minutes(self):
        now=timezone.now()
        self.post()
        bucket=MojPropRateBucket.objects.first()
        self.assertGreater(bucket.expires_at,now+timedelta(minutes=20))
        self.assertLess(bucket.expires_at,now+timedelta(minutes=31))
