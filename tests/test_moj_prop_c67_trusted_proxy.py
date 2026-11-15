"""Trusted reverse proxy must be pinned before per-visitor abuse checks."""
from django.test import TestCase, override_settings
from core.models import MojPropRateBucket, MojPropRequest

URL="/moj-prop-intake/"
FORM={"name":"Interested Buyer","email":"visitor@example.org",
      "service":"audit","horizon":"week",
      "notes":"Please review the research delivery scope and pricing.",
      "consent":"yes"}


@override_settings(ALLOWED_HOSTS=["testserver"])
class MojPropC67TrustedProxyTests(TestCase):
    def post(self,email="visitor@example.org",peer="10.11.12.13",forwarded="203.0.113.3",**extra):
        meta={"REMOTE_ADDR":peer,"HTTP_X_REAL_IP":forwarded}
        meta.update(extra)
        return self.client.post(URL,data={**FORM,"email":email},**meta)

    @override_settings(MOJ_PROP_TRUSTED_PROXY_IPS=["10.11.12.13"])
    def test_known_proxy_has_distinct_real_visitor_quota(self):
        for i in range(5):
            self.assertEqual(self.post(email=f"v{i}@example.org",
                                      forwarded="203.0.113.30").status_code,201)
        self.assertEqual(self.post(email="over@example.org",
                                   forwarded="203.0.113.30").status_code,429)
        self.assertEqual(self.post(email="other@example.org",
                                   forwarded="203.0.113.31").status_code,201)
        self.assertEqual(MojPropRequest.objects.count(),6)

    @override_settings(MOJ_PROP_TRUSTED_PROXY_IPS=[])
    def test_unpinned_peer_cannot_spoof_visitor_origin(self):
        for i in range(5):
            self.post(email=f"v{i}@example.org",forwarded=f"203.0.113.{i+1}")
        self.assertEqual(self.post(email="last@example.org",
                                   forwarded="203.0.113.240").status_code,429)

    @override_settings(MOJ_PROP_TRUSTED_PROXY_IPS=["10.11.12.13"])
    def test_trusted_proxy_missing_identity_fails_closed(self):
        self.assertEqual(self.post(forwarded="").status_code,503)
        self.assertFalse(MojPropRequest.objects.exists())

    @override_settings(MOJ_PROP_TRUSTED_PROXY_IPS=["10.11.12.13"])
    def test_trusted_proxy_cannot_supply_untrusted_comma_chain(self):
        self.assertEqual(self.post(forwarded="203.0.113.1, 192.0.2.1").status_code,503)
        self.assertFalse(MojPropRateBucket.objects.exists())

    @override_settings(MOJ_PROP_TRUSTED_PROXY_IPS=["bad-origin"])
    def test_malformed_proxy_config_fails_closed_without_lead(self):
        self.assertEqual(self.post().status_code,503)
        self.assertFalse(MojPropRequest.objects.exists())

    @override_settings(MOJ_PROP_TRUSTED_PROXY_IPS="10.11.12.13")
    def test_string_allowlist_not_interpreted_as_characters(self):
        self.assertEqual(self.post().status_code,503)
        self.assertFalse(MojPropRequest.objects.exists())

    @override_settings(MOJ_PROP_TRUSTED_PROXY_IPS=["10.11.12.13"])
    def test_ipv6_visitor_behind_pinned_proxy_accepted(self):
        self.assertEqual(self.post(forwarded="2001:db8::42").status_code,201)
        self.assertEqual(MojPropRateBucket.objects.count(),2)

    @override_settings(MOJ_PROP_TRUSTED_PROXY_IPS=[])
    def test_untrusted_forwarded_for_does_not_override_immediate_peer(self):
        self.assertEqual(self.post(HTTP_X_FORWARDED_FOR="8.8.8.8").status_code,201)
        row=MojPropRequest.objects.get()
        import hashlib,hmac
        from django.conf import settings
        expected=hmac.new(settings.SECRET_KEY.encode(),b"10.11.12.13",hashlib.sha256).hexdigest()
        self.assertEqual(row.ip_hash,expected)
